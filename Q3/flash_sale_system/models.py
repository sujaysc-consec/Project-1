from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from database import Base

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(String, primary_key=True, index=True)
    count = Column(Integer, nullable=False)


    __table_args__ = (
        CheckConstraint('count >= 0', name='check_inventory_positive'),
    )

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String, ForeignKey("inventory.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
