from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from . import models
from .database import engine, get_db
from .models import NotificationInternal, NotificationResponse
import httpx
from typing import Optional

models.NotificationTable.metadata.create_all(bind=engine)

SECRET_KEY     = "ecommerce-super-secret-key-2026"
ALGORITHM      = "HS256"

# Internal secret — only Payment Service knows this
# This prevents anyone else from calling the internal route
INTERNAL_SECRET = "internal-service-secret-2026"

app = FastAPI(
    title="Notification Service (Customer Only)",
    description="Manages notifications for the E-Commerce platform. Notifications are created automatically by the Payment Service.",
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
            data={"username": form_data.username, "password": form_data.password}
        )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return response.json()

# ── Helper: decode JWT → username and role ────────────────────
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

# ── Helper: customers only ────────────────────────────────────
def require_customer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only customers can access notifications."
        )
    return current_user

# ── Helper: validate internal service secret ─────────────────
def verify_internal_secret(x_internal_secret: Optional[str] = Header(None)):
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This is an internal route."
        )

# ── Routes ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {"service": "Notification Service", "status": "running", "port": 8005}

# ── Internal route — called automatically by Payment Service ──
@app.post(
    "/notifications/internal",
    response_model=NotificationResponse,
    tags=["(Ignore this) For Payment Service Only"],
    status_code=201
)
def create_notification(
    notification: NotificationInternal,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_secret)
):
    new_notification = models.NotificationTable(
        username=notification.username,
        message=notification.message,
        type=notification.type
    )
    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)
    return new_notification

# ── Customer routes ───────────────────────────────────────────
@app.get("/notifications/me", response_model=list[NotificationResponse], tags=["Notifications"])
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    return db.query(models.NotificationTable).filter(
        models.NotificationTable.username == current_user["username"]
    ).order_by(models.NotificationTable.created_at.desc()).all()

@app.put("/notifications/{notification_id}/read", response_model=NotificationResponse, tags=["Notifications"])
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    notification = db.query(models.NotificationTable).filter(
        models.NotificationTable.id == notification_id,
        models.NotificationTable.username == current_user["username"]
    ).first()
    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or does not belong to you"
        )
    if notification.is_read:
        raise HTTPException(
            status_code=400,
            detail="Notification is already marked as read"
        )
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification

@app.delete("/notifications/{notification_id}", tags=["Notifications"])
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer)
):
    notification = db.query(models.NotificationTable).filter(
        models.NotificationTable.id == notification_id,
        models.NotificationTable.username == current_user["username"]
    ).first()
    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found or does not belong to you"
        )
    db.delete(notification)
    db.commit()
    return {"message": f"Notification {notification_id} deleted successfully"}