from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional
import httpx

SECRET_KEY = "ecommerce-super-secret-key-2026"
ALGORITHM  = "HS256"

SERVICES = {
    "users":         "http://localhost:8001",
    "products":      "http://localhost:8002",
    "orders":        "http://localhost:8003",
    "payments":      "http://localhost:8004",
    "notifications": "http://localhost:8005",
}

#Pydantic models for request bodies
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    category: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class OrderCreate(BaseModel):
    product_id: int
    quantity: int

class PaymentCreate(BaseModel):
    order_id: int
    payment_method: str

#App setup
app = FastAPI(
    title="API Gateway of the E-Commerce Microservices",
    description="""
Single entry point for the E-Commerce Microservices platform. All requests go through port **8000**.

The gateway validates JWT tokens and routes requests to the correct microservice.

## Service Routing
| Gateway Prefix | Microservice | Port |
|---|---|---|
| `/users/...` | User Service | 8001 |
| `/products/...` | Product Service | 8002 |
| `/orders/...` | Order Service | 8003 |
| `/payments/...` | Payment Service | 8004 |
| `/notifications/...` | Notification Service | 8005 |
    """,
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

#JWT helpers
def validate_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str     = payload.get("role")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    return validate_token(token)

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied. Admin role required.")
    return current_user

def require_customer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Access denied. Only customers can perform this action.")
    return current_user

#Core proxy
async def proxy_with_body(url: str, method: str, token: Optional[str], body: dict):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {url}")
    try:
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(content={"detail": resp.text}, status_code=resp.status_code)

async def proxy_no_body(request: Request, url: str):
    headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
    full_url = url
    if request.query_params:
        full_url += f"?{request.query_params}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=full_url,
                headers=headers
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Service unavailable: {url}")
    try:
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception:
        return JSONResponse(content={"detail": resp.text}, status_code=resp.status_code)

#HEALTH
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "API Gateway", "status": "running", "port": 8000}

#USER SERVICE - Customer
@app.post("/users/register", tags=["Customer"], summary="Register Customer")
async def register_customer(body: UserCreate):
    return await proxy_with_body(
        f"{SERVICES['users']}/register", "POST", None, body.model_dump()
    )

@app.post("/users/login", tags=["Customer"], summary="Login",
          include_in_schema=True)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{SERVICES['users']}/login",
                data={
                    "username": form_data.username,
                    "password": form_data.password
                }
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="User Service unavailable")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)

# @app.get("/users/me", tags=["Customer"], summary="Get My Profile")
# async def get_me(
#     request: Request,
#     current_user: dict = Depends(require_customer)
# ):
#     return await proxy_no_body(request, f"{SERVICES['users']}/users/me")

# @app.put("/users/me", tags=["Customer"], summary="Update My Profile")
# async def update_me(
#     body: UserUpdate,
#     current_user: dict = Depends(require_customer),
#     token: str = Depends(oauth2_scheme)
# ):
#     return await proxy_with_body(
#         f"{SERVICES['users']}/users/me", "PUT", token, body.model_dump(exclude_unset=True)
#     )

#USER SERVICE - Admin
@app.post("/users/register/admin", tags=["Shop Owner"], summary="Register Admin")
async def register_admin(body: UserCreate, admin_key: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{SERVICES['users']}/register/admin",
                params={"admin_key": admin_key},
                json=body.model_dump()
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="User Service unavailable")
    return JSONResponse(content=resp.json(), status_code=resp.status_code)

@app.get("/users/admin/users", tags=["Shop Owner"], summary="Get All Customers")
async def get_all_users(
    request: Request,
    current_user: dict = Depends(require_admin)
):
    return await proxy_no_body(request, f"{SERVICES['users']}/admin/users")

