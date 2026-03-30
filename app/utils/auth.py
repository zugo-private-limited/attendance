"""Authentication utilities and dependencies."""
from fastapi import Request, HTTPException
import config

def require_hr(request: Request):
    """Dependency to ensure HR/Admin access"""
    user_email = request.session.get("user_email")
    user_role = request.session.get("user_role", "employee")
    
    # Allow HQ admin and office admin
    if user_role not in ["hq_admin", "office_admin"]:
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    return user_email
