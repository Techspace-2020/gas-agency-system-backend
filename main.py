from sqlalchemy.orm import Session
from app.core.database import get_db 
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from datetime import date, timedelta
from typing import List, Optional
from services.auth_service import(register_admin_service,register_employee_service,employee_login_service,admin_login_service)

from fastapi.middleware.cors import CORSMiddleware
#Base.metadata.create_all(bind=engine)

from app.core.database import engine, get_db
from app.models.schema import (BaseResponse, UserCreate, LoginRequest)
from app.core.config import settings
from app.core.exceptions import BusinessException

# Include API routers
from app.api.stock_days import router as stock_days_router
from app.api.cash import router as cash_router
from app.api.office import router as office_router
from app.core.security import get_current_user,require_role
# from app.api.auth import (
#     register_admin_service,
#     register_employee_service,
#     employee_login_service,admin_login_service
# )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)
# ROUTER INCLUSION
app.include_router(stock_days_router)
app.include_router(cash_router)
app.include_router(office_router)

# =====================================================
# MIDDLEWARE CONFIGURATION
# =====================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Request ID Middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Global Exception Handler
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    logger.warning(f"Business exception: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code if hasattr(exc, 'status_code') else status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred",
        },
    )

# ---------------- HEALTH CHECK ----------------
@app.get("/")
def health_check():
    return {"status": "Gas Agency API is running"}

# ---------------- DATABASE CHECK ----------------
@app.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    return {"message": "Database connected successfully"}

# ---------------- ADMIN REGISTER ----------------
@app.post("/auth/admin/register",
          response_model=BaseResponse,
          tags=["Step - Admin Authentication"],)
def register_admin(data: UserCreate, db: Session = Depends(get_db)):
    result = register_admin_service(data, db)
    return BaseResponse(success=True, message=f"Admin registered successfully with name {data.username}!!")

# ---------------- ADMIN LOGIN ----------------
@app.post("/auth/admin/login",
          response_model=BaseResponse,
          tags=["Step - Admin Authentication"],)
def admin_login(data: LoginRequest, db: Session = Depends(get_db)):
    result = admin_login_service(data, db)
    return BaseResponse(success=True, message="Admin logged in successfully!!")

# ---------------- EMPLOYEE REGISTER ----------------
@app.post("/auth/employee/register",
          response_model=BaseResponse,
          tags=["Step - Employee Authentication"],)
def register_employee(data: UserCreate, db: Session = Depends(get_db)):
    result = register_employee_service(data, db)
    return BaseResponse(success=True, message=f"Employee registered successfully with name {data.username}!!")


# ---------------- EMPLOYEE LOGIN ----------------
@app.post("/auth/employee/login",
          response_model=BaseResponse,
          tags=["Step - Employee Authentication"],)
def employee_login(data: LoginRequest, db: Session = Depends(get_db)):
    result = employee_login_service(data, db)
    return BaseResponse(success=True, message="Employee logged in successfully!!")
