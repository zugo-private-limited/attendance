"""
Pydantic Schemas for Billing Module
Data validation and serialization schemas
"""

from pydantic import BaseModel, Field
from datetime import date as Date
from typing import Optional
from enum import Enum


class InvoiceStatus(str, Enum):
    """Invoice status options"""
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"


class GSTBillStatus(str, Enum):
    """GST Bill status options"""
    RECEIVED = "received"
    VERIFIED = "verified"
    PROCESSED = "processed"


class SupplyType(str, Enum):
    """GST supply type"""
    INTRA = "intra"
    INTER = "inter"


# =========================================================================
# INVOICE SCHEMAS
# =========================================================================

class InvoiceCreate(BaseModel):
    """Schema for creating an invoice"""
    invoice_no: str = Field(..., min_length=1, max_length=100)
    date: Date
    vendor_name: str = Field(..., min_length=1, max_length=255)
    vendor_gstin: Optional[str] = Field(None, max_length=50)
    vendor_address: Optional[str] = None
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_gstin: Optional[str] = Field(None, max_length=50)
    customer_address: Optional[str] = None
    description: str = Field(..., min_length=1)
    hsn_code: Optional[str] = Field(None, max_length=20)
    uom: Optional[str] = Field(None, max_length=50)
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., gt=0)
    cgst: Optional[float] = Field(0, ge=0, le=100)
    sgst: Optional[float] = Field(0, ge=0, le=100)
    igst: Optional[float] = Field(0, ge=0, le=100)
    status: Optional[InvoiceStatus] = InvoiceStatus.DRAFT
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_no": "INV-2025-001",
                "date": "2025-01-07",
                "vendor_name": "Acme Corp",
                "vendor_gstin": "18AABCT1234H1Z0",
                "customer_name": "XYZ Ltd",
                "description": "Services rendered",
                "quantity": 10,
                "rate": 1000.00,
                "cgst": 9,
                "sgst": 9,
                "status": "draft"
            }
        }


class InvoiceUpdate(BaseModel):
    """Schema for updating an invoice"""
    invoice_no: Optional[str] = None
    date: Optional[Date] = None
    vendor_name: Optional[str] = None
    customer_name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    rate: Optional[float] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Schema for invoice response"""
    id: int
    invoice_no: str
    date: Date
    vendor_name: str
    vendor_gstin: Optional[str] = None
    vendor_address: Optional[str] = None
    customer_name: str
    customer_gstin: Optional[str] = None
    customer_address: Optional[str] = None
    description: str
    hsn_code: Optional[str] = None
    uom: Optional[str] = None
    quantity: float
    rate: float
    cgst: float
    sgst: float
    igst: float
    status: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# =========================================================================
# GST BILL SCHEMAS
# =========================================================================

class GSTBillCreate(BaseModel):
    """Schema for creating a GST bill"""
    bill_no: str = Field(..., min_length=1, max_length=100)
    date: Date
    vendor_name: str = Field(..., min_length=1, max_length=255)
    vendor_gstin: str = Field(..., min_length=1, max_length=50)
    amount: float = Field(..., gt=0)
    supply_type: Optional[SupplyType] = SupplyType.INTRA
    cgst: Optional[float] = Field(0, ge=0, le=100)
    sgst: Optional[float] = Field(0, ge=0, le=100)
    igst: Optional[float] = Field(0, ge=0, le=100)
    description: Optional[str] = None
    status: Optional[GSTBillStatus] = GSTBillStatus.RECEIVED

    class Config:
        json_schema_extra = {
            "example": {
                "bill_no": "BILL-2025-001",
                "date": "2025-01-07",
                "vendor_name": "Vendor Inc",
                "vendor_gstin": "18AABCT1234H1Z0",
                "amount": 50000.00,
                "supply_type": "intra",
                "cgst": 9,
                "sgst": 9,
                "status": "received"
            }
        }


class GSTBillUpdate(BaseModel):
    """Schema for updating a GST bill"""
    bill_no: Optional[str] = None
    date: Optional[Date] = None
    vendor_name: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[GSTBillStatus] = None
    description: Optional[str] = None


class GSTBillResponse(BaseModel):
    """Schema for GST bill response"""
    id: int
    bill_no: str
    date: Date
    vendor_name: str
    vendor_gstin: str
    amount: float
    supply_type: str
    cgst: float
    sgst: float
    igst: float
    total_with_gst: float
    description: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# =========================================================================
# SUMMARY SCHEMAS
# =========================================================================

class InvoiceSummary(BaseModel):
    """Schema for invoice summary"""
    total_invoices: int = 0
    total_amount: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    paid_count: int = 0


class GSTBillSummary(BaseModel):
    """Schema for GST bill summary"""
    total_bills: int = 0
    total_amount: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_with_gst: float = 0.0
