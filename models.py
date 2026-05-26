from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from db import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=True)
    work_type = Column(String(50), nullable=False, default="Не указано", index=True)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="new", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now(), index=True)

    contacts = relationship("OrderContact", back_populates="order", cascade="all, delete-orphan")


class OrderContact(Base):
    __tablename__ = "order_contacts"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # phone / email
    value = Column(String(255), nullable=False)

    order = relationship("Order", back_populates="contacts")

