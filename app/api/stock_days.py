from fastapi import Depends, APIRouter, status
from datetime import date
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.models.schema import (
    BaseResponse,
    CreateStockDayRequest,
    UpdateIOCLMovementsRequest,
    RecordDeliverySalesRequest,
    RecordOfficeSaleRequest,
    RecordTVOutRequest,
)
from services.delivery_service import DeliveryService
from services.stock_calculation import StockCalculationService
from services.stock_service import StockDayService


router = APIRouter()


# STEP 1 - CREATE NEW WORKING DAY
@router.post(
    "/api/v1/stock-days",
    response_model=BaseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Step 1 - Stock Day Management"],)
async def create_stock_day(request: CreateStockDayRequest, db: Session = Depends(get_db)):
    """
    **STEP 1: Create New Working Day**
    
    Creates a new operational day in the system.
    
    - Validates that the previous day is closed
    - Creates new day in OPEN status
    - Returns stock_day_id for subsequent operations
    
    **Business Rules:**
    - Only one OPEN day allowed at a time
    - Previous day must be CLOSED
    - Cannot create duplicate dates
    """
    result = StockDayService.create_stock_day(db, request.stock_date)
    return BaseResponse(success=True, message=f"Stock day created for {request.stock_date}", data=result)

# STEP 2 - INITIALIZE OPENING STOCK
@router.post(
    "/api/v1/stock-days/{stock_date}/initialize",
    response_model=BaseResponse,
    tags=["Step 2 - Opening Stock"],)
async def initialize_opening_stock(stock_date: date, db: Session = Depends(get_db)):
    """
    **STEP 2: Initialize Opening Stock**
    
    Automatically carries forward closing stock from previous day as opening stock.
    
    - Ensures stock continuity
    - No manual entry required
    - Audit-safe tracking
    
    **Formula:**
    Opening Stock (Today) = Closing Stock (Yesterday)
    """
    result = StockDayService.initialize_opening_stock(db, stock_date)
    return BaseResponse(success=True, message=f"Opening stock initialized for {stock_date}", data=result)

# STEP 3A - UPDATE IOCL MOVEMENTS
@router.put(
    "/api/v1/stock-days/iocl-movements",
    response_model=BaseResponse,
    tags=["Step 3 - Delivery Transactions"],)
async def update_iocl_movements(request: UpdateIOCLMovementsRequest, db: Session = Depends(get_db)):
    """
    **STEP 3A: Update IOCL Movements**
    
    Records bulk cylinder movements between IOCL and godown.
    
    - Item Receipt: Cylinders received from IOCL
    - Item Return: Empty cylinders returned to IOCL
    - Not linked to delivery boys
    """
    result = DeliveryService.update_iocl_movements(db, request.stock_date, request.movements)
    return BaseResponse(success=True, message="IOCL movements updated successfully", data=result)

# STEP 3B - RECORD DELIVERY SALES
@router.post(
    "/api/v1/stock-days/delivery-sales",
    response_model=BaseResponse,
    tags=["Step 3 - Delivery Transactions"],)
async def record_delivery_sales(request: RecordDeliverySalesRequest, db: Session = Depends(get_db)):
    """
    **STEP 3B: Record Delivery Boy Sales**
    
    Records sales by each delivery boy including:
    - Regular refills
    - New Connections (NC)
    - DBC (Duplicate Booking Connection)
    
    Sales are captured per delivery boy per cylinder type.
    """
    result = DeliveryService.record_delivery_sales(db, request.stock_date, request.sales)
    return BaseResponse(success=True, message="Delivery sales recorded successfully", data=result)

# STEP 3C - RECORD OFFICE SALE
@router.post(
    "/api/v1/stock-days/office-sales",
    response_model=BaseResponse,
    tags=["Step 3 - Delivery Transactions"],)
async def record_office_sale(request: RecordOfficeSaleRequest, db: Session = Depends(get_db)):
    """
    **STEP 3C: Record Office Sales**
    
    Records cylinders sent to office for later sale.
    
    - Tracked separately from delivery boys
    - Cash collected when actually sold
    - Stock impact immediate
    """
    result = DeliveryService.record_office_sale(db, request.stock_date, request.sales)
    return BaseResponse(success=True, message="Office sales recorded successfully", data=result)

# STEP 3D - RECORD TV OUT
@router.post(
    "/api/v1/stock-days/tv-out",
    response_model=BaseResponse,
    tags=["Step 3 - Delivery Transactions"],)
async def record_tv_out(request: RecordTVOutRequest, db: Session = Depends(get_db)):
    """
    **STEP 3D: Record TV-Out**
    
    TV-Out = Customer returns empty, delivery boy refunds deposit.
    
    **Important:**
    - Recorded on day empty reaches godown (next day)
    - Increases empty stock
    - Reduces expected cash (refund already paid)
    - Does NOT reduce filled stock
    """
    result = DeliveryService.record_tv_out(db, request.stock_date, request.tv_out_entries)
    return BaseResponse(success=True, message="TV-Out entries recorded successfully", data=result)

# STEP 4 - CALCULATE CLOSING STOCK
@router.post(
    "/api/v1/stock-days/{stock_date}/calculate-stock",
    response_model=BaseResponse,
    tags=["Step 4 - Stock Calculation"],)
async def calculate_closing_stock(stock_date: date, db: Session = Depends(get_db)):
    """
    **STEP 4: Auto-Derive Closing Stock**
    
    Consolidates all transactions and calculates:
    - Closing Filled
    - Closing Empty
    - Total Stock
    
    **Formulas:**
    ```
    Closing Filled = Opening Filled + Item Receipt - (Regular + NC + DBC)
    Closing Empty = Opening Empty + Regular Sales + TV-Out - Item Return
    Total = Closing Filled + Closing Empty + Defective
    ```
    
    **Validates:**
    - No negative stock
    - All sales aggregated correctly
    """
    result = StockCalculationService.calculate_closing_stock(db, stock_date)
    return BaseResponse(success=True, message="Closing stock calculated successfully", data=result)

# STEP 8 - CLOSE DAY
@router.post(
    "/api/v1/stock-days/{stock_date}/close",
    response_model=BaseResponse,
    tags=["Step 8 - Day Close"],)
async def close_stock_day(stock_date: date, db: Session = Depends(get_db)):
    """
    **STEP 8: Close Working Day**
    
    Formally closes the day after all transactions are completed.
    
    **Effects:**
    - Changes status from OPEN to CLOSED
    - Prevents further edits
    - Balances carry forward to next day
    
    **Before closing, ensure:**
    - All delivery transactions recorded
    - Stock calculated
    - Cash reconciliation complete
    """
    result = StockDayService.close_day(db, stock_date)
    return BaseResponse(success=True, message=f"Stock day closed for {stock_date}", data=result)