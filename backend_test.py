#!/usr/bin/env python3
"""
LA Tracker Backend API Test Suite
Tests all invoice-related features including PDF-only restrictions and attachment requirements.
"""

import io
import sys
import time
import requests
from typing import Optional, Dict, Any

# Backend URL from environment
BASE_URL = "https://github-restart-1.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@la-tracker.com"
ADMIN_PASSWORD = "admin123"

# Global token storage
TOKEN: Optional[str] = None

# Test data IDs (will be populated during tests)
TEST_WO_ID_NO_ATTACHMENT: Optional[str] = None
TEST_WO_ID_WITH_ATTACHMENT: Optional[str] = None
TEST_PELANGGAN: str = "TEST_PELANGGAN_REGRESSION"
TEST_INVOICE_ID: Optional[str] = None

# Unique suffix for this test run
TEST_RUN_ID = str(int(time.time()))


def log(msg: str, level: str = "INFO"):
    """Print formatted log message."""
    print(f"[{level}] {msg}")


def create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF for testing using reportlab."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        c.drawString(100, 750, "Test PDF Document")
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    except ImportError:
        # Fallback to minimal PDF if reportlab not available
        return b"%PDF-1.4\n1 0 obj<<>>endobj\nxref\n0 1\n0000000000 65535 f\ntrailer<<>>\nstartxref\n0\n%%EOF"


