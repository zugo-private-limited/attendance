"""Billing, invoices, and GST bills routes."""
import os
import logging
import psycopg2

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

import config
from data import get_db_connection
from bills_services import (
    create_invoice, fetch_invoice_by_id, fetch_all_invoices, update_invoice, update_invoice_status, delete_invoice,
    create_gst_bill, fetch_gst_bill_by_id, fetch_all_gst_bills, update_gst_bill_status, delete_gst_bill,
    get_invoice_summary, get_gst_bill_summary, DuplicateInvoiceNumberError
)
from app.utils.auth import require_hr

router = APIRouter()

def _get_templates():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
    return Jinja2Templates(directory=TEMPLATES_DIR)

# --- API ENDPOINTS ---

@router.get("/api/invoice/{invoice_id}")
async def api_get_invoice(invoice_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Get invoice details for API"""
    office_id = request.session.get("office_id", 1)
    invoice = fetch_invoice_by_id(invoice_id, office_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.get("/api/gst-bill/{bill_id}")
async def api_get_gst_bill(bill_id: int, hr_email: str = Depends(require_hr)):
    """Get GST bill details for API"""
    bill = fetch_gst_bill_by_id(bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="GST bill not found")
    return bill

# --- INVOICE ENDPOINTS ---

@router.get("/billing", response_class=HTMLResponse, name="billing", summary="Display billing page")
async def get_billing(request: Request, hr_email: str = Depends(require_hr)):
    """Display billing dashboard with invoices and GST bills"""
    templates = _get_templates()
    try:
        user_email = request.session.get("user_email")
        office_id = request.session.get("office_id", 1)
        invoices = fetch_all_invoices(office_id, limit=100)
        bills = fetch_all_gst_bills(limit=100)
        
        invoice_summary = get_invoice_summary()
        bill_summary = get_gst_bill_summary()
        
        return templates.TemplateResponse("billing.html", {
            "request": request,
            "invoices": invoices,
            "bills": bills,
            "invoice_summary": invoice_summary,
            "bill_summary": bill_summary,
            "is_hr": True,
            "user_email": user_email
        })
    except Exception as e:
        print(f"Error in /billing endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Billing page error: {str(e)}")

@router.get("/quotation", response_class=HTMLResponse, summary="Display quotation page")
async def get_quotation(request: Request, hr_email: str = Depends(require_hr)):
    """Display quotation page for creating or viewing quotations"""
    from datetime import date
    templates = _get_templates()
    return templates.TemplateResponse("quotation.html", {
        "request": request,
        "quote_date": date.today().isoformat()
    })

@router.get("/invoices", response_class=HTMLResponse, summary="Display invoices page")
async def get_invoices(request: Request, hr_email: str = Depends(require_hr)):
    """Display all invoices with filtering and search"""
    templates = _get_templates()
    office_id = request.session.get("office_id", 1)
    invoices = fetch_all_invoices(office_id, limit=100)
    summary = get_invoice_summary()
    
    return templates.TemplateResponse("billing.html", {
        "request": request,
        "invoices": invoices,
        "summary": summary,
        "page": "invoices"
    })

@router.get("/invoice/{invoice_id}", response_class=HTMLResponse)
async def get_invoice_detail(invoice_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Get detailed view of a single invoice"""
    templates = _get_templates()
    office_id = request.session.get("office_id", 1)
    invoice = fetch_invoice_by_id(invoice_id, office_id)
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    
    quantity = to_float(invoice.get("quantity"))
    rate = to_float(invoice.get("rate"))
    cgst = to_float(invoice.get("cgst"))
    sgst = to_float(invoice.get("sgst"))
    igst = to_float(invoice.get("igst"))
    
    subtotal = quantity * rate
    taxable_value = subtotal
    cgst_amount = subtotal * cgst / 100
    sgst_amount = subtotal * sgst / 100
    igst_amount = subtotal * igst / 100
    total_tax_amount = cgst_amount + sgst_amount + igst_amount
    total_amount = subtotal + total_tax_amount
    
    grand_total = round(total_amount, 2)
    round_off = round(grand_total - total_amount, 2)

    invoice = {
        **invoice,
        "vendor_address": invoice.get("vendor_address") or "",
        "customer_address": invoice.get("customer_address") or "",
        "vendor_gstin": invoice.get("vendor_gstin") or "",
        "customer_gstin": invoice.get("customer_gstin") or "",
        "hsn_code": invoice.get("hsn_code") or "",
        "uom": invoice.get("uom") or "No",
        "quantity": quantity,
        "rate": rate,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "subtotal": subtotal,
        "taxable_value": taxable_value,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "total_tax_amount": total_tax_amount,
        "total_amount": total_amount,
        "round_off": round_off,
        "grand_total": grand_total,
    }
    
    bank_details = {
        "account_holder": "ZUGO PRIVATE LIMITED",
        "bank_name": "AXIS BANK",
        "account_number": "925020039794750",
        "ifsc_code": "UTIB0002810",
        "branch": "Kumar Nagar"
    }
    
    return templates.TemplateResponse("invoice_view.html", {
        "request": request,
        "invoice": invoice,
        "bank_details": bank_details,
        "taxable_value": taxable_value,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": igst_amount,
        "total_amount": total_amount,
    })

@router.post("/invoice/create")
async def create_new_invoice(
    request: Request,
    invoice_no: str = Form(...),
    invoice_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: Optional[str] = Form(None),
    vendor_address: Optional[str] = Form(None),
    customer_name: str = Form(...),
    customer_gstin: Optional[str] = Form(None),
    customer_address: Optional[str] = Form(None),
    description: str = Form(...),
    hsn_code: Optional[str] = Form(None),
    uom: Optional[str] = Form(None),
    quantity: str = Form(...),
    rate: str = Form(...),
    cgst: Optional[str] = Form("0"),
    sgst: Optional[str] = Form("0"),
    igst: Optional[str] = Form("0"),
    notes: Optional[str] = Form(None),
    hr_email: str = Depends(require_hr)
):
    """Create a new invoice"""
    try:
        office_id = request.session.get("office_id", 1)
        
        def to_float(value: str, default: float = 0.0) -> float:
            if not value or value.strip() == "":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        invoice_data = {
            "invoice_no": invoice_no,
            "date": invoice_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "vendor_address": vendor_address,
            "customer_name": customer_name,
            "customer_gstin": customer_gstin,
            "customer_address": customer_address,
            "description": description,
            "hsn_code": hsn_code,
            "uom": uom,
            "quantity": to_float(quantity, 1.0),
            "rate": to_float(rate, 0.0),
            "cgst": to_float(cgst, 0.0),
            "sgst": to_float(sgst, 0.0),
            "igst": to_float(igst, 0.0),
            "notes": notes,
            "status": "draft"
        }
        
        result = create_invoice(invoice_data, office_id)
        return RedirectResponse(url=f"/invoice/{result['id']}", status_code=303)
    except DuplicateInvoiceNumberError as e:
        logging.warning(f"Duplicate invoice number when creating invoice: {invoice_no}")
        raise HTTPException(status_code=409, detail="Invoice number already exists. Please use a different invoice number.")
    except psycopg2.errors.UniqueViolation:
        logging.warning(f"Duplicate invoice number when creating invoice: {invoice_no}")
        raise HTTPException(status_code=409, detail="Invoice number already exists. Please use a different invoice number.")
    except ValueError as e:
        logging.warning(f"Validation error when creating invoice: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Error creating invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to create invoice. Please try again or contact support.")

@router.post("/invoice/{invoice_id}/update-status")
async def update_invoice_status_endpoint(
    invoice_id: int,
    status: str = Form(...),
    request: Request = None,
    hr_email: str = Depends(require_hr)
):
    """Update invoice status"""
    try:
        office_id = request.session.get("office_id", 1)
        success = update_invoice_status(invoice_id, status, office_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice status updated", "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update invoice: {str(e)}")

@router.post("/delete-invoice/{invoice_id}")
async def delete_invoice_post_endpoint(invoice_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Delete an invoice (POST method for frontend compatibility)"""
    try:
        office_id = request.session.get("office_id", 1)
        success = delete_invoice(invoice_id, office_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"success": True, "message": "Invoice deleted"}
    except Exception as e:
        logging.error(f"Error deleting invoice: {str(e)}", exc_info=True)
        return {"success": False, "message": f"Failed to delete invoice: {str(e)}"}

@router.delete("/invoice/{invoice_id}")
async def delete_invoice_endpoint(invoice_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Delete an invoice"""
    try:
        office_id = request.session.get("office_id", 1)
        success = delete_invoice(invoice_id, office_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"message": "Invoice deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete invoice: {str(e)}")

@router.post("/invoice/{invoice_id}/update")
async def update_invoice_endpoint(
    invoice_id: int,
    request: Request,
    invoice_no: str = Form(...),
    invoice_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: Optional[str] = Form(None),
    vendor_address: Optional[str] = Form(None),
    customer_name: str = Form(...),
    customer_gstin: Optional[str] = Form(None),
    customer_address: Optional[str] = Form(None),
    description: str = Form(...),
    hsn_code: Optional[str] = Form(None),
    uom: Optional[str] = Form(None),
    quantity: str = Form(...),
    rate: str = Form(...),
    cgst: Optional[str] = Form("0"),
    sgst: Optional[str] = Form("0"),
    igst: Optional[str] = Form("0"),
    notes: Optional[str] = Form(None),
    invoice_status: Optional[str] = Form("draft"),
    hr_email: str = Depends(require_hr)
):
    """Update an existing invoice"""
    try:
        office_id = request.session.get("office_id", 1)
        
        def to_float(value: str, default: float = 0.0) -> float:
            if not value or value.strip() == "":
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        invoice_data = {
            "invoice_no": invoice_no,
            "date": invoice_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "vendor_address": vendor_address,
            "customer_name": customer_name,
            "customer_gstin": customer_gstin,
            "customer_address": customer_address,
            "description": description,
            "hsn_code": hsn_code,
            "uom": uom,
            "quantity": to_float(quantity, 1.0),
            "rate": to_float(rate, 0.0),
            "cgst": to_float(cgst, 0.0),
            "sgst": to_float(sgst, 0.0),
            "igst": to_float(igst, 0.0),
            "notes": notes,
            "status": invoice_status or "draft"
        }
        
        success = update_invoice(invoice_id, invoice_data, office_id)
        if not success:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return RedirectResponse(url=f"/invoice/{invoice_id}", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to update invoice: {str(e)}")

# --- GST BILL ENDPOINTS ---

@router.get("/gst-bills", response_class=HTMLResponse, summary="Display GST bills page")
async def get_gst_bills(request: Request, hr_email: str = Depends(require_hr)):
    """Display all GST bills with filtering and search"""
    templates = _get_templates()
    bills = fetch_all_gst_bills(limit=100)
    summary = get_gst_bill_summary()
    
    return templates.TemplateResponse("billing.html", {
        "request": request,
        "bills": bills,
        "summary": summary,
        "page": "gst_bills"
    })

@router.get("/gst-bill/{bill_id}", response_class=HTMLResponse)
async def get_gst_bill_detail(bill_id: int, request: Request, hr_email: str = Depends(require_hr)):
    """Get detailed view of a single GST bill"""
    templates = _get_templates()
    bill = fetch_gst_bill_by_id(bill_id)
    
    if not bill:
        raise HTTPException(status_code=404, detail="GST bill not found")
    
    return templates.TemplateResponse("gst_bill_view.html", {
        "request": request,
        "bill": bill,
    })

@router.post("/gst-bill/create")
async def create_new_gst_bill(
    request: Request,
    bill_no: str = Form(...),
    bill_date: str = Form(...),
    vendor_name: str = Form(...),
    vendor_gstin: str = Form(...),
    amount: float = Form(...),
    supply_type: str = Form("intra"),
    cgst: Optional[float] = Form(0),
    sgst: Optional[float] = Form(0),
    igst: Optional[float] = Form(0),
    description: Optional[str] = Form(None),
    hr_email: str = Depends(require_hr)
):
    """Create a new GST bill"""
    try:
        bill_data = {
            "bill_no": bill_no,
            "date": bill_date,
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "amount": amount,
            "supply_type": supply_type,
            "cgst": cgst or 0,
            "sgst": sgst or 0,
            "igst": igst or 0,
            "description": description,
            "status": "received"
        }
        
        result = create_gst_bill(bill_data)
        return RedirectResponse(url=f"/gst-bill/{result['id']}", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create GST bill: {str(e)}")

@router.post("/gst-bill/{bill_id}/update-status")
async def update_gst_bill_status_endpoint(
    bill_id: int,
    status: str = Form(...),
    request: Request = None,
    hr_email: str = Depends(require_hr)
):
    """Update GST bill status"""
    try:
        success = update_gst_bill_status(bill_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="GST bill not found")
        return {"message": "GST bill status updated", "status": status}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update GST bill: {str(e)}")

@router.delete("/gst-bill/{bill_id}")
async def delete_gst_bill_endpoint(bill_id: int, hr_email: str = Depends(require_hr)):
    """Delete a GST bill"""
    try:
        success = delete_gst_bill(bill_id)
        if not success:
            raise HTTPException(status_code=404, detail="GST bill not found")
        return {"message": "GST bill deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete GST bill: {str(e)}")

@router.get("/summary")
async def get_billing_summary(hr_email: str = Depends(require_hr)):
    """Get billing summary statistics"""
    invoice_summary = get_invoice_summary()
    bill_summary = get_gst_bill_summary()
    
    return {
        "invoices": invoice_summary,
        "gst_bills": bill_summary,
        "total_revenue": (invoice_summary.get('total_amount', 0) or 0),
        "pending_invoices": invoice_summary.get('total_invoices', 0) - invoice_summary.get('paid_count', 0),
        "total_bills": bill_summary.get('total_bills', 0)
    }
