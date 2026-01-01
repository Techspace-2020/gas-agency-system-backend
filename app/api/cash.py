from fastapi import Depends, APIRouter
from datetime import date
from app.models.schema import (
    BaseResponse,
    ExpectedCashResponse,
    RecordCashDepositsRequest,
)
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, get_db
from services.cash_service import CashService


router = APIRouter()


# STEP 5 - CALCULATE EXPECTED CASH
@router.post(
    "/api/v1/stock-days/{stock_date}/calculate-expected-cash",
    response_model=BaseResponse,
    tags=["Step 5 - Cash Management"],)
async def calculate_expected_cash(
    stock_date: date,
    db: Session = Depends(get_db)):
    """
    **STEP 5: Calculate Expected Cash**
    
    Calculates expected cash deposit from each delivery boy.
    
    **Formula:**
    ```
    Expected Cash = (Regular Amount + NC Amount + DBC Amount) - TV-Out Refund
    ```
    
    **Pricing:**
    - Regular: Refill amount only
    - NC: Deposit + Refill + Document + Installation + Regulator (domestic)
    - DBC: Deposit + Refill + Document + Installation
    - TV-Out Refund: Deposit amount (deducted)
    """
    result = CashService.calculate_expected_cash(db, stock_date)
    return BaseResponse(success=True, message="Expected cash calculated successfully", data=result)

# STEP 6 - RECORD CASH DEPOSITS
@router.post(
    "/api/v1/stock-days/cash-deposits",
    response_model=BaseResponse,
    tags=["Step 6 - Cash Deposits"],)
async def record_cash_deposits(
    request: RecordCashDepositsRequest,
    db: Session = Depends(get_db)):
    """
    **STEP 6: Record Cash Deposits**
    
    Records actual cash/UPI deposits from delivery boys.
    
    - Can be full, partial, or no deposit
    - Supports both cash and UPI
    - Calculates variance (deposited vs expected)
    
    **No deposit = No entry required**
    """
    result = CashService.record_cash_deposits(db, request.stock_date, request.deposits)
    return BaseResponse(success=True, message="Cash deposits recorded successfully", data=result)

# STEP 7 - UPDATE DELIVERY BOY BALANCES
@router.post(
    "/api/v1/stock-days/{stock_date}/update-balances",
    response_model=BaseResponse,
    tags=["Step 7 - Cash Balance Update"],)
async def update_delivery_boy_balances(
    stock_date: date,
    db: Session = Depends(get_db)):
    """
    **STEP 7: Update Delivery Boy Cash Balances**
    
    Updates running cash balance for each delivery boy.
    
    **Process:**
    1. Freeze opening balance
    2. Update today's expected
    3. Update today's deposited
    4. Calculate closing balance
    5. Update status (PENDING/SETTLED/EXCESS)
    
    **Formula:**
    ```
    Closing Balance = Opening Balance + Today Expected - Today Deposited
    ```
    """
    result = CashService.update_delivery_boy_balances(db, stock_date)
    return BaseResponse(success=True, message="Delivery boy balances updated successfully", data=result)