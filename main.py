import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Customer, Account, Transaction


app = FastAPI(title="Bank Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers

def to_str_id(doc: dict):
    if not doc:
        return doc
    d = {**doc}
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["_id"] = str(d["_id"])
    return d


@app.get("/")
def read_root():
    return {"message": "Bank Management Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Request models for simple IDs
class CreateCustomerRequest(Customer):
    pass


class CreateAccountRequest(Account):
    pass


class DepositWithdrawRequest(BaseModel):
    amount: float
    note: Optional[str] = None


class TransferRequest(BaseModel):
    from_account_id: str
    to_account_id: str
    amount: float
    note: Optional[str] = None


# Customers
@app.post("/api/customers")
def create_customer(payload: CreateCustomerRequest):
    try:
        customer_id = create_document("customer", payload)
        return {"_id": customer_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/customers")
def list_customers():
    try:
        docs = [to_str_id(d) for d in get_documents("customer")]
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Accounts
@app.post("/api/accounts")
def create_account(payload: CreateAccountRequest):
    # Basic validation: referenced customer must exist
    try:
        cust = db["customer"].find_one({"_id": ObjectId(payload.customer_id)})
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        account_id = create_document("account", payload)
        return {"_id": account_id}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/accounts")
def list_accounts(customer_id: Optional[str] = None):
    try:
        filt = {"customer_id": customer_id} if customer_id else {}
        docs = [to_str_id(d) for d in get_documents("account", filt)]
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Transactions
@app.post("/api/transactions/deposit")
def deposit(account_id: str, payload: DepositWithdrawRequest):
    try:
        acc = db["account"].find_one({"_id": ObjectId(account_id)})
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        new_balance = float(acc.get("balance", 0)) + float(payload.amount)
        db["account"].update_one({"_id": acc["_id"]}, {"$set": {"balance": new_balance}})
        tx = Transaction(
            account_id=str(acc["_id"]),
            tx_type="deposit",
            amount=payload.amount,
            currency=acc.get("currency", "USD"),
            note=payload.note,
        )
        create_document("transaction", tx)
        return {"balance": new_balance}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transactions/withdraw")
def withdraw(account_id: str, payload: DepositWithdrawRequest):
    try:
        acc = db["account"].find_one({"_id": ObjectId(account_id)})
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        current = float(acc.get("balance", 0))
        if payload.amount > current:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        new_balance = current - float(payload.amount)
        db["account"].update_one({"_id": acc["_id"]}, {"$set": {"balance": new_balance}})
        tx = Transaction(
            account_id=str(acc["_id"]),
            tx_type="withdraw",
            amount=payload.amount,
            currency=acc.get("currency", "USD"),
            note=payload.note,
        )
        create_document("transaction", tx)
        return {"balance": new_balance}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transactions/transfer")
def transfer(payload: TransferRequest):
    try:
        from_acc = db["account"].find_one({"_id": ObjectId(payload.from_account_id)})
        to_acc = db["account"].find_one({"_id": ObjectId(payload.to_account_id)})
        if not from_acc or not to_acc:
            raise HTTPException(status_code=404, detail="Source or destination account not found")
        if from_acc.get("currency") != to_acc.get("currency"):
            raise HTTPException(status_code=400, detail="Currency mismatch")
        current = float(from_acc.get("balance", 0))
        if payload.amount > current:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        # Update balances
        db["account"].update_one({"_id": from_acc["_id"]}, {"$set": {"balance": current - payload.amount}})
        db["account"].update_one({"_id": to_acc["_id"]}, {"$set": {"balance": float(to_acc.get("balance", 0)) + payload.amount}})
        # Record transactions
        tx_out = Transaction(
            account_id=str(from_acc["_id"]),
            tx_type="transfer",
            amount=payload.amount,
            currency=from_acc.get("currency", "USD"),
            note=payload.note,
            to_account_id=str(to_acc["_id"]),
        )
        create_document("transaction", tx_out)
        tx_in = Transaction(
            account_id=str(to_acc["_id"]),
            tx_type="deposit",
            amount=payload.amount,
            currency=to_acc.get("currency", "USD"),
            note=f"Transfer from {str(from_acc['_id'])}",
        )
        create_document("transaction", tx_in)
        return {"status": "ok"}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions")
def list_transactions(account_id: Optional[str] = None, limit: int = 50):
    try:
        filt = {"account_id": account_id} if account_id else {}
        docs = [to_str_id(d) for d in get_documents("transaction", filt, limit=limit)]
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
