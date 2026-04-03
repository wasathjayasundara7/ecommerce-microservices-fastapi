from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from . import models
from .database import engine, get_db
from .models import OrderCreate, OrderResponse
import httpx

models.OrderTable.metadata.create_all(bind=engine)

SECRET_KEY          = "ecommerce-super-secret-key-2026"
ALGORITHM           = "HS256"
PRODUCT_SERVICE_URL = "http://localhost:8002"

app = FastAPI(
    title="Order Service (Customer Only)",
    description="Manages customer orders for the E-Commerce platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Proxy login 
@app.post("/login", tags=["Auth"], include_in_schema=False)
async def login_proxy(form_data: OAuth2PasswordRequestForm = Depends()):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/login",
            data={"username": form_data.username, "password": form_data.password}
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return response.json()

# decode JWT → returns username and role 
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str     = payload.get("role")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

# customers only 
def require_customer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only customers can perform this action."
        )
    return current_user

# fetch and validate product 
async def fetch_product(product_id: int):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Product Service unavailable. Make sure it is running on port 8002."
            )
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Product with id {product_id} does not exist"
        )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to retrieve product details")
    product = response.json()
    if not product.get("is_active"):
        raise HTTPException(status_code=400, detail="Product is no longer available")
    return product

#  Routes 
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Order Service", "status": "running", "port": 8003}

@app.post("/orders", response_model=OrderResponse, tags=["Orders"], status_code=201)
async def place_order(
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    product = await fetch_product(order.product_id)

    if product["stock"] < order.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Available: {product['stock']}"
        )

    unit_price  = product["price"]
    total_price = round(unit_price * order.quantity, 2)

    new_order = models.OrderTable(
        username=current_user["username"],
        product_id=product["id"],
        product_name=product["name"],
        quantity=order.quantity,
        unit_price=unit_price,
        total_price=total_price,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

@app.get("/orders", response_model=list[OrderResponse], tags=["Orders"])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    # Customer sees only their own orders 
    return db.query(models.OrderTable).filter(
        models.OrderTable.username == current_user["username"]
    ).all()

@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    order = db.query(models.OrderTable).filter(
        models.OrderTable.id == order_id,
        models.OrderTable.username == current_user["username"]
    ).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found or does not belong to you"
        )
    return order

@app.put("/orders/{order_id}/cancel", response_model=OrderResponse, tags=["Orders"])
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    order = db.query(models.OrderTable).filter(
        models.OrderTable.id == order_id,
        models.OrderTable.username == current_user["username"]
    ).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found or does not belong to you"
        )
    if order.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Order is already cancelled"
        )
    if order.status == "delivered":
        raise HTTPException(
            status_code=400,
            detail="Delivered orders cannot be cancelled"
        )

    # Check if a completed payment exists for this order
    async def check_payment():
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"http://localhost:8004/payments",
                    headers={"Authorization": f"Bearer {current_user.get('token', '')}"}
                )
            except httpx.ConnectError:
                return False
            if resp.status_code == 200:
                payments = resp.json()
                for p in payments:
                    if p["order_id"] == order_id and p["status"] == "completed":
                        return True
        return False

    # Simpler approach — add a status check directly in order table
    if order.status == "paid":
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel a paid order"
        )

    order.status = "cancelled"
    db.commit()
    db.refresh(order)
    return order

# Internal route — called by Payment Service only
@app.put("/orders/{order_id}/mark-paid", tags=["Orders"])
def mark_order_paid(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    order = db.query(models.OrderTable).filter(
        models.OrderTable.id == order_id,
        models.OrderTable.username == current_user["username"]
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "paid"
    db.commit()
    db.refresh(order)
    return {"message": f"Order {order_id} marked as paid"}