def create_fake_png() -> bytes:
    """Create fake PNG bytes for testing rejection."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"


def test_login() -> bool:
    """Test 1: Login & Auth - POST /api/auth/login and GET /api/auth/me"""
    global TOKEN
    log("=" * 80)
    log("TEST 1: Login & Auth")
    log("=" * 80)
    
    try:
        # Step 1: Login
        log(f"Attempting login with {ADMIN_EMAIL}...")
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
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
        log(f"✅ Login successful, token received: {TOKEN[:20]}...")
        
        # Step 2: Verify /api/auth/me
        log("Verifying /api/auth/me with Bearer token...")
        resp = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ /auth/me failed with status {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        user = resp.json()
        if user.get("email") != ADMIN_EMAIL:
            log(f"❌ /auth/me returned wrong user: {user}", "ERROR")
            return False
        
        log(f"✅ /auth/me successful, user: {user.get('name')} ({user.get('email')})")
        return True
        
    except Exception as e:
        log(f"❌ Exception during login test: {e}", "ERROR")
        return False


def test_wo_attachment_pdf_only() -> bool:
    """Test 2: Work Order Attachment PDF-only restriction"""
    global TEST_WO_ID_NO_ATTACHMENT, TEST_WO_ID_WITH_ATTACHMENT
    log("=" * 80)
    log("TEST 2: Work Order Attachment PDF-only restriction")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Create two test work orders
        log("Creating test work order #1 (no attachment)...")
        wo_data = {
            "pelanggan": TEST_PELANGGAN,
            "sa_id": "TEST_SA_001",
            "jenis_order": "PSB",
            "wo_jenis_pekerjaan": "SURVEY",
            "activity_survey_start": "2024-01-01T10:00:00",
            "activity_survey_end": "2024-01-01T12:00:00",
            "hasil_survey_status": "OK",
            "boq_jasa": 500000,
            "boq_material": 500000,
            "boq_jumlah": 1000000,
        }
        resp = requests.post(f"{BASE_URL}/workorders", json=wo_data, headers=headers, timeout=10)
        if resp.status_code != 200:
            log(f"❌ Failed to create WO #1: {resp.status_code} {resp.text}", "ERROR")
            return False
        TEST_WO_ID_NO_ATTACHMENT = resp.json()["id"]
        log(f"✅ Created WO #1: {TEST_WO_ID_NO_ATTACHMENT}")
        
        log("Creating test work order #2 (will have attachment)...")
        wo_data["sa_id"] = "TEST_SA_002"
        resp = requests.post(f"{BASE_URL}/workorders", json=wo_data, headers=headers, timeout=10)
        if resp.status_code != 200:
            log(f"❌ Failed to create WO #2: {resp.status_code} {resp.text}", "ERROR")
            return False
        TEST_WO_ID_WITH_ATTACHMENT = resp.json()["id"]
        log(f"✅ Created WO #2: {TEST_WO_ID_WITH_ATTACHMENT}")
        
        # Test: Upload non-PDF (should fail with 400)
        log(f"Attempting to upload PNG to WO #{TEST_WO_ID_WITH_ATTACHMENT} (should fail)...")
        files = {"file": ("test.png", create_fake_png(), "image/png")}
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID_WITH_ATTACHMENT}/attachments",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected 400 for PNG upload, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        if "Hanya file PDF yang diperbolehkan" not in resp.text:
            log(f"❌ Expected error message 'Hanya file PDF yang diperbolehkan', got: {resp.text}", "ERROR")
            return False
        
        log("✅ PNG upload correctly rejected with 400")
        
        # Test: Upload PDF (should succeed)
        log(f"Uploading PDF to WO #{TEST_WO_ID_WITH_ATTACHMENT} (should succeed)...")
        files = {"file": ("test.pdf", create_minimal_pdf(), "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/workorders/{TEST_WO_ID_WITH_ATTACHMENT}/attachments",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ PDF upload failed with {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        att_data = resp.json()
        if att_data.get("content_type") != "application/pdf":
            log(f"❌ Attachment content_type is not application/pdf: {att_data}", "ERROR")
            return False
        
        log(f"✅ PDF uploaded successfully: {att_data.get('id')}")
        
        # Verify attachment is listed
        log(f"Verifying attachment list for WO #{TEST_WO_ID_WITH_ATTACHMENT}...")
        resp = requests.get(
            f"{BASE_URL}/workorders/{TEST_WO_ID_WITH_ATTACHMENT}/attachments",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Failed to list attachments: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        attachments = resp.json()
        if len(attachments) != 1:
            log(f"❌ Expected 1 attachment, got {len(attachments)}", "ERROR")
            return False
        
        if attachments[0].get("content_type") != "application/pdf":
            log(f"❌ Listed attachment content_type is not application/pdf", "ERROR")
            return False
        
        log("✅ Attachment correctly listed with content_type=application/pdf")
        return True
        
    except Exception as e:
        log(f"❌ Exception during WO attachment test: {e}", "ERROR")
        return False


def test_invoice_candidates_has_attachment() -> bool:
    """Test 3: Invoice Candidates includes has_attachment flag"""
    log("=" * 80)
    log("TEST 3: Invoice Candidates includes has_attachment flag")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        log(f"Fetching invoice candidates for jenis_pekerjaan=SURVEY, pelanggan={TEST_PELANGGAN}...")
        resp = requests.get(
            f"{BASE_URL}/invoices/candidates",
            params={
                "jenis_pekerjaan": "SURVEY",
                "pelanggans": TEST_PELANGGAN
            },
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Failed to fetch candidates: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        candidates = resp.json()
        log(f"Found {len(candidates)} candidates")
        
        # Find our two test WOs
        wo1 = None
        wo2 = None
        for c in candidates:
            if c["id"] == TEST_WO_ID_NO_ATTACHMENT:
                wo1 = c
            elif c["id"] == TEST_WO_ID_WITH_ATTACHMENT:
                wo2 = c
        
        if not wo1:
            log(f"❌ WO #1 (no attachment) not found in candidates", "ERROR")
            return False
        
        if not wo2:
            log(f"❌ WO #2 (with attachment) not found in candidates", "ERROR")
            return False
        
        # Verify has_attachment flags
        if wo1.get("has_attachment") is not False:
            log(f"❌ WO #1 has_attachment should be False, got: {wo1.get('has_attachment')}", "ERROR")
            return False
        
        if wo2.get("has_attachment") is not True:
            log(f"❌ WO #2 has_attachment should be True, got: {wo2.get('has_attachment')}", "ERROR")
            return False
        
        log(f"✅ WO #1 has_attachment=False (correct)")
        log(f"✅ WO #2 has_attachment=True (correct)")
        return True
        
    except Exception as e:
        log(f"❌ Exception during invoice candidates test: {e}", "ERROR")
        return False


def test_invoice_create_rejects_missing_attachment() -> bool:
    """Test 4: Invoice create rejects WO without attachment"""
    global TEST_INVOICE_ID
    log("=" * 80)
    log("TEST 4: Invoice create rejects WO without attachment")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Test: Create invoice with WO that has no attachment (should fail)
        log("Attempting to create invoice with WO #1 (no attachment) - should fail...")
        invoice_data = {
            "pelanggans": [TEST_PELANGGAN],
            "jenis_pekerjaan": "SURVEY",
            "invoice_no": "TEST_INV_001",
            "tanggal": "2024-01-15",
            "work_order_ids": [TEST_WO_ID_NO_ATTACHMENT, TEST_WO_ID_WITH_ATTACHMENT]
        }
        resp = requests.post(f"{BASE_URL}/invoices", json=invoice_data, headers=headers, timeout=10)
        
        if resp.status_code != 400:
            log(f"❌ Expected 400 for invoice with missing attachment, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        error_text = resp.json().get("detail", "")
        if "wajib upload attachment PDF" not in error_text:
            log(f"❌ Expected error message about 'wajib upload attachment PDF', got: {error_text}", "ERROR")
            return False
        
        if "TEST_SA_001" not in error_text:
            log(f"❌ Expected error to mention WO #1's SA_ID (TEST_SA_001), got: {error_text}", "ERROR")
            return False
        
        log(f"✅ Invoice creation correctly rejected: {error_text}")
        
        # Test: Create invoice with only WO that has attachment (should succeed)
        log("Creating invoice with only WO #2 (has attachment) - should succeed...")
        invoice_data["work_order_ids"] = [TEST_WO_ID_WITH_ATTACHMENT]
        invoice_data["invoice_no"] = f"TEST_INV_{TEST_RUN_ID}"
        resp = requests.post(f"{BASE_URL}/invoices", json=invoice_data, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            log(f"❌ Invoice creation failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        invoice = resp.json()
        TEST_INVOICE_ID = invoice.get("id")
        log(f"✅ Invoice created successfully: {TEST_INVOICE_ID}")
        
        if invoice.get("grand_total") != 1000000:
            log(f"❌ Expected grand_total=1000000, got {invoice.get('grand_total')}", "ERROR")
            return False
        
        log(f"✅ Invoice grand_total correct: {invoice.get('grand_total')}")
        return True
        
    except Exception as e:
        log(f"❌ Exception during invoice create test: {e}", "ERROR")
        return False


def test_faktur_pajak_pdf_only() -> bool:
    """Test 5: Faktur Pajak upload/download/delete (PDF only)"""
    log("=" * 80)
    log("TEST 5: Faktur Pajak upload/download/delete (PDF only)")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Test: Upload non-PDF (should fail)
        log(f"Attempting to upload PNG as Faktur Pajak to invoice {TEST_INVOICE_ID} (should fail)...")
        files = {"file": ("faktur.png", create_fake_png(), "image/png")}
        resp = requests.post(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/faktur-pajak",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected 400 for PNG upload, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        if "Hanya file PDF yang diperbolehkan" not in resp.text:
            log(f"❌ Expected error message 'Hanya file PDF yang diperbolehkan', got: {resp.text}", "ERROR")
            return False
        
        log("✅ PNG upload correctly rejected with 400")
        
        # Test: Upload PDF (should succeed)
        log(f"Uploading PDF as Faktur Pajak to invoice {TEST_INVOICE_ID} (should succeed)...")
        files = {"file": ("faktur_pajak.pdf", create_minimal_pdf(), "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/faktur-pajak",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Faktur Pajak upload failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        fp_data = resp.json()
        if fp_data.get("faktur_pajak_attachment", {}).get("ext") != "pdf":
            log(f"❌ Faktur Pajak ext should be 'pdf', got: {fp_data}", "ERROR")
            return False
        
        if fp_data.get("faktur_pajak_attachment", {}).get("content_type") != "application/pdf":
            log(f"❌ Faktur Pajak content_type should be 'application/pdf', got: {fp_data}", "ERROR")
            return False
        
        log(f"✅ Faktur Pajak uploaded successfully with ext=pdf, content_type=application/pdf")
        
        # Test: Download Faktur Pajak
        log(f"Downloading Faktur Pajak from invoice {TEST_INVOICE_ID}...")
        resp = requests.get(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/faktur-pajak/download",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Faktur Pajak download failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        if resp.headers.get("Content-Type") != "application/pdf":
            log(f"❌ Downloaded Faktur Pajak Content-Type should be application/pdf, got: {resp.headers.get('Content-Type')}", "ERROR")
            return False
        
        if len(resp.content) < 10:
            log(f"❌ Downloaded Faktur Pajak is too small: {len(resp.content)} bytes", "ERROR")
            return False
        
        log(f"✅ Faktur Pajak downloaded successfully: {len(resp.content)} bytes, Content-Type=application/pdf")
        
        # Test: Delete Faktur Pajak
        log(f"Deleting Faktur Pajak from invoice {TEST_INVOICE_ID}...")
        resp = requests.delete(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/faktur-pajak",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Faktur Pajak delete failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        log("✅ Faktur Pajak deleted successfully")
        
        # Verify it's gone
        log("Verifying Faktur Pajak is removed from invoice...")
        resp = requests.get(f"{BASE_URL}/invoices/{TEST_INVOICE_ID}", headers=headers, timeout=10)
        if resp.status_code != 200:
            log(f"❌ Failed to fetch invoice: {resp.status_code}", "ERROR")
            return False
        
        invoice = resp.json()
        if invoice.get("faktur_pajak_attachment"):
            log(f"❌ Faktur Pajak should be removed but still present: {invoice.get('faktur_pajak_attachment')}", "ERROR")
            return False
        
        log("✅ Faktur Pajak correctly removed from invoice")
        
        # Re-upload for next test
        log("Re-uploading Faktur Pajak for PDF merge test...")
        files = {"file": ("faktur_pajak.pdf", create_minimal_pdf(), "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/faktur-pajak",
            files=files,
            headers=headers,
            timeout=10
        )
        if resp.status_code != 200:
            log(f"❌ Re-upload failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        log("✅ Faktur Pajak re-uploaded for next test")
        
        return True
        
    except Exception as e:
        log(f"❌ Exception during Faktur Pajak test: {e}", "ERROR")
        return False


def test_bukti_potong_pdf_only() -> bool:
    """Test 6: Bukti Potong upload/download/delete (PDF only)"""
    log("=" * 80)
    log("TEST 6: Bukti Potong upload/download/delete (PDF only)")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Test: Upload non-PDF (should fail)
        log(f"Attempting to upload PNG as Bukti Potong to invoice {TEST_INVOICE_ID} (should fail)...")
        files = {"file": ("bukti.png", create_fake_png(), "image/png")}
        resp = requests.post(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/bukti-potong",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected 400 for PNG upload, got {resp.status_code}: {resp.text}", "ERROR")
            return False
        
        if "Hanya file PDF yang diperbolehkan" not in resp.text:
            log(f"❌ Expected error message 'Hanya file PDF yang diperbolehkan', got: {resp.text}", "ERROR")
            return False
        
        log("✅ PNG upload correctly rejected with 400")
        
        # Test: Upload PDF (should succeed)
        log(f"Uploading PDF as Bukti Potong to invoice {TEST_INVOICE_ID} (should succeed)...")
        files = {"file": ("bukti_potong.pdf", create_minimal_pdf(), "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/bukti-potong",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Bukti Potong upload failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        bp_data = resp.json()
        if bp_data.get("bukti_potong_attachment", {}).get("ext") != "pdf":
            log(f"❌ Bukti Potong ext should be 'pdf', got: {bp_data}", "ERROR")
            return False
        
        if bp_data.get("bukti_potong_attachment", {}).get("content_type") != "application/pdf":
            log(f"❌ Bukti Potong content_type should be 'application/pdf', got: {bp_data}", "ERROR")
            return False
        
        log(f"✅ Bukti Potong uploaded successfully with ext=pdf, content_type=application/pdf")
        
        # Test: Download Bukti Potong
        log(f"Downloading Bukti Potong from invoice {TEST_INVOICE_ID}...")
        resp = requests.get(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/bukti-potong/download",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 200:
            log(f"❌ Bukti Potong download failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        if resp.headers.get("Content-Type") != "application/pdf":
            log(f"❌ Downloaded Bukti Potong Content-Type should be application/pdf, got: {resp.headers.get('Content-Type')}", "ERROR")
            return False
        
        if len(resp.content) < 10:
            log(f"❌ Downloaded Bukti Potong is too small: {len(resp.content)} bytes", "ERROR")
            return False
        
        log(f"✅ Bukti Potong downloaded successfully: {len(resp.content)} bytes, Content-Type=application/pdf")
        
        # Don't delete yet - we need it for the PDF merge test
        log("✅ Keeping Bukti Potong for PDF merge test")
        return True
        
    except Exception as e:
        log(f"❌ Exception during Bukti Potong test: {e}", "ERROR")
        return False


def test_invoice_pdf_merge() -> bool:
    """Test 7: Invoice PDF merges lampiran"""
    log("=" * 80)
    log("TEST 7: Invoice PDF merges lampiran")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # At this point, the invoice should have:
        # - Faktur Pajak PDF (re-uploaded in test 5)
        # - Bukti Potong PDF (uploaded in test 6)
        # - WO #2 with 1 PDF attachment
        
        log(f"Downloading merged invoice PDF for invoice {TEST_INVOICE_ID}...")
        resp = requests.get(
            f"{BASE_URL}/invoices/{TEST_INVOICE_ID}/pdf",
            headers=headers,
            timeout=30
        )
        
        if resp.status_code != 200:
            log(f"❌ Invoice PDF download failed: {resp.status_code} {resp.text}", "ERROR")
            return False
        
        # Verify Content-Type
        if resp.headers.get("Content-Type") != "application/pdf":
            log(f"❌ Invoice PDF Content-Type should be application/pdf, got: {resp.headers.get('Content-Type')}", "ERROR")
            return False
        
        log(f"✅ Invoice PDF Content-Type is application/pdf")
        
        # Verify Content-Disposition includes invoice number
        content_disp = resp.headers.get("Content-Disposition", "")
        if "inline" not in content_disp or "filename" not in content_disp:
            log(f"❌ Content-Disposition should include 'inline; filename=...', got: {content_disp}", "ERROR")
            return False
        
        if f"TEST_INV_{TEST_RUN_ID}" not in content_disp:
            log(f"❌ Content-Disposition should include invoice number TEST_INV_{TEST_RUN_ID}, got: {content_disp}", "ERROR")
            return False
        
        log(f"✅ Content-Disposition correct: {content_disp}")
        
        # Verify PDF is valid and has multiple pages
        pdf_bytes = resp.content
        if len(pdf_bytes) < 100:
            log(f"❌ PDF is too small: {len(pdf_bytes)} bytes", "ERROR")
            return False
        
        log(f"✅ PDF size: {len(pdf_bytes)} bytes")
        
        # Try to parse with pypdf to count pages
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            log(f"✅ PDF has {page_count} pages")
            
            # Expected: at least 4 pages
            # - Main invoice (at least 1 page)
            # - Faktur Pajak (1 page)
            # - Bukti Potong (1 page)
            # - WO attachment (1 page)
            if page_count < 4:
                log(f"❌ Expected at least 4 pages (main + faktur + bukti + wo attachment), got {page_count}", "ERROR")
                return False
            
            log(f"✅ PDF merge successful: {page_count} pages (main + faktur pajak + bukti potong + wo attachments)")
            
        except ImportError:
            log("⚠️  pypdf not available, skipping page count verification", "WARN")
        except Exception as e:
            log(f"⚠️  Could not parse PDF for page count: {e}", "WARN")
        
        return True
        
    except Exception as e:
        log(f"❌ Exception during invoice PDF merge test: {e}", "ERROR")
        return False


def test_edge_cases() -> bool:
    """Test 8: Edge cases - invalid IDs, non-existent resources"""
    log("=" * 80)
    log("TEST 8: Edge Cases")
    log("=" * 80)
    
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Test: Invalid invoice ID (not ObjectId format)
        log("Testing invalid invoice ID 'abc' on faktur-pajak endpoint...")
        files = {"file": ("test.pdf", create_minimal_pdf(), "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/invoices/abc/faktur-pajak",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 400:
            log(f"❌ Expected 400 for invalid ID, got {resp.status_code}", "ERROR")
            return False
        
        if "Invalid id" not in resp.text:
            log(f"❌ Expected 'Invalid id' error, got: {resp.text}", "ERROR")
            return False
        
        log("✅ Invalid ID correctly rejected with 400 'Invalid id'")
        
        # Test: Non-existent invoice ID (valid ObjectId but not in DB)
        log("Testing non-existent invoice ID on faktur-pajak endpoint...")
        fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format but doesn't exist
        resp = requests.post(
            f"{BASE_URL}/invoices/{fake_id}/faktur-pajak",
            files=files,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code != 404:
            log(f"❌ Expected 404 for non-existent invoice, got {resp.status_code}", "ERROR")
            return False
        
        if "Invoice tidak ditemukan" not in resp.text:
            log(f"❌ Expected 'Invoice tidak ditemukan' error, got: {resp.text}", "ERROR")
            return False
        
        log("✅ Non-existent invoice correctly rejected with 404 'Invoice tidak ditemukan'")
        
        return True
        
    except Exception as e:
        log(f"❌ Exception during edge cases test: {e}", "ERROR")
        return False


def main():
    """Run all tests and report results."""
    log("=" * 80)
    log("LA TRACKER BACKEND API TEST SUITE")
    log("=" * 80)
    log(f"Base URL: {BASE_URL}")
    log(f"Admin Email: {ADMIN_EMAIL}")
    log("")
    
    results = {}
    
    # Run tests in sequence
    tests = [
        ("Login & Auth", test_login),
        ("Work Order Attachment PDF-only", test_wo_attachment_pdf_only),
        ("Invoice Candidates has_attachment flag", test_invoice_candidates_has_attachment),
        ("Invoice create rejects missing attachment", test_invoice_create_rejects_missing_attachment),
        ("Faktur Pajak PDF-only", test_faktur_pajak_pdf_only),
        ("Bukti Potong PDF-only", test_bukti_potong_pdf_only),
        ("Invoice PDF merge", test_invoice_pdf_merge),
        ("Edge Cases", test_edge_cases),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            log(f"❌ Test '{name}' crashed: {e}", "ERROR")
            results[name] = False
        log("")
    
    # Summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {name}")
    
    log("")
    log(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        log("🎉 ALL TESTS PASSED!", "SUCCESS")
        return 0
    else:
        log(f"⚠️  {total - passed} test(s) failed", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
