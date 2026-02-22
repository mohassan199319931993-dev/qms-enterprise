# QMS Authentication & User Management System

A production-ready Authentication & User Management System for an Industrial Quality Management Platform.

## Tech Stack

- **Frontend**: HTML5, CSS3, Vanilla JavaScript, Fetch API
- **Backend**: Python Flask, JWT, bcrypt, SQLAlchemy, Blueprint architecture
- **Database**: PostgreSQL with multi-tenant factory isolation
- **Infrastructure**: Docker, docker-compose, Nginx, Gunicorn

---

## Quick Start (Docker)

```bash
# 1. Clone and navigate
cd QMS-Auth

# 2. Copy environment config
cp .env.example .env
# Edit .env with your secret keys

# 3. Launch all services
docker-compose up -d

# 4. Access the app
open http://localhost:3000
```

---

## Manual Setup

### Database
```bash
createdb qms_db
psql qms_db < database/schema.sql
psql qms_db < database/seed.sql
```

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp ../.env.example .env
# Edit .env

# Run
flask --app app:create_app run --debug
# Or for production:
gunicorn "app:create_app()" --bind 0.0.0.0:5000 --workers 4
```

### Create Demo Admin
```bash
flask --app app:create_app seed-admin
# Creates: admin@qms.com / Admin@123
```

### Frontend
```bash
# Serve frontend folder with any static server
cd frontend
python -m http.server 3000
# Or: npx serve .
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login with email/password |
| POST | `/api/auth/register` | Register user in existing factory |
| POST | `/api/auth/admin-register` | Create factory + admin |
| POST | `/api/auth/refresh` | Rotate refresh token |
| POST | `/api/auth/forgot-password` | Request reset email |
| POST | `/api/auth/reset-password` | Reset with token |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get current user |
| PUT | `/api/users/me` | Update profile / change password |
| GET | `/api/users/` | List factory users |

### Roles
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/roles/` | List factory roles |
| POST | `/api/roles/` | Create role |
| PUT | `/api/roles/<id>` | Update role |
| DELETE | `/api/roles/<id>` | Delete role |
| GET | `/api/roles/permissions` | All permissions |

### Factories
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/factories/` | List factories |
| GET | `/api/factories/mine` | My factory |

---

## User Flow

```
1. Admin → admin-register.html → Creates Factory + Admin account
2. Admin → login.html → Dashboard
3. Admin → roles.html → Create roles, assign permissions
4. Admin → Invite users via register.html
5. Users → login.html → Role-based dashboard
6. Factory data isolated per tenant (factory_id)
```

---

## Security Features

- bcrypt password hashing (12 rounds)
- JWT access tokens (15 min expiry)
- JWT refresh tokens with rotation (7 days)
- Account lockout after 5 failed attempts (15 min)
- Rate limiting on auth endpoints
- Input validation (frontend + backend)
- Audit logging for all auth events
- Multi-tenant isolation via factory_id
- CORS configured for production

---

## Default Roles (auto-created per factory)

| Role | Access |
|------|--------|
| Admin | Full system access |
| Quality Manager | Quality + reports |
| Inspector | Create quality records |
| Viewer | Read-only |

---

## Project Structure

```
QMS-Auth/
├── frontend/
│   ├── login.html
│   ├── register.html
│   ├── admin-register.html
│   ├── forgot-password.html
│   ├── reset-password.html
│   ├── dashboard.html
│   ├── profile.html
│   ├── roles.html
│   ├── css/style.css
│   └── js/
│       ├── api.js       # Central API handler, JWT auto-attach
│       ├── auth.js      # Auth logic
│       ├── guards.js    # Route protection
│       └── utils.js     # Validation, toasts, helpers
├── backend/
│   ├── app.py           # Flask factory
│   ├── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routes/          # Blueprints
│   ├── models/          # SQLAlchemy models
│   ├── services/        # Business logic layer
│   └── middleware/      # Auth, validation
├── database/
│   ├── schema.sql       # PostgreSQL schema
│   └── seed.sql         # Default data
├── docker-compose.yml
├── nginx.conf
└── .env.example
```
