"""
Business Logic for Billing Module
Handles invoicing operations, calculations, and database interactions
"""

from datetime import datetime, date
from typing import Optional, List, Dict
from decimal import Decimal

import psycopg2
import config
from bills_models import Invoice, GSTBill
from data import get_db_conn

# Custom error types for clearer handling
class DuplicateInvoiceNumberError(ValueError):
    pass


# =========================================================================
# INVOICE OPERATIONS
# =========================================================================

def create_invoice(invoice_data: dict, office_id: int = 1) -> Dict:
    """
    Create a new invoice in the database
    
    Args:
        invoice_data: Dictionary with invoice details
        office_id: Office ID for segregation (default: 1 for main HQ)
        
    Returns:
        Dictionary with created invoice details including ID
    """
    conn = get_db_conn()
    try:
        # Prevent duplicate invoice numbers by checking existing records first
        existing = fetch_invoice_by_number(invoice_data.get('invoice_no'), office_id)
        if existing:
            raise DuplicateInvoiceNumberError("Invoice number already exists")

        cursor = conn.cursor()
        query = """
            INSERT INTO invoices 
            (office_id, invoice_no, date, vendor_name, vendor_gstin, vendor_address,
             customer_name, customer_gstin, customer_address, description,
             hsn_code, uom, quantity, rate, cgst, sgst, igst, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        values = (
            office_id,
            invoice_data.get('invoice_no'),
            invoice_data.get('date'),
            invoice_data.get('vendor_name'),
            invoice_data.get('vendor_gstin'),
            invoice_data.get('vendor_address'),
            invoice_data.get('customer_name'),
            invoice_data.get('customer_gstin'),
            invoice_data.get('customer_address'),
            invoice_data.get('description'),
            invoice_data.get('hsn_code'),
            invoice_data.get('uom'),
            invoice_data.get('quantity'),
            invoice_data.get('rate'),
            invoice_data.get('cgst', 0),
            invoice_data.get('sgst', 0),
            invoice_data.get('igst', 0),
            invoice_data.get('status', 'draft'),
            invoice_data.get('notes'),
        )
        try:
            cursor.execute(query, values)
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise DuplicateInvoiceNumberError("Invoice number already exists")

        invoice_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return {'id': invoice_id, **invoice_data}
    finally:
        conn.close()


def fetch_invoice_by_id(invoice_id: int, office_id: int = 1) -> Optional[Dict]:
    """Fetch invoice by ID for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE id = %s AND office_id = %s", (invoice_id, office_id))
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        return dict(zip(columns, row)) if row else None
    finally:
        conn.close()


