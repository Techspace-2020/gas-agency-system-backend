from datetime import date
from sqlalchemy import text
import logging

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import DayNotFoundException, NegativeStockException


logger = logging.getLogger(__name__)


class StockCalculationService:
    """Handles stock calculations"""
    
    @staticmethod
    def calculate_closing_stock(db: Session, stock_date: date) -> dict:
        """
        STEP 4: Auto-derive closing stock
        """
        day = db.execute(
            text("SELECT stock_day_id, status FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        # Step 4.1: Aggregate sales from delivery issues
        db.execute(text("""
            UPDATE daily_stock_summary dss
            JOIN (
                SELECT
                    stock_day_id,
                    cylinder_type_id,
                    SUM(regular_qty) AS sales_regular,
                    SUM(nc_qty) AS nc_qty,
                    SUM(dbc_qty) AS dbc_qty
                FROM delivery_issues
                WHERE stock_day_id = :day_id
                GROUP BY stock_day_id, cylinder_type_id
            ) di ON di.stock_day_id = dss.stock_day_id
                AND di.cylinder_type_id = dss.cylinder_type_id
            SET
                dss.sales_regular = di.sales_regular,
                dss.nc_qty = di.nc_qty,
                dss.dbc_qty = di.dbc_qty
            WHERE dss.stock_day_id = :day_id
        """), {"day_id": day.stock_day_id})
        
        # Step 4.2: Calculate closing filled
        db.execute(text("""
            UPDATE daily_stock_summary
            SET closing_filled = 
                opening_filled
                + IFNULL(item_receipt, 0)
                - (IFNULL(sales_regular, 0) + IFNULL(nc_qty, 0) + IFNULL(dbc_qty, 0))
            WHERE stock_day_id = :day_id
        """), {"day_id": day.stock_day_id})
        
        # Step 4.3: Calculate closing empty
        db.execute(text("""
            UPDATE daily_stock_summary
            SET closing_empty = 
                opening_empty
                + IFNULL(sales_regular, 0)
                + IFNULL(tv_out_qty, 0)
                - IFNULL(item_return, 0)
            WHERE stock_day_id = :day_id
        """), {"day_id": day.stock_day_id})
        
        # Step 4.4: Calculate total stock
        db.execute(text("""
            UPDATE daily_stock_summary
            SET total_stock = 
                IFNULL(closing_filled, 0)
                + IFNULL(closing_empty, 0)
                + IFNULL(defective_empty_vehicle, 0)
            WHERE stock_day_id = :day_id
        """), {"day_id": day.stock_day_id})
        
        db.commit()
        
        # Validate no negative stock
        negative_stock = db.execute(text("""
            SELECT ct.name
            FROM daily_stock_summary dss
            JOIN cylinder_types ct ON dss.cylinder_type_id = ct.id
            WHERE dss.stock_day_id = :day_id 
            AND (dss.closing_filled < 0 OR dss.closing_empty < 0)
        """), {"day_id": day.stock_day_id}).fetchall()
        
        if negative_stock:
            cylinders = ", ".join([row.name for row in negative_stock])
            raise NegativeStockException(cylinders)
        
        # Fetch result
        stocks = db.execute(text("""
            SELECT
                ct.name AS cylinder_type,
                dss.opening_filled, dss.opening_empty,
                dss.item_receipt, dss.item_return,
                dss.sales_regular, dss.nc_qty, dss.dbc_qty,
                dss.tv_out_qty, dss.closing_filled, dss.closing_empty,
                dss.defective_empty_vehicle, dss.total_stock
            FROM daily_stock_summary dss
            JOIN cylinder_types ct ON dss.cylinder_type_id = ct.id
            WHERE dss.stock_day_id = :day_id
            ORDER BY ct.display_order
        """), {"day_id": day.stock_day_id})
        
        return {
            "stock_date": stock_date,
            "stocks": [dict(row._mapping) for row in stocks]
        }