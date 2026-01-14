from fastapi import FastAPI, HTTPException, status
from sqlalchemy.exc import OperationalError, TimeoutError
from database import get_transaction
from sql_loader import execute_sql
import os
import time
import random

app = FastAPI()

@app.post("/buy_ticket")
def buy_ticket():
    """
    Attempts to buy a ticket for 'Item A' using raw SQL.
    Uses Row-Level Locking (SELECT ... FOR UPDATE) to ensure strict consistency.
    """
    start_time = time.monotonic()
    retry_budget_seconds = float(os.getenv("DB_RETRY_BUDGET_SECONDS", "2.0"))
    attempts = 0
    while True:
        try:
            with get_transaction() as conn:
                result = execute_sql(conn, "get_item_for_update", {"item_id": "Item A"})
                item = result.fetchone()

                if not item:
                    raise HTTPException(status_code=500, detail="Item not found")

                if item.count <= 0:
                    raise HTTPException(status_code=status.HTTP_410_GONE, detail="Sold out")

                purchase_result = execute_sql(conn, "buy_ticket", {"item_id": "Item A"})
                purchase = purchase_result.fetchone()

                if not purchase:
                    raise HTTPException(status_code=500, detail="Purchase failed")

                return {
                    "status": "success",
                    "message": "Ticket purchased",
                    "purchase_id": purchase.purchase_id,
                    "remaining_stock": purchase.remaining_count,
                }

        except HTTPException:
            raise
        except TimeoutError:
            if time.monotonic() - start_time >= retry_budget_seconds:
                raise HTTPException(status_code=500, detail="Database busy, please retry")
            attempts += 1
            time.sleep(min(0.2, 0.01 * (2 ** (attempts - 1))) + random.random() * 0.01)
            continue
        except OperationalError as e:
            if time.monotonic() - start_time >= retry_budget_seconds:
                raise HTTPException(status_code=500, detail="Database busy, please retry")
            attempts += 1
            pgcode = getattr(getattr(e, "orig", None), "pgcode", None)
            if attempts <= 8 and (
                pgcode in {"40P01", "55P03", "40001"} or getattr(e, "connection_invalidated", False)
            ):
                time.sleep(0.01 * (2 ** (attempts - 1)) + random.random() * 0.01)
                continue
            raise HTTPException(status_code=500, detail="Database operational error")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