@app.get("/users/admin/users/{user_id}", tags=["Shop Owner"], summary="Get Customer By ID")
async def get_user_by_id(
    user_id: int,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    return await proxy_no_body(request, f"{SERVICES['users']}/admin/users/{user_id}")

@app.put("/users/admin/users/{user_id}", tags=["Shop Owner"], summary="Update Customer By ID")
async def update_user_by_id(
    user_id: int,
    body: UserUpdate,
    current_user: dict = Depends(require_admin),
    token: str = Depends(oauth2_scheme)
):
    return await proxy_with_body(
        f"{SERVICES['users']}/admin/users/{user_id}", "PUT", token, body.model_dump(exclude_unset=True)
    )

@app.delete("/users/admin/users/{user_id}", tags=["Shop Owner"], summary="Delete Customer By ID")
async def delete_user(
    user_id: int,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    return await proxy_no_body(request, f"{SERVICES['users']}/admin/users/{user_id}")

#PRODUCT SERVICE - Public
@app.get("/products/products", tags=["Product (Accessible to All)"], summary="Get All Products")
async def get_all_products(request: Request):
    return await proxy_no_body(request, f"{SERVICES['products']}/products")

@app.get("/products/products/{product_id}", tags=["Product (Accessible to All)"], summary="Get Product By ID")
async def get_product(product_id: int, request: Request):
    return await proxy_no_body(request, f"{SERVICES['products']}/products/{product_id}")

#PRODUCT SERVICE - Admin
@app.post("/products/products", tags=["Product (Shop Owner Only)"], summary="Create Product")
async def create_product(
    body: ProductCreate,
    current_user: dict = Depends(require_admin),
    token: str = Depends(oauth2_scheme)
):
    return await proxy_with_body(
        f"{SERVICES['products']}/products", "POST", token, body.model_dump()
    )

@app.put("/products/products/{product_id}", tags=["Product (Shop Owner Only)"], summary="Update Product")
async def update_product(
    product_id: int,
    body: ProductUpdate,
    current_user: dict = Depends(require_admin),
    token: str = Depends(oauth2_scheme)
):
    return await proxy_with_body(
        f"{SERVICES['products']}/products/{product_id}", "PUT", token, body.model_dump(exclude_unset=True)
    )

@app.delete("/products/products/{product_id}", tags=["Product (Shop Owner Only)"], summary="Delete Product")
async def delete_product(
    product_id: int,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    return await proxy_no_body(request, f"{SERVICES['products']}/products/{product_id}")

#ORDER SERVICE - Customer only
@app.post("/orders/orders", tags=["Orders (Customer Only)"], summary="Place Order")
async def place_order(
    body: OrderCreate,
    current_user: dict = Depends(require_customer),
    token: str = Depends(oauth2_scheme)
):
    return await proxy_with_body(
        f"{SERVICES['orders']}/orders", "POST", token, body.model_dump()
    )

@app.get("/orders/orders", tags=["Orders (Customer Only)"], summary="Get My Orders")
async def get_my_orders(
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['orders']}/orders")

@app.get("/orders/orders/{order_id}", tags=["Orders (Customer Only)"], summary="Get Order By ID")
async def get_order(
    order_id: int,
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['orders']}/orders/{order_id}")

@app.put("/orders/orders/{order_id}/cancel", tags=["Orders (Customer Only)"], summary="Cancel Order")
async def cancel_order(
    order_id: int,
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['orders']}/orders/{order_id}/cancel")

#PAYMENT SERVICE - Customer only
@app.post("/payments/payments", tags=["Payments (Customer Only)"], summary="Process Payment")
async def process_payment(
    body: PaymentCreate,
    current_user: dict = Depends(require_customer),
    token: str = Depends(oauth2_scheme)
):
    return await proxy_with_body(
        f"{SERVICES['payments']}/payments", "POST", token, body.model_dump()
    )

@app.get("/payments/payments", tags=["Payments (Customer Only)"], summary="Get My Payments")
async def get_my_payments(
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['payments']}/payments")

@app.get("/payments/payments/{payment_id}", tags=["Payments (Customer Only)"], summary="Get Payment By ID")
async def get_payment(
    payment_id: int,
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['payments']}/payments/{payment_id}")

#NOTIFICATION SERVICE - Customer only
@app.get("/notifications/notifications/me", tags=["Notifications (Customer Only)"],
         summary="Get My Notifications")
async def get_my_notifications(
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(request, f"{SERVICES['notifications']}/notifications/me")

@app.put("/notifications/notifications/{notification_id}/read",
         tags=["Notifications (Customer Only)"],
         summary="Mark Notification As Read")
async def mark_as_read(
    notification_id: int,
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(
        request,
        f"{SERVICES['notifications']}/notifications/{notification_id}/read"
    )

@app.delete("/notifications/notifications/{notification_id}",
            tags=["Notifications (Customer Only)"],
            summary="Delete Notification")
async def delete_notification(
    notification_id: int,
    request: Request,
    current_user: dict = Depends(require_customer)
):
    return await proxy_no_body(
        request,
        f"{SERVICES['notifications']}/notifications/{notification_id}"
    )