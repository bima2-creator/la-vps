#!/usr/bin/env python3
"""
LA Tracker Backend API Test Suite - SPK Upload Feature
Tests the new 'kind' tag for work order attachments (SPK vs general).
"""

import io
import sys
import time
import requests
from typing import Optional

# Backend URL from environment
BASE_URL = "https://project-bootstrap-18.preview.emergentagent.com/api"

# Test credentials (username-based auth)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Global token storage
TOKEN: Optional[str] = None

# Test data IDs
TEST_WO_ID: Optional[str] = None
TEST_RUN_ID = str(int(time.time()))


def log(msg: str, level: str = "INFO"):
    """Print formatted log message."""
    print(f"[{level}] {msg}")


def create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF for testing."""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""


def create_fake_png() -> bytes:
    """Create fake PNG bytes for testing rejection."""
    # Valid PNG header
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


def test_login() -> bool:
    """Step 1: Login as admin with username/password"""
    global TOKEN
    log("=" * 80)
    log("STEP 1: Login as admin")
    log("=" * 80)
    
    try:
        log(f"Attempting login with username={ADMIN_USERNAME}...")
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ Login failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        if "token" not in data:
            log(f"❌ Login response missing 'token' field: {data}", "ERROR")
            return False
        
        TOKEN = data["token"]
        log(f"✅ Login successful")
        log(f"   Token: {TOKEN[:30]}...")
        log(f"   Username: {data.get('username')}")
        log(f"   Role: {data.get('role')}")
        log(f"   Email: {data.get('email')}")
        
        return True
        
    except Exception as e:
        log(f"❌ Login exception: {e}", "ERROR")
        return False


def test_create_workorder() -> bool:
    """Step 2: Create a work order"""
    global TEST_WO_ID
    log("\n" + "=" * 80)
    log("STEP 2: Create a work order")
    log("=" * 80)
    
    try:
        payload = {
            "pelanggan": "SPK TEST WO",
            "jenis_order": "PSB"
        }
        
        log(f"Creating work order with payload: {payload}")
        resp = requests.post(
            f"{BASE_URL}/workorders",
            json=payload,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
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
        log(f"❌ Create work order exception: {e}", "ERROR")
        return False


def test_upload_spk_pdf() -> bool:
    """Step 3: Upload SPK PDF with kind=spk"""
    log("\n" + "=" * 80)
    log("STEP 3: Upload SPK PDF with kind=spk")
    log("=" * 80)
    
    try:
        pdf_bytes = create_minimal_pdf()
        log(f"Created minimal PDF ({len(pdf_bytes)} bytes)")
        
        files = {
            'file': ('spk_test.pdf', io.BytesIO(pdf_bytes), 'application/pdf')
        }
        data = {
            'kind': 'spk'
        }
        
        log(f"Uploading to /workorders/{TEST_WO_ID}/attachments with kind=spk...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ Upload failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        result = resp.json()
        log(f"✅ SPK PDF uploaded successfully")
        log(f"   ID: {result.get('id')}")
        log(f"   Kind: {result.get('kind')}")
        log(f"   Filename: {result.get('original_filename')}")
        log(f"   Content-Type: {result.get('content_type')}")
        log(f"   Size: {result.get('size')} bytes")
        
        # Verify kind is "spk"
        if result.get('kind') != 'spk':
            log(f"❌ Expected kind='spk', got kind='{result.get('kind')}'", "ERROR")
            return False
        
        log("✅ Kind field correctly set to 'spk'")
        return True
        
    except Exception as e:
        log(f"❌ Upload SPK PDF exception: {e}", "ERROR")
        return False


def test_reject_non_pdf() -> bool:
    """Step 4: Reject non-PDF file with kind=spk"""
    log("\n" + "=" * 80)
    log("STEP 4: Reject non-PDF file with kind=spk")
    log("=" * 80)
    
    try:
        png_bytes = create_fake_png()
        log(f"Created fake PNG ({len(png_bytes)} bytes)")
        
        files = {
            'file': ('test.png', io.BytesIO(png_bytes), 'image/png')
        }
        data = {
            'kind': 'spk'
        }
        
        log(f"Attempting to upload PNG to /workorders/{TEST_WO_ID}/attachments with kind=spk...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 400:
            log(f"❌ Expected HTTP 400, got {resp.status_code}", "ERROR")
            log(f"   Response: {resp.text}")
            return False
        
        result = resp.json()
        detail = result.get('detail', '')
        log(f"✅ Non-PDF correctly rejected with HTTP 400")
        log(f"   Error message: {detail}")
        
        # Verify error message
        expected_msg = "Hanya file PDF yang diperbolehkan"
        if expected_msg not in detail:
            log(f"❌ Expected error message '{expected_msg}', got '{detail}'", "ERROR")
            return False
        
        log(f"✅ Error message correct: '{expected_msg}'")
        return True
        
    except Exception as e:
        log(f"❌ Reject non-PDF exception: {e}", "ERROR")
        return False


def test_list_attachments_spk() -> bool:
    """Step 5: List attachments and verify kind=spk"""
    log("\n" + "=" * 80)
    log("STEP 5: List attachments and verify kind=spk")
    log("=" * 80)
    
    try:
        log(f"Getting attachments for work order {TEST_WO_ID}...")
        resp = requests.get(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ List attachments failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        attachments = resp.json()
        log(f"✅ Retrieved {len(attachments)} attachment(s)")
        
        if len(attachments) == 0:
            log("❌ Expected at least 1 attachment, got 0", "ERROR")
            return False
        
        # Find the SPK attachment
        spk_found = False
        for att in attachments:
            log(f"   - ID: {att.get('id')}, Kind: {att.get('kind')}, Filename: {att.get('original_filename')}")
            if att.get('kind') == 'spk':
                spk_found = True
        
        if not spk_found:
            log("❌ No attachment with kind='spk' found", "ERROR")
            return False
        
        log("✅ Found attachment with kind='spk'")
        return True
        
    except Exception as e:
        log(f"❌ List attachments exception: {e}", "ERROR")
        return False


def test_upload_default_kind() -> bool:
    """Step 6: Upload PDF without kind field (should default to 'general')"""
    log("\n" + "=" * 80)
    log("STEP 6: Upload PDF without kind field (default to 'general')")
    log("=" * 80)
    
    try:
        pdf_bytes = create_minimal_pdf()
        log(f"Created minimal PDF ({len(pdf_bytes)} bytes)")
        
        files = {
            'file': ('general_test.pdf', io.BytesIO(pdf_bytes), 'application/pdf')
        }
        # No 'kind' field in data
        
        log(f"Uploading to /workorders/{TEST_WO_ID}/attachments WITHOUT kind field...")
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            files=files,
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ Upload failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        result = resp.json()
        log(f"✅ PDF uploaded successfully")
        log(f"   ID: {result.get('id')}")
        log(f"   Kind: {result.get('kind')}")
        log(f"   Filename: {result.get('original_filename')}")
        
        # Verify kind defaults to "general"
        if result.get('kind') != 'general':
            log(f"❌ Expected kind='general', got kind='{result.get('kind')}'", "ERROR")
            return False
        
        log("✅ Kind field correctly defaulted to 'general'")
        return True
        
    except Exception as e:
        log(f"❌ Upload default kind exception: {e}", "ERROR")
        return False


def test_list_both_attachments() -> bool:
    """Step 7: Confirm list shows 2 items: one kind=spk, one kind=general"""
    log("\n" + "=" * 80)
    log("STEP 7: Confirm list shows 2 attachments (spk + general)")
    log("=" * 80)
    
    try:
        log(f"Getting attachments for work order {TEST_WO_ID}...")
        resp = requests.get(
            f"{BASE_URL}/workorders/{TEST_WO_ID}/attachments",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ List attachments failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        attachments = resp.json()
        log(f"✅ Retrieved {len(attachments)} attachment(s)")
        
        if len(attachments) != 2:
            log(f"❌ Expected 2 attachments, got {len(attachments)}", "ERROR")
            return False
        
        # Count kinds
        spk_count = 0
        general_count = 0
        
        for att in attachments:
            kind = att.get('kind')
            log(f"   - ID: {att.get('id')}, Kind: {kind}, Filename: {att.get('original_filename')}")
            if kind == 'spk':
                spk_count += 1
            elif kind == 'general':
                general_count += 1
        
        if spk_count != 1:
            log(f"❌ Expected 1 attachment with kind='spk', got {spk_count}", "ERROR")
            return False
        
        if general_count != 1:
            log(f"❌ Expected 1 attachment with kind='general', got {general_count}", "ERROR")
            return False
        
        log("✅ Confirmed: 1 attachment with kind='spk', 1 with kind='general'")
        return True
        
    except Exception as e:
        log(f"❌ List both attachments exception: {e}", "ERROR")
        return False


def test_cleanup() -> bool:
    """Step 8: Cleanup - Delete the test work order"""
    log("\n" + "=" * 80)
    log("STEP 8: Cleanup - Delete test work order")
    log("=" * 80)
    
    try:
        log(f"Deleting work order {TEST_WO_ID}...")
        resp = requests.delete(
            f"{BASE_URL}/workorders/{TEST_WO_ID}",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"⚠️  Delete failed with status {resp.status_code}: {resp.text}", "WARN")
            log("   (This is not critical - test data may remain)")
            return True  # Don't fail the test suite for cleanup issues
        
        log(f"✅ Work order deleted successfully")
        return True
        
    except Exception as e:
        log(f"⚠️  Cleanup exception: {e}", "WARN")
        log("   (This is not critical - test data may remain)")
        return True  # Don't fail the test suite for cleanup issues


def main():
    """Run all SPK upload tests"""
    log("=" * 80)
    log("LA TRACKER - SPK UPLOAD FEATURE TEST SUITE")
    log("=" * 80)
    log(f"Backend URL: {BASE_URL}")
    log(f"Test Run ID: {TEST_RUN_ID}")
    log("")
    
    tests = [
        ("Login as admin", test_login),
        ("Create work order", test_create_workorder),
        ("Upload SPK PDF with kind=spk", test_upload_spk_pdf),
        ("Reject non-PDF with kind=spk", test_reject_non_pdf),
        ("List attachments (verify kind=spk)", test_list_attachments_spk),
        ("Upload PDF without kind (default to general)", test_upload_default_kind),
        ("List both attachments (spk + general)", test_list_both_attachments),
        ("Cleanup", test_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                log(f"\n❌ TEST FAILED: {name}\n", "ERROR")
        except Exception as e:
            failed += 1
            log(f"\n❌ TEST EXCEPTION: {name} - {e}\n", "ERROR")
    
    # Summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log(f"Total tests: {len(tests)}")
    log(f"Passed: {passed}")
    log(f"Failed: {failed}")
    
    if failed == 0:
        log("\n✅ ALL TESTS PASSED", "SUCCESS")
        return 0
    else:
        log(f"\n❌ {failed} TEST(S) FAILED", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
