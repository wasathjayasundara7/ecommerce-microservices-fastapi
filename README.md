# E-Commerce Microservices Platform
### IT4020 — Modern Topics in IT | Assignment 2 | Year 4 Semester 2 | 2026

A fully functional e-commerce backend built with **microservices architecture** using Python and FastAPI. The system consists of 5 independent microservices and a custom API Gateway.

---

## Project Structure

```
ecommerce-microservices/
├── api-gateway/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   └── requirements.txt
├── user-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── database.py
│   │   └── auth.py
│   └── requirements.txt
├── product-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── database.py
│   └── requirements.txt
├── order-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── database.py
│   └── requirements.txt
├── payment-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── database.py
│   └── requirements.txt
├── notification-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── database.py
│   └── requirements.txt
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Architecture Overview

```
Client / Postman
      │
      ▼
┌─────────────────────────────┐
│     API Gateway  :8000      │  ← Single entry point
│  JWT validation + routing   │
└──────────────┬──────────────┘
               │
    ┌──────────┼──────────────────────┐
    │          │          │           │           │
    ▼          ▼          ▼           ▼           ▼
User Svc  Product Svc  Order Svc  Payment Svc  Notif. Svc
 :8001      :8002        :8003       :8004        :8005
   │           │            │           │            │
users.db  products.db  orders.db  payments.db  notifications.db
```

### Inter-Service Communication
- **Order Service** → calls **Product Service** to validate product existence, fetch price and check stock
- **Payment Service** → calls **Order Service** to validate order and mark it as paid after payment
- **Payment Service** → calls **Notification Service** to auto-trigger a notification after successful payment

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.11 | Programming language |
| FastAPI | Web framework for all services |
| Uvicorn | ASGI server |
| SQLAlchemy | ORM for database interaction |
| SQLite | Lightweight database (one per service) |
| python-jose | JWT token creation and validation |
| passlib + bcrypt==4.0.1 | Password hashing |
| httpx | Async HTTP client for inter-service calls |
| python-multipart | Form data handling (login forms) |

---

## User Roles

| Role | Capabilities |
|---|---|
| **Customer** | Register, login, browse products, place orders, make payments, view notifications |
| **Admin (Shop Owner)** | Register (requires existing admin + secret key), manage products, manage customers |

---

## Getting Started

### Prerequisites
- Python 3.11 or higher
- pip

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd ecommerce-microservices
```

### 2. Create and activate virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Mac/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install fastapi uvicorn sqlalchemy python-jose[cryptography] passlib[bcrypt] httpx python-multipart
pip install bcrypt==4.0.1
```

### 4. Run all services (6 terminals required)

> All 6 must be running simultaneously. The API Gateway forwards requests to the individual services — it cannot run standalone.

**Terminal 1 — User Service**
```powershell
cd user-service
uvicorn app.main:app --reload --port 8001
```

**Terminal 2 — Product Service**
```powershell
cd product-service
uvicorn app.main:app --reload --port 8002
```

**Terminal 3 — Order Service**
```powershell
cd order-service
uvicorn app.main:app --reload --port 8003
```

**Terminal 4 — Payment Service**
```powershell
cd payment-service
uvicorn app.main:app --reload --port 8004
```

**Terminal 5 — Notification Service**
```powershell
cd notification-service
uvicorn app.main:app --reload --port 8005
```

**Terminal 6 — API Gateway**
```powershell
cd api-gateway
uvicorn app.main:app --reload --port 8000
```

---

## Swagger Documentation

Each service has its own Swagger UI. All services are also accessible via the API Gateway.

| Service | Native Swagger | Via Gateway |
|---|---|---|
| API Gateway | http://localhost:8000/docs | — |
| User Service | http://localhost:8001/docs | http://localhost:8000/users/... |
| Product Service | http://localhost:8002/docs | http://localhost:8000/products/... |
| Order Service | http://localhost:8003/docs | http://localhost:8000/orders/... |
| Payment Service | http://localhost:8004/docs | http://localhost:8000/payments/... |
| Notification Service | http://localhost:8005/docs | http://localhost:8000/notifications/... |

---

## Authentication

This system uses **JWT (JSON Web Token)** authentication.

- Tokens are issued by the **User Service** on successful login
- Tokens carry the user's `username` and `role` (`customer` or `admin`) in the payload
- Tokens expire after **60 minutes**
- The **API Gateway** validates the token before forwarding any protected request
- Each individual service also validates the token independently

### Secret Keys
| Key | Value | Purpose |
|---|---|---|
| JWT Secret | `ecommerce-super-secret-key-2026` | Signing JWT tokens |
| Admin Secret | `admin-secret-2026` | Required when registering a new admin |
| Internal Secret | `internal-service-secret-2026` | Protects the internal notification route |

> In a production environment, all secrets must be stored in environment variables and never hardcoded.

---

## API Reference

### User Service (Port 8001)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/` | No | — | Health check |
| POST | `/register` | No | — | Register a customer |
| POST | `/register/first-admin` | No | — | Create the very first admin (one-time only) |
| POST | `/register/admin` | Yes | Admin | Register a new admin |
| POST | `/login` | No | — | Login and receive JWT token |
| GET | `/users/me` | Yes | Customer | Get own profile |
| PUT | `/users/me` | Yes | Customer | Update own profile |
| GET | `/admin/users` | Yes | Admin | Get all customers |
| GET | `/admin/users/{id}` | Yes | Admin | Get customer by ID |
| PUT | `/admin/users/{id}` | Yes | Admin | Update customer by ID |
| DELETE | `/admin/users/{id}` | Yes | Admin | Delete customer by ID |

