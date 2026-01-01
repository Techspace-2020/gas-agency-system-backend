# OFFICE VALIDATION
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, get_db
from app.models.schema import BaseResponse
from services.office_validation import OfficeService


router = APIRouter()


@router.get(
    "/api/v1/office/pending-stock",
    response_model=BaseResponse,
    tags=["Office Validation"],)
async def get_pending_office_stock(db: Session = Depends(get_db)):
    """
    **Office Pending Stock Validation**
    
    Shows cylinders currently held in office awaiting sale.
    
    - Quantity pending
    - Expected amount when sold
    - Does not affect delivery boy cash
    - Read-only validation
    """
    result = OfficeService.get_pending_office_stock(db)
    return BaseResponse(success=True, message="Office pending stock retrieved", data=result)