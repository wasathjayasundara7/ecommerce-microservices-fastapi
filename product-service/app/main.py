from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models
from .database import engine, get_db
from .models import ProductCreate, ProductUpdate, ProductResponse
from jose import JWTError, jwt
import httpx

# Create all DB tables on startup
models.ProductTable.metadata.create_all(bind=engine)

SECRET_KEY = "ecommerce-super-secret-key-2026"
ALGORITHM  = "HS256"

app = FastAPI(
    title="Product Service",
    description="Manages the product catalogue for the E-Commerce platform.",
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

# ── Proxy login — forwards to User Service ────────────────────
@app.post("/login", tags=["Auth"], include_in_schema=False)
async def login_proxy(form_data: OAuth2PasswordRequestForm = Depends()):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/login",
            data={
                "username": form_data.username,
                "password": form_data.password
            }
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return response.json()

# ── Helper: validate JWT and extract username + role ──────────
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

# ── Helper: admin only ────────────────────────────────────────
def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user

# ── Routes ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Product Service", "status": "running", "port": 8002}

@app.post("/products", response_model=ProductResponse, tags=["Products (Shop Owner Only)"], status_code=201)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)   # ← changed
):
    new_product = models.ProductTable(**product.model_dump())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@app.get("/products", response_model=list[ProductResponse], tags=["Products (Accessible to All)"])
def get_all_products(db: Session = Depends(get_db)):
    return db.query(models.ProductTable).filter(
        models.ProductTable.is_active == True
    ).all()

@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products (Accessible to All)"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.ProductTable).filter(
        models.ProductTable.id == product_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products (Shop Owner Only)"])
def update_product(
    product_id: int,
    update_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)   # ← changed
):
    product = db.query(models.ProductTable).filter(
        models.ProductTable.id == product_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product

@app.delete("/products/{product_id}", tags=["Products (Shop Owner Only)"])
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)   # ← changed
):
    product = db.query(models.ProductTable).filter(
        models.ProductTable.id == product_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": f"Product {product_id} deleted successfully"}