### Product Service (Port 8002)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/` | No | — | Health check |
| GET | `/products` | No | Public | Get all active products |
| GET | `/products/{id}` | No | Public | Get product by ID |
| POST | `/products` | Yes | Admin | Create a product |
| PUT | `/products/{id}` | Yes | Admin | Update a product |
| DELETE | `/products/{id}` | Yes | Admin | Delete a product |

### Order Service (Port 8003)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/` | No | — | Health check |
| POST | `/orders` | Yes | Customer | Place an order |
| GET | `/orders` | Yes | Customer | Get own orders |
| GET | `/orders/{id}` | Yes | Customer | Get specific order |
| PUT | `/orders/{id}/cancel` | Yes | Customer | Cancel order (only if pending) |

### Payment Service (Port 8004)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/` | No | — | Health check |
| POST | `/payments` | Yes | Customer | Process a payment |
| GET | `/payments` | Yes | Customer | Get own payments |
| GET | `/payments/{id}` | Yes | Customer | Get specific payment |

### Notification Service (Port 8005)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| GET | `/` | No | — | Health check |
| POST | `/notifications/internal` | Internal secret header | Internal only | Auto-triggered by Payment Service |
| GET | `/notifications/me` | Yes | Customer | Get own notifications |
| PUT | `/notifications/{id}/read` | Yes | Customer | Mark notification as read |
| DELETE | `/notifications/{id}` | Yes | Customer | Delete a notification |

---

## End-to-End Test Flow

Follow these steps to test the complete system via the **API Gateway** at `http://localhost:8000/docs`:

1. **Create first admin** — `POST /users/register/first-admin` with `admin_key=admin-secret-2026`
2. **Register a customer** — `POST /users/register`
3. **Login as admin** — Authorize with admin credentials
4. **Create a product** — `POST /products/products`
5. **Login as customer** — Re-authorize with customer credentials
6. **Place an order** — `POST /orders/orders` with `product_id` and `quantity`
7. **Process payment** — `POST /payments/payments` with `order_id` and `payment_method`
8. **Check notification** — `GET /notifications/notifications/me` — auto-created notification appears
9. **Try to cancel paid order** — `PUT /orders/orders/{id}/cancel` — returns 400 error ✅

---

## Order Status Lifecycle

```
pending ──(payment success)──► paid ──(shipped)──► delivered
   │
   └──(cancel, only if pending)──► cancelled
```

---

## 👨Group Members & Contributions

| Member | Service | Responsibility |
|---|---|---|
| Member 1 | User Service | Authentication, JWT, customer and admin management |
| Member 2 | Product Service | Product catalogue, role-based access control |
| Member 3 | Order Service | Order placement, inter-service calls, order lifecycle |
| Member 4 | Payment Service | Payment processing, auto-trigger notifications, mark order paid |
| Member 5 | Notification Service + API Gateway | Auto notifications, single entry point, routing |
