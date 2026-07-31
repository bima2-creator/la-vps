#!/usr/bin/env python3
"""
LA Tracker Backend API Test Suite - SPK Upload Feature
Tests SPK upload with kind=spk, PDF-only validation, single SPK rule, and replacement after delete.
"""

import io
import sys
import time
import requests
from typing import Optional, Dict, Any

# Backend URL from environment
BASE_URL = "https://project-bootstrap-18.preview.emergentagent.com/api"

# Test credentials (username-based auth)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Global token storage
TOKEN: Optional[str] = None

# Test data IDs
TEST_WO_ID: Optional[str] = None
TEST_SPK_ID: Optional[str] = None
TEST_GENERAL_ID: Optional[str] = None

# Unique suffix for this test run
TEST_RUN_ID = str(int(time.time()))


def log(msg: str, level: str = "INFO"):
    """Print formatted log message."""
    print(f"[{level}] {msg}")


def create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF for testing."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, "Test SPK Document")
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    except ImportError:
        # Fallback to minimal PDF if reportlab not available
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"


def create_fake_png() -> bytes:
    """Create fake PNG bytes for testing rejection."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


def test_login() -> bool:
    """Test 1: Login as admin with username-based auth"""
    global TOKEN
    log("=" * 80)
    log("TEST 1: Login as admin (username-based)")
    log("=" * 80)
    
    try:
        log(f"Attempting login with username={ADMIN_USERNAME}...")
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Login failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        if "token" not in data:
            log(f"❌ Login response missing 'token' field: {data}", "ERROR")
            return False
        
        TOKEN = data["token"]
        log(f"✅ Login successful, token received")
        log(f"   Username: {data.get('username')}")
        log(f"   Role: {data.get('role')}")
        log(f"   Email: {data.get('email')}")
        
        return True
        
    except Exception as e:
        log(f"❌ Login test failed with exception: {e}", "ERROR")
        return False


def test_create_work_order() -> bool:
    """Test 2: Create a work order for SPK testing"""
    global TEST_WO_ID
    log("=" * 80)
    log("TEST 2: Create Work Order")
    log("=" * 80)
    
    try:
        payload = {
            "pelanggan": f"SPK TEST WO",
            "jenis_order": "PSB"
        }
        
        log(f"Creating work order: {payload}")
        resp = requests.post(
            f"{BASE_URL}/workorders",
            json=payload,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Create work order failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        TEST_WO_ID = data.get("id")
        
        if not TEST_WO_ID:
            log(f"❌ Work order response missing 'id' field: {data}", "ERROR")
            return False
        
        log(f"✅ Work order created successfully")
        log(f"   ID: {TEST_WO_ID}")
        log(f"   Pelanggan: {data.get('pelanggan')}")
        log(f"   Jenis Order: {data.get('jenis_order')}")
        
        return True
        
    except Exception as e:
        log(f"❌ Create work order test failed with exception: {e}", "ERROR")
        return False


def test_upload_spk_pdf() -> bool:
    """Test 3: Upload SPK PDF with kind=spk (expect 200)"""
    global TEST_SPK_ID
    log("=" * 80)
    log("TEST 3: Upload SPK PDF with kind=spk")
    log("=" * 80)
    
    try:
        pdf_bytes = create_minimal_pdf()
        log(f"Created PDF: {len(pdf_bytes)} bytes, starts with: {pdf_bytes[:10]}")
        
        files = {
            "file": ("spk_document.pdf", pdf_bytes, "application/pdf")
        }
        data = {
            "kind": "spk"
        }
        
        log(f"Uploading SPK PDF to /workorders/{TEST_WO_ID}/attachments with kind=spk...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Upload SPK PDF failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        result = resp.json()
        TEST_SPK_ID = result.get("id")
        
        if result.get("kind") != "spk":
            log(f"❌ Expected kind='spk', got kind='{result.get('kind')}'", "ERROR")
            return False
        
        log(f"✅ SPK PDF uploaded successfully")
        log(f"   ID: {TEST_SPK_ID}")
        log(f"   Kind: {result.get('kind')}")
        log(f"   Filename: {result.get('original_filename')}")
        log(f"   Content-Type: {result.get('content_type')}")
        log(f"   Size: {result.get('size')} bytes")
        
        return True
        
    except Exception as e:
        log(f"❌ Upload SPK PDF test failed with exception: {e}", "ERROR")
        return False


def test_reject_non_pdf() -> bool:
    """Test 4: Reject non-PDF file with kind=spk (expect 400)"""
    log("=" * 80)
    log("TEST 4: Reject non-PDF with kind=spk")
    log("=" * 80)
    
    try:
        png_bytes = create_fake_png()
        log(f"Created PNG: {len(png_bytes)} bytes")
        
        files = {
            "file": ("test.png", png_bytes, "image/png")
        }
        data = {
            "kind": "spk"
        }
        
        log(f"Attempting to upload PNG with kind=spk (should be rejected)...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected status 400, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        error_detail = resp.json().get("detail", "")
        expected_msg = "Hanya file PDF yang diperbolehkan"
        
        if expected_msg not in error_detail:
            log(f"❌ Expected error message '{expected_msg}', got '{error_detail}'", "ERROR")
            return False
        
        log(f"✅ Non-PDF correctly rejected with HTTP 400")
        log(f"   Error message: {error_detail}")
        
        return True
        
    except Exception as e:
        log(f"❌ Reject non-PDF test failed with exception: {e}", "ERROR")
        return False


def test_list_attachments() -> bool:
    """Test 5: List attachments and verify kind=='spk'"""
    log("=" * 80)
    log("TEST 5: List attachments and verify kind")
    log("=" * 80)
    
    try:
        log(f"Getting attachments for work order {TEST_WO_ID}...")
        resp = requests.get(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ List attachments failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        attachments = resp.json()
        
        if not isinstance(attachments, list):
            log(f"❌ Expected list response, got {type(attachments)}", "ERROR")
            return False
        
        spk_attachments = [a for a in attachments if a.get("kind") == "spk"]
        
        if len(spk_attachments) != 1:
            log(f"❌ Expected 1 SPK attachment, found {len(spk_attachments)}", "ERROR")
            return False
        
        spk = spk_attachments[0]
        log(f"✅ Attachments listed successfully")
        log(f"   Total attachments: {len(attachments)}")
        log(f"   SPK attachment found:")
        log(f"     - ID: {spk.get('id')}")
        log(f"     - Kind: {spk.get('kind')}")
        log(f"     - Filename: {spk.get('original_filename')}")
        
        return True
        
    except Exception as e:
        log(f"❌ List attachments test failed with exception: {e}", "ERROR")
        return False


def test_default_kind() -> bool:
    """Test 6: Upload PDF without kind field (expect default kind=='general')"""
    global TEST_GENERAL_ID
    log("=" * 80)
    log("TEST 6: Upload PDF without kind field (default to 'general')")
    log("=" * 80)
    
    try:
        pdf_bytes = create_minimal_pdf()
        
        files = {
            "file": ("general_document.pdf", pdf_bytes, "application/pdf")
        }
        # No kind field in data
        
        log(f"Uploading PDF without kind field...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Upload PDF failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        result = resp.json()
        TEST_GENERAL_ID = result.get("id")
        
        if result.get("kind") != "general":
            log(f"❌ Expected kind='general', got kind='{result.get('kind')}'", "ERROR")
            return False
        
        log(f"✅ PDF uploaded successfully with default kind")
        log(f"   ID: {TEST_GENERAL_ID}")
        log(f"   Kind: {result.get('kind')}")
        log(f"   Filename: {result.get('original_filename')}")
        
        return True
        
    except Exception as e:
        log(f"❌ Default kind test failed with exception: {e}", "ERROR")
        return False


def test_single_spk_rule() -> bool:
    """Test 7: SINGLE SPK RULE - attempt to upload 2nd SPK (expect 400)"""
    log("=" * 80)
    log("TEST 7: SINGLE SPK RULE - Reject 2nd SPK upload")
    log("=" * 80)
    
    try:
        pdf_bytes = create_minimal_pdf()
        
        files = {
            "file": ("second_spk.pdf", pdf_bytes, "application/pdf")
        }
        data = {
            "kind": "spk"
        }
        
        log(f"Attempting to upload 2nd SPK (should be rejected)...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected status 400, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        error_detail = resp.json().get("detail", "")
        expected_msg = "SPK sudah ada. Hapus file SPK yang lama sebelum upload baru."
        
        if expected_msg not in error_detail:
            log(f"❌ Expected error message '{expected_msg}', got '{error_detail}'", "ERROR")
            return False
        
        log(f"✅ 2nd SPK correctly rejected with HTTP 400")
        log(f"   Error message: {error_detail}")
        
        return True
        
    except Exception as e:
        log(f"❌ Single SPK rule test failed with exception: {e}", "ERROR")
        return False


def test_replacement_after_delete() -> bool:
    """Test 8: Delete existing SPK, then upload new SPK (expect 200)"""
    log("=" * 80)
    log("TEST 8: Replacement after delete - Delete SPK then upload new one")
    log("=" * 80)
    
    try:
        # Step 1: Delete existing SPK
        log(f"Deleting existing SPK attachment {TEST_SPK_ID}...")
        resp = requests.delete(
            f"{BASE_URL}/attachments/{TEST_SPK_ID}",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Delete SPK failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        log(f"✅ Existing SPK deleted successfully")
        
        # Step 2: Upload new SPK
        pdf_bytes = create_minimal_pdf()
        
        files = {
            "file": ("new_spk.pdf", pdf_bytes, "application/pdf")
        }
        data = {
            "kind": "spk"
        }
        
        log(f"Uploading new SPK after delete...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Upload new SPK failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        result = resp.json()
        
        if result.get("kind") != "spk":
            log(f"❌ Expected kind='spk', got kind='{result.get('kind')}'", "ERROR")
            return False
        
        log(f"✅ New SPK uploaded successfully after delete")
        log(f"   ID: {result.get('id')}")
        log(f"   Kind: {result.get('kind')}")
        log(f"   Filename: {result.get('original_filename')}")
        
        return True
        
    except Exception as e:
        log(f"❌ Replacement after delete test failed with exception: {e}", "ERROR")
        return False


def test_cleanup() -> bool:
    """Test 9: Cleanup - Delete work order"""
    log("=" * 80)
    log("TEST 9: Cleanup - Delete work order")
    log("=" * 80)
    
    try:
        log(f"Deleting work order {TEST_WO_ID}...")
        resp = requests.delete(
            f"{BASE_URL}/workorders/{TEST_WO_ID}",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Delete work order failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        log(f"✅ Work order deleted successfully")
        
        return True
        
    except Exception as e:
        log(f"❌ Cleanup test failed with exception: {e}", "ERROR")
        return False


def main():
    """Run all SPK upload tests"""
    log("=" * 80)
    log("LA TRACKER - SPK UPLOAD FEATURE TEST SUITE")
    log("=" * 80)
    log(f"Base URL: {BASE_URL}")
    log(f"Test Run ID: {TEST_RUN_ID}")
    log("")
    
    tests = [
        ("Login as admin", test_login),
        ("Create work order", test_create_work_order),
        ("Upload SPK PDF with kind=spk", test_upload_spk_pdf),
        ("Reject non-PDF with kind=spk", test_reject_non_pdf),
        ("List attachments and verify kind", test_list_attachments),
        ("Upload PDF without kind (default to general)", test_default_kind),
        ("SINGLE SPK RULE - Reject 2nd SPK", test_single_spk_rule),
        ("Replacement after delete", test_replacement_after_delete),
        ("Cleanup", test_cleanup),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
            if not passed:
                log(f"Test '{name}' failed, continuing with remaining tests...", "WARN")
            log("")
        except Exception as e:
            log(f"Test '{name}' raised exception: {e}", "ERROR")
            results.append((name, False))
            log("")
    
    # Summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        log(f"{status} - {name}")
    
    log("")
    log(f"Total: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        log("=" * 80)
        log("🎉 ALL TESTS PASSED!")
        log("=" * 80)
        return 0
    else:
        log("=" * 80)
        log(f"⚠️  {total_count - passed_count} TEST(S) FAILED")
        log("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