def fetch_invoice_by_number(invoice_no: str, office_id: int = 1) -> Optional[Dict]:
    """Fetch invoice by invoice number for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE invoice_no = %s AND office_id = %s", (invoice_no, office_id))
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        return dict(zip(columns, row)) if row else None
    finally:
        conn.close()


def fetch_all_invoices(office_id: int = 1, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Fetch all invoices with optional status filter
    
    Args:
        office_id: Office ID to filter by (default: 1)
        status: Filter by status (draft, pending, paid)
        limit: Maximum number of records to fetch
        
    Returns:
        List of invoice dictionaries
    """
    try:
        conn = get_db_conn()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM invoices WHERE office_id = %s AND status = %s ORDER BY date DESC LIMIT %s",
                    (office_id, status, limit)
                )
            else:
                cursor.execute("SELECT * FROM invoices WHERE office_id = %s ORDER BY date DESC LIMIT %s", (office_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in fetch_all_invoices: {e}")
        return []


def update_invoice(invoice_id: int, invoice_data: dict, office_id: int = 1) -> bool:
    """
    Update an existing invoice in the database
    
    Args:
        invoice_id: ID of the invoice to update
        invoice_data: Dictionary with invoice details to update
        office_id: Office ID to verify ownership
        
    Returns:
        True if update was successful, False otherwise
    """
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        query = """
            UPDATE invoices 
            SET invoice_no = %s, date = %s, vendor_name = %s, vendor_gstin = %s, vendor_address = %s,
                customer_name = %s, customer_gstin = %s, customer_address = %s, description = %s,
                hsn_code = %s, uom = %s, quantity = %s, rate = %s, cgst = %s, sgst = %s, igst = %s,
                status = %s, notes = %s, updated_at = NOW()
            WHERE id = %s AND office_id = %s
        """
        values = (
            invoice_data.get('invoice_no'),
            invoice_data.get('date'),
            invoice_data.get('vendor_name'),
            invoice_data.get('vendor_gstin'),
            invoice_data.get('vendor_address'),
            invoice_data.get('customer_name'),
            invoice_data.get('customer_gstin'),
            invoice_data.get('customer_address'),
            invoice_data.get('description'),
            invoice_data.get('hsn_code'),
            invoice_data.get('uom'),
            invoice_data.get('quantity'),
            invoice_data.get('rate'),
            invoice_data.get('cgst', 0),
            invoice_data.get('sgst', 0),
            invoice_data.get('igst', 0),
            invoice_data.get('status', 'draft'),
            invoice_data.get('notes'),
            invoice_id,
            office_id
        )
        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_invoice_status(invoice_id: int, status: str, office_id: int = 1) -> bool:
    """Update invoice status for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE invoices SET status = %s, updated_at = NOW() WHERE id = %s AND office_id = %s",
            (status, invoice_id, office_id)
        )
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_invoice(invoice_id: int, office_id: int = 1) -> bool:
    """Delete invoice by ID for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM invoices WHERE id = %s AND office_id = %s", (invoice_id, office_id))
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    finally:
        conn.close()


# =========================================================================
# GST BILL OPERATIONS
# =========================================================================

def create_gst_bill(bill_data: dict, office_id: int = 1) -> Dict:
    """
    Create a new GST bill in the database
    
    Args:
        bill_data: Dictionary with bill details
        office_id: Office ID for segregation (default: 1 for main HQ)
        
    Returns:
        Dictionary with created bill details including ID
    """
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO gst_bills 
            (office_id, bill_no, date, vendor_name, vendor_gstin, amount, supply_type,
             cgst, sgst, igst, total_with_gst, description, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        # Calculate total with GST
        amount = float(bill_data.get('amount', 0))
        cgst = float(bill_data.get('cgst', 0))
        sgst = float(bill_data.get('sgst', 0))
        igst = float(bill_data.get('igst', 0))
        
        tax_amount = (amount * cgst / 100) + (amount * sgst / 100) + (amount * igst / 100)
        total_with_gst = amount + tax_amount
        
        values = (
            office_id,
            bill_data.get('bill_no'),
            bill_data.get('date'),
            bill_data.get('vendor_name'),
            bill_data.get('vendor_gstin'),
            amount,
            bill_data.get('supply_type', 'intra'),
            cgst,
            sgst,
            igst,
            total_with_gst,
            bill_data.get('description'),
            bill_data.get('status', 'received'),
        )
        cursor.execute(query, values)
        bill_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return {'id': bill_id, **bill_data, 'total_with_gst': total_with_gst}
    finally:
        conn.close()


def fetch_gst_bill_by_id(bill_id: int, office_id: int = 1) -> Optional[Dict]:
    """Fetch GST bill by ID for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gst_bills WHERE id = %s AND office_id = %s", (bill_id, office_id))
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        return dict(zip(columns, row)) if row else None
    finally:
        conn.close()


def fetch_gst_bill_by_number(bill_no: str, office_id: int = 1) -> Optional[Dict]:
    """Fetch GST bill by bill number for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gst_bills WHERE bill_no = %s AND office_id = %s", (bill_no, office_id))
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        cursor.close()
        return dict(zip(columns, row)) if row else None
    finally:
        conn.close()


def fetch_all_gst_bills(office_id: int = 1, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Fetch all GST bills for an office with optional status filter
    
    Args:
        office_id: Office ID to filter by
        status: Filter by status (received, verified, processed)
        limit: Maximum number of records to fetch
        
    Returns:
        List of GST bill dictionaries
    """
    try:
        conn = get_db_conn()
        try:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM gst_bills WHERE office_id = %s AND status = %s ORDER BY date DESC LIMIT %s",
                    (office_id, status, limit)
                )
            else:
                cursor.execute("SELECT * FROM gst_bills WHERE office_id = %s ORDER BY date DESC LIMIT %s", (office_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            cursor.close()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in fetch_all_gst_bills: {e}")
        return []


def update_gst_bill_status(bill_id: int, status: str, office_id: int = 1) -> bool:
    """Update GST bill status for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE gst_bills SET status = %s, updated_at = NOW() WHERE id = %s AND office_id = %s",
            (status, bill_id, office_id)
        )
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_gst_bill(bill_id: int, office_id: int = 1) -> bool:
    """Delete GST bill by ID for specific office"""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gst_bills WHERE id = %s AND office_id = %s", (bill_id, office_id))
        conn.commit()
        cursor.close()
        return cursor.rowcount > 0
    finally:
        conn.close()


# =========================================================================
# REPORTING & ANALYTICS
# =========================================================================

def get_invoice_summary(office_id: int = 1, start_date: date = None, end_date: date = None) -> Dict:
    """
    Get invoice summary for an office for a date range
    
    Args:
        office_id: Office ID to filter by
        start_date: Start date filter
        end_date: End date filter
        
    Returns:
        Dictionary with summary statistics
    """
    try:
        conn = get_db_conn()
        try:
            cursor = conn.cursor()
            
            where_clause = "WHERE office_id = %s"
            params = [office_id]
            
            if start_date:
                where_clause += " AND date >= %s"
                params.append(start_date)
            if end_date:
                where_clause += " AND date <= %s"
                params.append(end_date)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_invoices,
                    SUM(quantity * rate) as total_amount,
                    SUM(cgst * quantity * rate / 100) as total_cgst,
                    SUM(sgst * quantity * rate / 100) as total_sgst,
                    COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_count
                FROM invoices
                {where_clause}
            """
            
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            cursor.close()
            return dict(zip(columns, row)) if row else {}
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_invoice_summary: {e}")
        return {"total_invoices": 0, "total_amount": 0, "total_cgst": 0, "total_sgst": 0, "paid_count": 0}


def get_gst_bill_summary(office_id: int = 1, start_date: date = None, end_date: date = None) -> Dict:
    """
    Get GST bill summary for an office for a date range
    
    Args:
        office_id: Office ID to filter by
        start_date: Start date filter
        end_date: End date filter
        
    Returns:
        Dictionary with summary statistics
    """
    try:
        conn = get_db_conn()
        try:
            cursor = conn.cursor()
            
            where_clause = "WHERE office_id = %s"
            params = [office_id]
            
            if start_date:
                where_clause += " AND date >= %s"
                params.append(start_date)
            if end_date:
                where_clause += " AND date <= %s"
                params.append(end_date)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_bills,
                    SUM(amount) as total_amount,
                    SUM(cgst * amount / 100) as total_cgst,
                    SUM(sgst * amount / 100) as total_sgst,
                    SUM(total_with_gst) as total_with_gst
                FROM gst_bills
                {where_clause}
            """
            
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
            cursor.close()
            return dict(zip(columns, row)) if row else {}
        finally:
            conn.close()
    except Exception as e:
        print(f"Error in get_gst_bill_summary: {e}")
        return {"total_bills": 0, "total_amount": 0, "total_cgst": 0, "total_sgst": 0, "total_with_gst": 0}
