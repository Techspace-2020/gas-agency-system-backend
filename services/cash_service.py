from typing import List
from datetime import date
from decimal import Decimal
from sqlalchemy import text
import logging

from sqlalchemy.orm import Session
from app.core.exceptions import DayNotFoundException, DeliveryBoyNotFoundException
from app.models.schema import CashDeposit


logger = logging.getLogger(__name__)


class CashService:
    """Handles all cash-related operations"""
    
    @staticmethod
    def calculate_expected_cash(db: Session, stock_date: date) -> dict:
        """
        STEP 5: Calculate expected cash from delivery boys
        """
        day = db.execute(
            text("SELECT stock_day_id FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        # Calculate and insert expected amounts
        db.execute(text("""
            INSERT INTO delivery_expected_amount
            (stock_day_id, delivery_boy_id, expected_amount)
            SELECT
                s.stock_day_id,
                s.delivery_boy_id,
                (
                    s.regular_amount
                    + s.nc_amount
                    + s.dbc_amount
                    - IFNULL(t.tv_out_refund_amount, 0)
                ) AS expected_amount
            FROM
            (
                SELECT
                    di.stock_day_id,
                    di.delivery_boy_id,
                    SUM(di.regular_qty * pnc.refill_amount) AS regular_amount,
                    SUM(
                        di.nc_qty *
                        (
                            pnc.deposit_amount
                            + pnc.refill_amount
                            + pnc.document_charge
                            + pnc.installation_charge
                            + CASE
                                WHEN ct.category = 'DOMESTIC'
                                THEN pnc.regulator_charge
                                ELSE 0
                            END
                        )
                    ) AS nc_amount,
                    SUM(
                        di.dbc_qty *
                        (
                            pnc.deposit_amount
                            + pnc.refill_amount
                            + pnc.document_charge
                            + pnc.installation_charge
                        )
                    ) AS dbc_amount
                FROM delivery_issues di
                JOIN cylinder_types ct ON di.cylinder_type_id = ct.cylinder_type_id
                JOIN price_nc_components pnc ON di.cylinder_type_id = pnc.cylinder_type_id
                WHERE di.stock_day_id = :day_id
                AND di.delivery_source != 'OFFICE'
                GROUP BY di.stock_day_id, di.delivery_boy_id
            ) s
            LEFT JOIN
            (
                SELECT
                    dss.stock_day_id,
                    db.delivery_boy_id AS delivery_boy_id,
                    SUM(dss.tv_out_qty * pnc.deposit_amount) AS tv_out_refund_amount
                FROM daily_stock_summary dss
                JOIN price_nc_components pnc ON dss.cylinder_type_id = pnc.cylinder_type_id
                JOIN delivery_boys db ON db.is_active = TRUE
                WHERE dss.stock_day_id = :day_id
                AND dss.tv_out_qty > 0
                GROUP BY delivery_boy_id
            ) t ON s.stock_day_id = t.stock_day_id
                AND s.delivery_boy_id = t.delivery_boy_id
            ON DUPLICATE KEY UPDATE
                expected_amount = VALUES(expected_amount)
        """), {"day_id": day.stock_day_id})
        
        db.commit()
        
        # Fetch results
        results = db.execute(text("""
            SELECT
                db.name AS delivery_boy_name,
                dea.expected_amount
            FROM delivery_expected_amount dea
            JOIN delivery_boys db ON dea.delivery_boy_id = db.delivery_boy_id
            WHERE dea.stock_day_id = :day_id
            ORDER BY db.name
        """), {"day_id": day.stock_day_id})
        
        expected_list = [dict(row._mapping) for row in results]
        total = sum(Decimal(str(item['expected_amount'])) for item in expected_list)
        
        return {
            "stock_date": stock_date,
            "delivery_boys": expected_list,
            "total_expected": total
        }
    
    @staticmethod
    def record_cash_deposits(db: Session, stock_date: date, deposits: List[CashDeposit]) -> dict:
        """
        STEP 6: Record cash deposits from delivery boys
        """
        day = db.execute(
            text("SELECT stock_day_id FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        for deposit in deposits:
            # Get delivery boy
            delivery_boy = db.execute(
                text("SELECT delivery_boy_id FROM delivery_boys WHERE name = :name"),
                {"name": deposit.delivery_boy_name}
            ).fetchone()
            
            if not delivery_boy:
                raise DeliveryBoyNotFoundException(deposit.delivery_boy_name)
            
            # Insert deposit
            db.execute(text("""
                INSERT INTO delivery_cash_deposit
                (stock_day_id, delivery_boy_id, cash_amount, upi_amount)
                VALUES (:day_id, :boy_id, :cash, :upi)
                ON DUPLICATE KEY UPDATE
                    cash_amount = :cash,
                    upi_amount = :upi,
                    total_deposited = :cash + :upi
            """), {
                "day_id": day.stock_day_id,
                "boy_id": delivery_boy.delivery_boy_id,
                "cash": deposit.cash_amount,
                "upi": deposit.upi_amount
            })
        
        db.commit()
        
        # Fetch summary with variance
        summary = db.execute(text("""
            SELECT
                db.name AS delivery_boy_name,
                dcd.cash_amount,
                dcd.upi_amount,
                dcd.total_deposited,
                IFNULL(dea.expected_amount, 0) AS expected_amount,
                (dcd.total_deposited - IFNULL(dea.expected_amount, 0)) AS variance
            FROM delivery_cash_deposit dcd
            JOIN delivery_boys db ON dcd.delivery_boy_id = db.id
            LEFT JOIN delivery_expected_amount dea 
                ON dea.delivery_boy_id = dcd.delivery_boy_id
                AND dea.stock_day_id = dcd.stock_day_id
            WHERE dcd.stock_day_id = :day_id
            ORDER BY db.name
        """), {"day_id": day.stock_day_id})
        
        deposit_list = [dict(row._mapping) for row in summary]
        
        totals = db.execute(text("""
            SELECT
                SUM(cash_amount) AS total_cash,
                SUM(upi_amount) AS total_upi,
                SUM(total_deposited) AS total_deposited
            FROM delivery_cash_deposit
            WHERE stock_day_id = :day_id
        """), {"day_id": day.stock_day_id}).fetchone()
        
        return {
            "stock_date": stock_date,
            "deposits": deposit_list,
            "total_cash": totals.total_cash or 0,
            "total_upi": totals.total_upi or 0,
            "total_deposited": totals.total_deposited or 0,
        }
    
    @staticmethod
    def update_delivery_boy_balances(db: Session, stock_date: date) -> dict:
        """
        STEP 7: Update delivery boy cash balances
        """
        day = db.execute(
            text("SELECT stock_day_id FROM stock_days WHERE stock_date = :date"),
            {"date": stock_date}
        ).fetchone()
        
        if not day:
            raise DayNotFoundException(str(stock_date))
        
        # Step 7.1: Freeze opening balance
        db.execute(text("""
            UPDATE delivery_cash_balance
            SET opening_balance = closing_balance
        """))
        
        # Step 7.2: Update today's expected
        db.execute(text("""
            UPDATE delivery_cash_balance dcb
            LEFT JOIN delivery_expected_amount dea
                ON dea.delivery_boy_id = dcb.delivery_boy_id
                AND dea.stock_day_id = :day_id
            SET dcb.today_expected = IFNULL(dea.expected_amount, 0)
        """), {"day_id": day.stock_day_id})
        
        # Step 7.3: Update today's deposited
        db.execute(text("""
            UPDATE delivery_cash_balance dcb
            LEFT JOIN (
                SELECT
                    delivery_boy_id,
                    SUM(total_deposited) AS deposited_today
                FROM delivery_cash_deposit
                WHERE stock_day_id = :day_id
                GROUP BY delivery_boy_id
            ) dep ON dep.delivery_boy_id = dcb.delivery_boy_id
            SET dcb.today_deposited = IFNULL(dep.deposited_today, 0)
        """), {"day_id": day.stock_day_id})
        
        # Step 7.4: Calculate closing balance
        db.execute(text("""
            UPDATE delivery_cash_balance
            SET
                closing_balance = opening_balance + today_expected - today_deposited,
                last_updated = CURRENT_TIMESTAMP
        """))
        
        # Step 7.5: Update balance status
        db.execute(text("""
            UPDATE delivery_cash_balance
            SET balance_status =
                CASE
                    WHEN closing_balance = 0 THEN 'SETTLED'
                    WHEN closing_balance > 0 THEN 'PENDING'
                    ELSE 'EXCESS'
                END
        """))
        
        db.commit()
        
        # Fetch balances
        balances = db.execute(text("""
            SELECT
                db.name AS delivery_boy_name,
                dcb.opening_balance,
                dcb.today_expected,
                dcb.today_deposited,
                dcb.closing_balance,
                dcb.balance_status
            FROM delivery_cash_balance dcb
            JOIN delivery_boys db ON dcb.delivery_boy_id = db.id
            ORDER BY db.name
        """))
        
        return {
            "balances": [dict(row._mapping) for row in balances]
        }