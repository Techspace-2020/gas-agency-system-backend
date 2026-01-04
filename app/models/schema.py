from ast import pattern
from pydantic import BaseModel, Field, EmailStr,field_validator
from typing import Optional, List,Literal
from datetime import date, datetime
from enum import Enum
from decimal import Decimal

# Enums
class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    OPERATOR = "OPERATOR"
    DELIVERY_BOY = "DELIVERY_BOY"

class EntryType(str, Enum):
    ADDED = "ADDED"
    CLEARED = "CLEARED"

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

# Base Schemas
class ResponseModel(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

# Auth Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_info: dict

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=8)
    mobile: Optional[str] = Field(None, pattern=r"^\d{10,15}$")

class BaseResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None

# ============================================================================
# STEP 1 - CREATE NEW WORKING DAY
# ============================================================================

class CreateStockDayRequest(BaseModel):
    stock_date: date = Field(..., description="Working date (YYYY-MM-DD)")
    
    @field_validator('stock_date')
    @classmethod
    def validate_date(cls, v):
        if v < date(2020, 1, 1):
            raise ValueError('Date must be after 2020-01-01')
        return v

class StockDayResponse(BaseModel):
    stock_day_id: int
    stock_date: date
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None

# ============================================================================
# STEP 2 - OPENING STOCK
# ============================================================================

class OpeningStockItem(BaseModel):
    cylinder_type: str
    opening_filled: int
    opening_empty: int
    defective_empty_vehicle: int
    total_stock: int

class OpeningStockResponse(BaseModel):
    stock_date: date
    stocks: List[OpeningStockItem]

# ============================================================================
# STEP 3 - DELIVERY TRANSACTIONS
# ============================================================================

class IOCLMovement(BaseModel):
    cylinder_type: str = Field(..., description="14.2KG, 19KG, etc.")
    received: int = Field(0, ge=0, description="Cylinders received from IOCL")
    returned: int = Field(0, ge=0, description="Empty cylinders returned to IOCL")

class UpdateIOCLMovementsRequest(BaseModel):
    stock_date: date
    movements: List[IOCLMovement]

class DeliverySale(BaseModel):
    delivery_boy_name: str = Field(..., description="Delivery boy name")
    cylinder_type: str = Field(..., description="14.2KG, 19KG, etc.")
    regular_qty: int = Field(0, ge=0, description="Regular refill quantity")
    nc_qty: int = Field(0, ge=0, description="New connection quantity")
    dbc_qty: int = Field(0, ge=0, description="DBC quantity")
    
    @field_validator('regular_qty', 'nc_qty', 'dbc_qty')
    @classmethod
    def validate_quantities(cls, v):
        if v < 0:
            raise ValueError('Quantity cannot be negative')
        return v

class RecordDeliverySalesRequest(BaseModel):
    stock_date: date
    sales: List[DeliverySale]

class OfficeSale(BaseModel):
    cylinder_type: str
    regular_qty: int = Field(0, ge=0)
    nc_qty: int = Field(0, ge=0)
    dbc_qty: int = Field(0, ge=0)

class RecordOfficeSaleRequest(BaseModel):
    stock_date: date
    sales: List[OfficeSale]

class TVOutEntry(BaseModel):
    delivery_boy_name: str = Field(..., description="Who handled the refund")
    cylinder_type: str
    quantity: int = Field(..., gt=0, description="Empty cylinders returned")
    
class RecordTVOutRequest(BaseModel):
    stock_date: date
    tv_out_entries: List[TVOutEntry]

# ============================================================================
# STEP 4 - STOCK CALCULATION
# ============================================================================

class StockSummaryItem(BaseModel):
    cylinder_type: str
    opening_filled: int
    opening_empty: int
    item_receipt: int
    item_return: int
    sales_regular: int
    nc_qty: int
    dbc_qty: int
    tv_out_qty: int
    closing_filled: int
    closing_empty: int
    defective_empty_vehicle: int
    total_stock: int

class StockSummaryResponse(BaseModel):
    stock_date: date
    stocks: List[StockSummaryItem]

# ============================================================================
# STEP 5 - EXPECTED CASH CALCULATION
# ============================================================================

class DeliveryBoyExpectedCash(BaseModel):
    delivery_boy_name: str
    regular_amount: Decimal
    nc_amount: Decimal
    dbc_amount: Decimal
    tv_out_refund: Decimal
    expected_amount: Decimal

class ExpectedCashResponse(BaseModel):
    stock_date: date
    delivery_boys: List[DeliveryBoyExpectedCash]
    total_expected: Decimal

# ============================================================================
# STEP 6 - CASH DEPOSITS
# ============================================================================

class CashDeposit(BaseModel):
    delivery_boy_name: str
    cash_amount: Decimal = Field(0, ge=0, description="Cash deposited")
    upi_amount: Decimal = Field(0, ge=0, description="UPI deposited")

class RecordCashDepositsRequest(BaseModel):
    stock_date: date
    deposits: List[CashDeposit]

class CashDepositSummary(BaseModel):
    delivery_boy_name: str
    cash_amount: Decimal
    upi_amount: Decimal
    total_deposited: Decimal
    expected_amount: Decimal
    variance: Decimal

class CashDepositResponse(BaseModel):
    stock_date: date
    deposits: List[CashDepositSummary]
    total_cash: Decimal
    total_upi: Decimal
    total_deposited: Decimal

# ============================================================================
# STEP 7 - DELIVERY BOY CASH BALANCE
# ============================================================================

class DeliveryBoyCashBalance(BaseModel):
    delivery_boy_name: str
    opening_balance: Decimal
    today_expected: Decimal
    today_deposited: Decimal
    closing_balance: Decimal
    balance_status: Literal['PENDING', 'SETTLED', 'EXCESS']

class CashBalanceResponse(BaseModel):
    balances: List[DeliveryBoyCashBalance]

# ============================================================================
# STEP 8 - DAY CLOSE
# ============================================================================

class CloseDayRequest(BaseModel):
    stock_date: date

# ============================================================================
# OFFICE VALIDATION
# ============================================================================

class OfficePendingStock(BaseModel):
    cylinder_type: str
    pending_qty: int
    expected_amount: Decimal

class OfficePendingResponse(BaseModel):
    stocks: List[OfficePendingStock]
    total_expected: Decimal
