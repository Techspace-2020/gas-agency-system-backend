from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.orm import Session


class OfficeService:
    """Handles office-related validations"""
    
    @staticmethod
    def get_pending_office_stock(db: Session) -> dict:
        """
        Get pending office stock and expected amount
        """
        stocks = db.execute(text("""
            SELECT
                ct.code AS cylinder_type,
                SUM(di.regular_qty + di.nc_qty + di.dbc_qty) AS pending_qty,
                SUM(
                    di.regular_qty * pnc.refill_amount
                    + di.nc_qty *
                    (
                        pnc.deposit_amount
                        + pnc.refill_amount
                        + pnc.document_charge
                        + pnc.installation_charge
                        + CASE
                            WHEN ct.category = 'DOMESTIC' THEN pnc.regulator_charge
                            ELSE 0
                        END
                    )
                    + di.dbc_qty *
                    (
                        pnc.deposit_amount
                        + pnc.refill_amount
                        + pnc.document_charge
                        + pnc.installation_charge
                    )
                ) AS expected_amount
            FROM delivery_issues di
            JOIN cylinder_types ct ON di.cylinder_type_id = ct.cylinder_type_id
            JOIN price_nc_components pnc ON di.cylinder_type_id = pnc.cylinder_type_id
            WHERE di.delivery_source = 'OFFICE'
            GROUP BY ct.code
            ORDER BY ct.code
        """))
        
        stock_list = [dict(row._mapping) for row in stocks]
        total = sum(Decimal(str(item['expected_amount'])) for item in stock_list)
        
        return {
            "stocks": stock_list,
            "total_expected": total
        }