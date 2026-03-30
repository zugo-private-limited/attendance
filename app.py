"""
Entry point for Zugo Attendance Management System

This module provides backward compatibility by exposing the 
main FastAPI application from the refactored app package.

All application logic is now organized in modular components under the app/ directory.
"""
import os
import uvicorn
from app.main import app

# Re-export for easy access
__all__ = ["app"]

if __name__ == "__main__":
    """Start the FastAPI server when running this file directly."""
    # Detect environment (Render deployment vs local development)
    is_render = os.getenv("RENDER")
    
    if is_render:
        # Production on Render - pass app object directly
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Local development - use import string for reload support
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
