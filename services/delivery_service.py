from typing import List
from datetime import date
from sqlalchemy import text
import logging

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import (
    DayNotFoundException,
    DayNotOpenException,
    DeliveryBoyNotFoundException,
    InvalidStockDataException,
)
from app.core.exceptions import BusinessException
from app.models.schema import IOCLMovement, DeliverySale, OfficeSale, TVOutEntry


logger = logging.getLogger(__name__)


class DeliveryService:
    """Handles all delivery and stock transaction operations"""
    
    @staticmethod
    def update_iocl_movements(db: Session, stock_date: date, movements: List[IOCLMovement]) -> dict:
        """
        STEP 3A: Update IOCL receipts and returns
        """
        day = DeliveryService._get_open_day(db, stock_date)
        
        for movement in movements:
            # Validate cylinder type
            cylinder = db.execute(
                text("SELECT id FROM cylinder_types WHERE name = :name AND is_active = TRUE"),
                {"name": movement.cylinder_type}
            ).fetchone()
            
            if not cylinder:
                raise InvalidStockDataException(f"Invalid cylinder type: {movement.cylinder_type}")
            
            # Update IOCL movement
            db.execute(text("""
                UPDATE daily_stock_summary 
                SET item_receipt = :received, item_return = :returned
                WHERE stock_day_id = :day_id AND cylinder_type_id = :cylinder_id
            """), {
                "day_id": day.stock_day_id,
                "cylinder_id": cylinder.id,
                "received": movement.received,
                "returned": movement.returned
            })
        
        db.commit()
        logger.info(f"Updated IOCL movements for {stock_date}")
        
        return {"stock_date": stock_date, "movements_updated": len(movements)}
    
    @staticmethod
    def record_delivery_sales(db: Session, stock_date: date, sales: List[DeliverySale]) -> dict:
        """
        STEP 3B: Record delivery boy sales
        """
        day = DeliveryService._get_open_day(db, stock_date)
        
        records_inserted = 0
        
        for sale in sales:
            # Get delivery boy
            delivery_boy = db.execute(
                text("SELECT id FROM delivery_boys WHERE name = :name AND is_active = TRUE"),
                {"name": sale.delivery_boy_name}
            ).fetchone()
            
            if not delivery_boy:
                raise DeliveryBoyNotFoundException(sale.delivery_boy_name)
            
            # Get cylinder type
            cylinder = db.execute(
                text("SELECT id FROM cylinder_types WHERE name = :name AND is_active = TRUE"),
                {"name": sale.cylinder_type}
            ).fetchone()
            
            if not cylinder:
                raise InvalidStockDataException(f"Invalid cylinder type: {sale.cylinder_type}")
            
            # Insert/Update delivery issue
            db.execute(text("""
                INSERT INTO delivery_issues 
                (stock_day_id, delivery_boy_id, cylinder_type_id, regular_qty, nc_qty, dbc_qty)
                VALUES (:day_id, :boy_id, :cylinder_id, :regular, :nc, :dbc)
                ON DUPLICATE KEY UPDATE
                    regular_qty = :regular,
                    nc_qty = :nc,
                    dbc_qty = :dbc
            """), {
                "day_id": day.stock_day_id,
                "boy_id": delivery_boy.id,
                "cylinder_id": cylinder.id,
                "regular": sale.regular_qty,
                "nc": sale.nc_qty,
                "dbc": sale.dbc_qty
            })
            records_inserted += 1
        
        db.commit()
        logger.info(f"Recorded {records_inserted} delivery sales for {stock_date}")
        
        return {"stock_date": stock_date, "records_inserted": records_inserted}
    
    @staticmethod
    def record_office_sale(db: Session, stock_date: date, sales: List[OfficeSale]) -> dict:
        """
        STEP 3C: Record office NC/sales
        """
        day = DeliveryService._get_open_day(db, stock_date)
        
        # Get office "delivery boy"
        office = db.execute(
            text("SELECT id FROM delivery_boys WHERE name = 'Office'"),
        ).fetchone()
        
        if not office:
            raise BusinessException("Office delivery boy not configured in system")
        
        for sale in sales:
            cylinder = db.execute(
                text("SELECT id FROM cylinder_types WHERE name = :name"),
                {"name": sale.cylinder_type}
            ).fetchone()
            
            if not cylinder:
                raise InvalidStockDataException(f"Invalid cylinder type: {sale.cylinder_type}")
            
            db.execute(text("""
                INSERT INTO delivery_issues 
                (stock_day_id, delivery_boy_id, cylinder_type_id, delivery_source, 
                 regular_qty, nc_qty, dbc_qty)
                VALUES (:day_id, :boy_id, :cylinder_id, 'OFFICE', :regular, :nc, :dbc)
                ON DUPLICATE KEY UPDATE
                    regular_qty = :regular,
                    nc_qty = :nc,
                    dbc_qty = :dbc,
                    delivery_source = 'OFFICE'
            """), {
                "day_id": day.stock_day_id,
                "boy_id": office.id,
                "cylinder_id": cylinder.id,
                "regular": sale.regular_qty,
                "nc": sale.nc_qty,
                "dbc": sale.dbc_qty
            })
        
        db.commit()
        return {"stock_date": stock_date, "office_sales_recorded": len(sales)}
    
    @staticmethod
    def record_tv_out(db: Session, stock_date: date, tv_out_entries: List[TVOutEntry]) -> dict:
        """
        STEP 3D: Record TV-Out (empty returns next day)
        """
        day = DeliveryService._get_open_day(db, stock_date)
        
        for entry in tv_out_entries:
            # Validate cylinder
            cylinder = db.execute(
                text("SELECT id FROM cylinder_types WHERE name = :name"),
                {"name": entry.cylinder_type}
            ).fetchone()
            
            if not cylinder:
                raise InvalidStockDataException(f"Invalid cylinder type: {entry.cylinder_type}")
            
            # Update TV-Out in daily stock summary
            db.execute(text("""
                UPDATE daily_stock_summary 
                SET tv_out_qty = IFNULL(tv_out_qty, 0) + :qty
                WHERE stock_day_id = :day_id AND cylinder_type_id = :cylinder_id
            """), {
                "day_id": day.stock_day_id,
                "cylinder_id": cylinder.id,
                "qty": entry.quantity
            })
            
            # Optional: Track delivery boy for audit
            if entry.delivery_boy_name:
                delivery_boy = db.execute(
                    text("SELECT id FROM delivery_boys WHERE name = :name"),
                    {"name": entry.delivery_boy_name}
                ).fetchone()
                
                if delivery_boy:
                    db.execute(text("""
                        INSERT INTO delivery_vehicle_empty_stock 
                        (stock_day_id, delivery_boy_id, cylinder_type_id, empty_qty)
                        VALUES (:day_id, :boy_id, :cylinder_id, :qty)
                        ON DUPLICATE KEY UPDATE empty_qty = empty_qty + :qty
                    """), {
                        "day_id": day.stock_day_id,
                        "boy_id": delivery_boy.id,
                        "cylinder_id": cylinder.id,
                        "qty": entry.quantity
                    })
        
        db.commit()
        return {"stock_date": stock_date, "tv_out_entries_recorded": len(tv_out_entries)}
    
    @staticmethod
    def _get_open_day(db: Session, stock_date: date):
        """Helper to get open day or raise exception"""
        day = db.execute(
            text("SELECT stock_day_id, status FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        if day.status != 'OPEN':
            raise DayNotOpenException(str(stock_date))
        
        return day