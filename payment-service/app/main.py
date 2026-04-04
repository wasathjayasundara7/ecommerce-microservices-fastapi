from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from . import models
from .database import engine, get_db
from .models import PaymentCreate, PaymentResponse
import httpx

models.PaymentTable.metadata.create_all(bind=engine)

SECRET_KEY             = "ecommerce-super-secret-key-2026"
ALGORITHM              = "HS256"
ORDER_SERVICE_URL      = "http://localhost:8003"
NOTIFICATION_SERVICE_URL = "http://localhost:8005"
INTERNAL_SECRET        = "internal-service-secret-2026"

VALID_PAYMENT_METHODS  = ["credit_card", "debit_card", "paypal", "bank_transfer"]

app = FastAPI(
    title="Payment Service (Customer Only)",
    description="Processes payments for orders in the E-Commerce platform.",
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

# Proxy login — forwards to User Service
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

# Helper: decode JWT → username and role
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

# Helper: customers only 
def require_customer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only customers can make payments."
        )
    return current_user

# Helper: fetch and validate order from Order Service
async def fetch_order(order_id: int, username: str, token: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{ORDER_SERVICE_URL}/orders/{order_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Order Service unavailable. Make sure it is running on port 8003."
            )
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Order with id {order_id} does not exist or does not belong to you"
        )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to retrieve order details")

    order = response.json()

    # Make sure order belongs to current user
    if order["username"] != username:
        raise HTTPException(
            status_code=403,
            detail="This order does not belong to you"
        )
    # Make sure order is still pending
    if order["status"] == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Cannot pay for a cancelled order"
        )
    if order["status"] == "paid":
        raise HTTPException(
            status_code=400,
            detail="This order has already been paid"
        )
    return order

# Helper: auto-trigger notification after payment
async def send_notification(username: str, order_id: int, amount: float):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notifications/internal",
                json={
                    "username": username,
                    "message": f"Your payment of ${amount} for order #{order_id} was successful!",
                    "type": "payment_success"
                },
                headers={"x-internal-secret": INTERNAL_SECRET}
            )
        except httpx.ConnectError:
            # Notification failure should NOT block payment success
            pass

# Helper: update order status to paid
async def mark_order_as_paid(order_id: int, token: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.put(
                f"{ORDER_SERVICE_URL}/orders/{order_id}/mark-paid",
                headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.ConnectError:
            pass

# Routes
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Payment Service", "status": "running", "port": 8004}

@app.post("/payments", response_model=PaymentResponse, tags=["Payments"], status_code=201)
async def process_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
    token: str = Depends(oauth2_scheme)
):
    # Validate payment method
    if payment.payment_method not in VALID_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment method. Choose from: {', '.join(VALID_PAYMENT_METHODS)}"
        )

    # Check order has not already been paid by this user
    already_paid = db.query(models.PaymentTable).filter(
        models.PaymentTable.order_id == payment.order_id,
        models.PaymentTable.status == "completed"
    ).first()
    if already_paid:
        raise HTTPException(
            status_code=400,
            detail=f"Order {payment.order_id} has already been paid"
        )

    # Fetch and validate order from Order Service
    order = await fetch_order(payment.order_id, current_user["username"], token)

    # Record the payment
    new_payment = models.PaymentTable(
        username=current_user["username"],
        order_id=order["id"],
        amount=order["total_price"],
        payment_method=payment.payment_method,
        status="completed"
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)

    # Automatically trigger notification — fire and forget
    await send_notification(
        username=current_user["username"],
        order_id=order["id"],
        amount=order["total_price"]
    )

    # Mark order as paid in Order Service
    await mark_order_as_paid(order["id"], token)

    return new_payment

@app.get("/payments", response_model=list[PaymentResponse], tags=["Payments"])
def get_my_payments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    return db.query(models.PaymentTable).filter(
        models.PaymentTable.username == current_user["username"]
    ).all()

@app.get("/payments/{payment_id}", response_model=PaymentResponse, tags=["Payments"])
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    payment = db.query(models.PaymentTable).filter(
        models.PaymentTable.id == payment_id,
        models.PaymentTable.username == current_user["username"]
    ).first()
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found or does not belong to you"
        )
    return payment