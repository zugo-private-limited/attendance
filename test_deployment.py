#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple deployment test script to verify the application setup.
Run this before deploying to check for common issues.
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def test_imports():
    """Test if all required modules can be imported."""
    print("Testing imports...")
    try:
        import fastapi
        import uvicorn
        import psycopg2
        import jinja2
        print("[OK] All imports successful")
        return True
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    try:
        import config
        print(f"[OK] DB_HOST: {config.DB_HOST}")
        print(f"[OK] DB_PORT: {config.DB_PORT}")
        print(f"[OK] DB_NAME: {config.DB_NAME}")
        print(f"[OK] HR_EMAIL: {config.HR_EMAIL}")
        return True
    except Exception as e:
        print(f"[FAIL] Config error: {e}")
        return False

def test_database_connection():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        import config
        import psycopg2
        
        conn = psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        conn.close()
        print("[OK] Database connection successful")
        return True
    except psycopg2.Error as e:
        print(f"[FAIL] Database connection failed: {e}")
        print("  Make sure PostgreSQL is running and credentials are correct in .env")
        return False
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return False

def test_static_files():
    """Test if static files directory exists."""
    print("\nTesting static files...")
    if os.path.exists("static"):
        print("[OK] Static directory exists")
        return True
    else:
        print("[FAIL] Static directory not found")
        return False

def test_templates():
    """Test if templates directory exists."""
    print("\nTesting templates...")
    if os.path.exists("templates"):
        print("[OK] Templates directory exists")
        return True
    else:
        print("[FAIL] Templates directory not found")
        return False

def test_env_file():
    """Check if .env file exists."""
    print("\nTesting environment file...")
    if os.path.exists(".env"):
        print("[OK] .env file exists")
        return True
    else:
        print("[WARN] .env file not found (copy .env.example to .env)")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("Deployment Test Suite")
    print("=" * 50)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("Database Connection", test_database_connection()))
    results.append(("Static Files", test_static_files()))
    results.append(("Templates", test_templates()))
    results.append(("Environment File", test_env_file()))
    
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Ready for deployment.")
        return 0
    else:
        print("\n[ERROR] Some tests failed. Please fix issues before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

