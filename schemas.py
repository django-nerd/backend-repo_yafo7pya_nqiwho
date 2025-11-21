"""
Database Schemas for Bank Management System

Each Pydantic model maps to a MongoDB collection. Collection name is the
lowercase of the class name.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import datetime


class Customer(BaseModel):
    """
    Customers collection schema
    Collection: "customer"
    """
    full_name: str = Field(..., description="Customer full name")
    email: EmailStr = Field(..., description="Unique email address")
    phone: Optional[str] = Field(None, description="Phone number")
    address: Optional[str] = Field(None, description="Postal address")
    is_active: bool = Field(True, description="Whether the customer is active")


class Account(BaseModel):
    """
    Accounts collection schema
    Collection: "account"
    """
    customer_id: str = Field(..., description="Owner customer _id as string")
    account_type: Literal["checking", "savings"] = Field(
        ..., description="Type of bank account"
    )
    balance: float = Field(0.0, ge=0, description="Current account balance")
    currency: Literal["USD", "EUR", "GBP", "INR", "JPY", "AUD"] = Field(
        "USD", description="Currency code"
    )
    nickname: Optional[str] = Field(None, description="Optional account nickname")


class Transaction(BaseModel):
    """
    Transactions collection schema
    Collection: "transaction"
    """
    account_id: str = Field(..., description="Primary account _id as string")
    tx_type: Literal["deposit", "withdraw", "transfer"]
    amount: float = Field(..., gt=0, description="Transaction amount (positive)")
    currency: str = Field("USD", description="Currency code")
    note: Optional[str] = Field(None, description="Optional memo")
    # For transfers
    to_account_id: Optional[str] = Field(None, description="Destination account _id")
    occurred_at: Optional[datetime] = Field(None, description="When the transaction occurred")
