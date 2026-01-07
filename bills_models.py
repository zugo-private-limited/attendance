"""
Database Models for Billing Module
Defines data models for invoices, GST bills, and related entities
"""

from datetime import datetime
from enum import Enum
from typing import Optional
import psycopg2
from psycopg2 import sql
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT


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
# DATABASE SCHEMA INITIALIZATION
# =========================================================================

def initialize_billing_schema():
    """Initialize billing-related database tables"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT,
            database=DB_NAME
        )
        cursor = conn.cursor()

        # Create invoices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                invoice_no VARCHAR(100) UNIQUE NOT NULL,
                date DATE NOT NULL,
                vendor_name VARCHAR(255) NOT NULL,
                vendor_gstin VARCHAR(50),
                vendor_address TEXT,
                customer_name VARCHAR(255) NOT NULL,
                customer_gstin VARCHAR(50),
                customer_address TEXT,
                description TEXT NOT NULL,
                hsn_code VARCHAR(20),
                uom VARCHAR(50),
                quantity NUMERIC(10,2) NOT NULL,
                rate NUMERIC(12,2) NOT NULL,
                cgst NUMERIC(5,2),
                sgst NUMERIC(5,2),
                igst NUMERIC(5,2),
                status VARCHAR(50) DEFAULT 'draft',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create index for invoices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);")

        # Create GST Bills table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gst_bills (
                id SERIAL PRIMARY KEY,
                bill_no VARCHAR(100) UNIQUE NOT NULL,
                date DATE NOT NULL,
                vendor_name VARCHAR(255) NOT NULL,
                vendor_gstin VARCHAR(50) NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                supply_type VARCHAR(20) DEFAULT 'intra',
                cgst NUMERIC(5,2),
                sgst NUMERIC(5,2),
                igst NUMERIC(5,2),
                total_with_gst NUMERIC(12,2) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'received',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create indexes for gst_bills
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gst_bills_bill_no ON gst_bills(bill_no);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gst_bills_date ON gst_bills(date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gst_bills_status ON gst_bills(status);")

        conn.commit()
        cursor.close()
        conn.close()
        print("Billing schema initialization complete (PostgreSQL).")
        return True
    except psycopg2.Error as err:
        print(f"Error during billing schema initialization: {err}")
        return False


# =========================================================================
# DATA MODELS (Python Classes for Data Representation)
# =========================================================================

class Invoice:
    """Represents an Invoice"""
    def __init__(self, invoice_no: str, date, vendor_name: str, customer_name: str,
                 description: str, quantity: float, rate: float, hsn_code: str = None,
                 uom: str = None, cgst: float = 0, sgst: float = 0, igst: float = 0,
                 vendor_gstin: str = None, vendor_address: str = None,
                 customer_gstin: str = None, customer_address: str = None,
                 status: str = "draft", notes: str = None, id: int = None):
        self.id = id
        self.invoice_no = invoice_no
        self.date = date
        self.vendor_name = vendor_name
        self.vendor_gstin = vendor_gstin
        self.vendor_address = vendor_address
        self.customer_name = customer_name
        self.customer_gstin = customer_gstin
        self.customer_address = customer_address
        self.description = description
        self.hsn_code = hsn_code
        self.uom = uom
        self.quantity = quantity
        self.rate = rate
        self.cgst = cgst
        self.sgst = sgst
        self.igst = igst
        self.status = status
        self.notes = notes

    def calculate_subtotal(self) -> float:
        """Calculate subtotal (quantity * rate)"""
        return self.quantity * self.rate

    def calculate_total_tax(self) -> float:
        """Calculate total tax (CGST + SGST + IGST)"""
        subtotal = self.calculate_subtotal()
        cgst_amount = subtotal * (self.cgst / 100) if self.cgst else 0
        sgst_amount = subtotal * (self.sgst / 100) if self.sgst else 0
        igst_amount = subtotal * (self.igst / 100) if self.igst else 0
        return cgst_amount + sgst_amount + igst_amount

    def calculate_total(self) -> float:
        """Calculate grand total (subtotal + taxes)"""
        return self.calculate_subtotal() + self.calculate_total_tax()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'invoice_no': self.invoice_no,
            'date': self.date,
            'vendor_name': self.vendor_name,
            'vendor_gstin': self.vendor_gstin,
            'vendor_address': self.vendor_address,
            'customer_name': self.customer_name,
            'customer_gstin': self.customer_gstin,
            'customer_address': self.customer_address,
            'description': self.description,
            'hsn_code': self.hsn_code,
            'uom': self.uom,
            'quantity': self.quantity,
            'rate': self.rate,
            'cgst': self.cgst,
            'sgst': self.sgst,
            'igst': self.igst,
            'status': self.status,
            'notes': self.notes,
        }


class GSTBill:
    """Represents a GST Bill"""
    def __init__(self, bill_no: str, date, vendor_name: str, vendor_gstin: str,
                 amount: float, supply_type: str = "intra", cgst: float = 0,
                 sgst: float = 0, igst: float = 0, description: str = None,
                 status: str = "received", id: int = None):
        self.id = id
        self.bill_no = bill_no
        self.date = date
        self.vendor_name = vendor_name
        self.vendor_gstin = vendor_gstin
        self.amount = amount
        self.supply_type = supply_type
        self.cgst = cgst
        self.sgst = sgst
        self.igst = igst
        self.description = description
        self.status = status

    def calculate_total_tax(self) -> float:
        """Calculate total tax"""
        cgst_amount = self.amount * (self.cgst / 100) if self.cgst else 0
        sgst_amount = self.amount * (self.sgst / 100) if self.sgst else 0
        igst_amount = self.amount * (self.igst / 100) if self.igst else 0
        return cgst_amount + sgst_amount + igst_amount

    def calculate_total_with_gst(self) -> float:
        """Calculate total with GST"""
        return self.amount + self.calculate_total_tax()

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'bill_no': self.bill_no,
            'date': self.date,
            'vendor_name': self.vendor_name,
            'vendor_gstin': self.vendor_gstin,
            'amount': self.amount,
            'supply_type': self.supply_type,
            'cgst': self.cgst,
            'sgst': self.sgst,
            'igst': self.igst,
            'description': self.description,
            'status': self.status,
        }
