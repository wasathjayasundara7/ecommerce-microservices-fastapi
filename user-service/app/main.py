from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from . import models, auth
from .database import engine, get_db
from .models import UserCreate, UserUpdate, UserResponse, Token

models.UserTable.metadata.create_all(bind=engine)

app = FastAPI(
    title="User Service",
    description="Handles user registration, login and JWT authentication for the E-Commerce platform.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

ADMIN_SECRET = "admin-secret-2026"

#Helper: get current user from JWT
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    username, role = auth.decode_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(models.UserTable).filter(
        models.UserTable.username == username
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

#Helper: admin only
def require_admin(current_user: models.UserTable = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user

#Routes
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "User Service", "status": "running", "port": 8001}

@app.post("/register", response_model=UserResponse, tags=["Customer"], status_code=201)
def register_customer(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(models.UserTable).filter(
        models.UserTable.username == user.username
    ).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(models.UserTable).filter(
        models.UserTable.email == user.email
    ).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = models.UserTable(
        username=user.username,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        role="customer"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/register/admin", response_model=UserResponse, tags=["Shop Owner"], status_code=201)
def register_admin(
    user: UserCreate,
    admin_key: str,
    db: Session = Depends(get_db)
):
    if admin_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret key")
    if db.query(models.UserTable).filter(
        models.UserTable.username == user.username
    ).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(models.UserTable).filter(
        models.UserTable.email == user.email
    ).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    new_admin = models.UserTable(
        username=user.username,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        role="admin"
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin

@app.post("/login", response_model=Token, tags=["Customer"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.UserTable).filter(
        models.UserTable.username == form_data.username
    ).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    token = auth.create_access_token(data={
        "sub": user.username,
        "role": user.role
    })
    return {"access_token": token, "token_type": "bearer"}

#Customer routes
# @app.get("/users/me", response_model=UserResponse, tags=["Customer"])
# def get_me(current_user: models.UserTable = Depends(get_current_user)):
#     if current_user.role == "admin":
#         raise HTTPException(
#             status_code=403,
#             detail="Admins do not have a personal profile. Use admin routes."
#         )
#     return current_user

# @app.put("/users/me", response_model=UserResponse, tags=["Customer"])
# def update_me(
#     update_data: UserUpdate,
#     db: Session = Depends(get_db),
#     current_user: models.UserTable = Depends(get_current_user)
# ):
#     if current_user.role == "admin":
#         raise HTTPException(
#             status_code=403,
#             detail="Admins cannot update via this route."
#         )
#     if update_data.email:
#         existing = db.query(models.UserTable).filter(
#             models.UserTable.email == update_data.email
#         ).first()
#         if existing and existing.id != current_user.id:
#             raise HTTPException(status_code=400, detail="Email already in use")
#         current_user.email = update_data.email
#     if update_data.password:
#         current_user.hashed_password = auth.hash_password(update_data.password)
#     db.commit()
#     db.refresh(current_user)
#     return current_user

#Admin routes
@app.get("/admin/users", response_model=list[UserResponse], tags=["Shop Owner"])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.UserTable = Depends(require_admin)
):
    # Admin sees only customers, not other admins
    return db.query(models.UserTable).filter(
        models.UserTable.role == "customer"
    ).all()

@app.get("/admin/users/{user_id}", response_model=UserResponse, tags=["Shop Owner"])
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.UserTable = Depends(require_admin)
):
    user = db.query(models.UserTable).filter(
        models.UserTable.id == user_id,
        models.UserTable.role == "customer"
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")
    return user

@app.put("/admin/users/{user_id}", response_model=UserResponse, tags=["Shop Owner"])
def update_user_by_id(
    user_id: int,
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.UserTable = Depends(require_admin)
):
    user = db.query(models.UserTable).filter(
        models.UserTable.id == user_id,
        models.UserTable.role == "customer"
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")

    if update_data.email:
        existing = db.query(models.UserTable).filter(
            models.UserTable.email == update_data.email
        ).first()
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = update_data.email

    if update_data.password:
        user.hashed_password = auth.hash_password(update_data.password)

    db.commit()
    db.refresh(user)
    return user

@app.delete("/admin/users/{user_id}", tags=["Shop Owner"])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.UserTable = Depends(require_admin)
):
    user = db.query(models.UserTable).filter(
        models.UserTable.id == user_id,
        models.UserTable.role == "customer"
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(user)
    db.commit()
    return {"message": f"Customer '{user.username}' deleted successfully"}