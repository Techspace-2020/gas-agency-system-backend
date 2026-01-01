from datetime import date
from sqlalchemy import text
import logging

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import (
    DayAlreadyExistsException,
    PreviousDayNotClosedException,
    DayNotFoundException,
    DayNotOpenException,
    BusinessException,
)


logger = logging.getLogger(__name__)


class StockDayService:
    """Handles all stock day operations"""
    
    @staticmethod
    def create_stock_day(db: Session, stock_date: date) -> dict:
        """
        STEP 1: Create new working day
        """
        # Check if day already exists
        existing = db.execute(
            text("SELECT stock_day_id FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if existing:
            raise DayAlreadyExistsException(str(stock_date))
        
        # Check if previous day is closed (if exists)
        prev_day = db.execute(
            text("""
                SELECT stock_day_id, status 
                FROM stock_days 
                WHERE stock_date < :date 
                ORDER BY stock_date DESC 
                LIMIT 1
            """),
            {"date": stock_date}
        ).fetchone()
        
        if prev_day and prev_day.status != 'CLOSED':
            raise PreviousDayNotClosedException()
        
        # Create new day
        result = db.execute(
            text("INSERT INTO stock_days (stock_date, status) VALUES (:date, 'OPEN')"),
            {"date": stock_date}
        )
        db.commit()
        
        stock_day_id = result.lastrowid
        
        logger.info(f"Created stock day {stock_day_id} for date {stock_date}")
        
        return {
            "stock_day_id": stock_day_id,
            "stock_date": stock_date,
            "status": "OPEN"
        }
    
    @staticmethod
    def initialize_opening_stock(db: Session, stock_date: date) -> dict:
        """
        STEP 2: Initialize opening stock from previous day
        """
        # Get current day
        curr_day = db.execute(
            text("SELECT stock_day_id, status FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not curr_day:
            raise DayNotFoundException(str(stock_date))
        
        if curr_day.status != 'OPEN':
            raise DayNotOpenException(str(stock_date))
        
        # Get previous day
        prev_day = db.execute(
            text("""
                SELECT stock_day_id 
                FROM stock_days 
                WHERE stock_date < :date AND status = 'CLOSED'
                ORDER BY stock_date DESC 
                LIMIT 1
            """),
            {"date": stock_date}
        ).fetchone()
        
        if prev_day:
            # Copy closing stock as opening
            db.execute(text("""
                INSERT INTO daily_stock_summary (
                    stock_day_id, cylinder_type_id, opening_filled, 
                    opening_empty, defective_empty_vehicle, total_stock
                )
                SELECT
                    :curr_id, prev.cylinder_type_id, prev.closing_filled,
                    prev.closing_empty, prev.defective_empty_vehicle,
                    (prev.closing_filled + prev.closing_empty + prev.defective_empty_vehicle)
                FROM daily_stock_summary prev
                WHERE prev.stock_day_id = :prev_id
            """), {"curr_id": curr_day.stock_day_id, "prev_id": prev_day.stock_day_id})
        else:
            # First day - initialize with zeros
            db.execute(text("""
                INSERT INTO daily_stock_summary (stock_day_id, cylinder_type_id)
                SELECT :stock_day_id, cylinder_type_id 
                FROM cylinder_types 
                WHERE is_active = TRUE
            """), {"stock_day_id": curr_day.stock_day_id})
        
        db.commit()
        
        # Fetch and return opening stock
        stocks = db.execute(text("""
            SELECT 
                ct.name AS cylinder_type,
                dss.opening_filled,
                dss.opening_empty,
                dss.defective_empty_vehicle,
                dss.total_stock
            FROM daily_stock_summary dss
            JOIN cylinder_types ct ON dss.cylinder_type_id = ct.id
            WHERE dss.stock_day_id = :stock_day_id
            ORDER BY ct.display_order
        """), {"stock_day_id": curr_day.stock_day_id})
        
        return {
            "stock_date": stock_date,
            "stocks": [dict(row._mapping) for row in stocks]
        }
    
    @staticmethod
    def close_day(db: Session, stock_date: date) -> dict:
        """
        STEP 8: Close the working day
        """
        day = db.execute(
            text("SELECT stock_day_id, status FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        if day.status == 'CLOSED':
            raise BusinessException(f"Day {stock_date} is already closed")
        
        # Close the day
        db.execute(
            text("""
                UPDATE stock_days 
                SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP 
                WHERE stock_day_id = :id
            """),
            {"id": day.stock_day_id}
        )
        db.commit()
        
        logger.info(f"Closed stock day for date {stock_date}")
        
        return {"stock_date": stock_date, "status": "CLOSED"}