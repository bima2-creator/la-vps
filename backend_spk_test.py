#!/usr/bin/env python3
"""
SPK Upload Feature Test Suite for LA Tracker
Tests the SPK (Surat Perintah Kerja) upload functionality on Work Order attachments
"""

import requests
import sys
from io import BytesIO
from datetime import datetime

# Base URL from frontend/.env
BASE_URL = "https://project-bootstrap-18.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Test results tracking
test_results = []

def log_test(step, description, passed, status_code=None, details=""):
    """Log test result"""
    result = {
        "step": step,
        "description": description,
        "passed": passed,
        "status_code": status_code,
        "details": details
    }
    test_results.append(result)
    
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} - Step {step}: {description}")
    if status_code:
        print(f"   HTTP Status: {status_code}")
    if details:
        print(f"   Details: {details}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("SPK UPLOAD TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    for result in test_results:
        status = "✅" if result["passed"] else "❌"
        print(f"{status} Step {result['step']}: {result['description']} (HTTP {result['status_code']})")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    print("="*80)
    
    # Check for 500 errors
    errors_500 = [r for r in test_results if r["status_code"] and r["status_code"] >= 500]
    if errors_500:
        print("\n⚠️  WARNING: 500 ERRORS DETECTED:")
        for err in errors_500:
            print(f"   Step {err['step']}: {err['description']} returned {err['status_code']}")

def main():
    print("="*80)
    print("SPK UPLOAD FEATURE TEST - LA TRACKER")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Testing with admin credentials: {ADMIN_USERNAME}")
    
    token = None
    wo_id = None
    spk_attachment_id = None
    
    try:
        # Step 1: Login as admin
        print("\n--- Step 1: Login as admin ---")
        login_response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if login_response.status_code in [200, 201]:
            token = login_response.json().get("token")
            log_test(1, "Login as admin", True, login_response.status_code, f"Token received: {token[:20]}...")
        else:
            log_test(1, "Login as admin", False, login_response.status_code, login_response.text)
            print("❌ Login failed, cannot continue tests")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: Create a work order
        print("\n--- Step 2: Create work order ---")
        wo_data = {
            "pelanggan": "SPK TEST WO",
            "jenis_order": "PSB",
            "sa_id": "SPK_TEST_SA_" + str(int(datetime.now().timestamp()))
        }
        wo_response = requests.post(
            f"{BASE_URL}/workorders",
            json=wo_data,
            headers=headers,
            timeout=10
        )
        
        if wo_response.status_code in [200, 201]:
            wo_id = wo_response.json().get("id")
            log_test(2, "Create work order", True, wo_response.status_code, f"WO ID: {wo_id}")
        else:
            log_test(2, "Create work order", False, wo_response.status_code, wo_response.text)
            print("❌ Work order creation failed, cannot continue tests")
            return
        
        # Step 3: Upload SPK (valid PDF with kind=spk)
        print("\n--- Step 3: Upload valid PDF with kind=spk ---")
        valid_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        files = {
            "file": ("spk_test.pdf", BytesIO(valid_pdf), "application/pdf")
        }
        data = {"kind": "spk"}
        
        upload_response = requests.post(
            f"{BASE_URL}/workorders/{wo_id}/attachments",
            files=files,
            data=data,
            headers=headers,
            timeout=10
        )
        
        if upload_response.status_code == 200:
            response_json = upload_response.json()
            if response_json.get("kind") == "spk":
                spk_attachment_id = response_json.get("id")
                log_test(3, "Upload valid PDF with kind=spk", True, upload_response.status_code, 
                        f"SPK uploaded, kind={response_json.get('kind')}, id={spk_attachment_id}")
            else:
                log_test(3, "Upload valid PDF with kind=spk", False, upload_response.status_code, 
                        f"Expected kind='spk', got kind='{response_json.get('kind')}'")
        else:
            log_test(3, "Upload valid PDF with kind=spk", False, upload_response.status_code, upload_response.text)
        
        # Step 4: Non-PDF reject (upload PNG with kind=spk)
        print("\n--- Step 4: Upload PNG with kind=spk (should reject) ---")
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        files_png = {
            "file": ("test.png", BytesIO(png_bytes), "image/png")
        }
        data_png = {"kind": "spk"}
        
        png_response = requests.post(
            f"{BASE_URL}/workorders/{wo_id}/attachments",
            files=files_png,
            data=data_png,
            headers=headers,
            timeout=10
        )
        
        if png_response.status_code == 400:
            error_msg = png_response.json().get("detail", "")
            if "Hanya file PDF yang diperbolehkan" in error_msg:
                log_test(4, "Non-PDF reject", True, png_response.status_code, 
                        f"Correctly rejected: {error_msg}")
            else:
                log_test(4, "Non-PDF reject", False, png_response.status_code, 
                        f"Wrong error message: {error_msg}")
        else:
            log_test(4, "Non-PDF reject", False, png_response.status_code, 
                    "Expected 400 rejection, got different status")
        
        # Step 5: GET attachments list
        print("\n--- Step 5: GET attachments list ---")
        get_response = requests.get(
            f"{BASE_URL}/workorders/{wo_id}/attachments",
            headers=headers,
            timeout=10
        )
        
        if get_response.status_code == 200:
            attachments = get_response.json()
            spk_found = any(att.get("kind") == "spk" for att in attachments)
            if spk_found:
                log_test(5, "GET attachments list", True, get_response.status_code, 
                        f"SPK attachment found in list ({len(attachments)} total)")
            else:
                log_test(5, "GET attachments list", False, get_response.status_code, 
                        "SPK attachment not found in list")
        else:
            log_test(5, "GET attachments list", False, get_response.status_code, get_response.text)
        
        # Step 6: Upload PDF without kind (should default to general)
        print("\n--- Step 6: Upload PDF without kind (should default to general) ---")
        files_no_kind = {
            "file": ("general_test.pdf", BytesIO(valid_pdf), "application/pdf")
        }
        
        no_kind_response = requests.post(
            f"{BASE_URL}/workorders/{wo_id}/attachments",
            files=files_no_kind,
            headers=headers,
            timeout=10
        )
        
        if no_kind_response.status_code == 200:
            response_json = no_kind_response.json()
            if response_json.get("kind") == "general":
                log_test(6, "Upload PDF without kind", True, no_kind_response.status_code, 
                        f"Correctly defaulted to kind='general'")
            else:
                log_test(6, "Upload PDF without kind", False, no_kind_response.status_code, 
                        f"Expected kind='general', got kind='{response_json.get('kind')}'")
        else:
            log_test(6, "Upload PDF without kind", False, no_kind_response.status_code, no_kind_response.text)
        
        # Step 7: SINGLE SPK rule - try uploading second SPK (should reject)
        print("\n--- Step 7: SINGLE SPK rule - upload second SPK (should reject) ---")
        files_second_spk = {
            "file": ("spk_second.pdf", BytesIO(valid_pdf), "application/pdf")
        }
        data_second_spk = {"kind": "spk"}
        
        second_spk_response = requests.post(
            f"{BASE_URL}/workorders/{wo_id}/attachments",
            files=files_second_spk,
            data=data_second_spk,
            headers=headers,
            timeout=10
        )
        
        if second_spk_response.status_code == 400:
            error_msg = second_spk_response.json().get("detail", "")
            if "SPK sudah ada" in error_msg:
                log_test("7a", "SINGLE SPK rule - reject second SPK", True, second_spk_response.status_code, 
                        f"Correctly rejected: {error_msg}")
            else:
                log_test("7a", "SINGLE SPK rule - reject second SPK", False, second_spk_response.status_code, 
                        f"Wrong error message: {error_msg}")
        else:
            log_test("7a", "SINGLE SPK rule - reject second SPK", False, second_spk_response.status_code, 
                    "Expected 400 rejection, got different status")
        
        # Step 7b: DELETE existing SPK and upload new one
        print("\n--- Step 7b: DELETE existing SPK and upload new one ---")
        if spk_attachment_id:
            delete_response = requests.delete(
                f"{BASE_URL}/attachments/{spk_attachment_id}",
                headers=headers,
                timeout=10
            )
            
            if delete_response.status_code in [200, 204]:
                print(f"   SPK deleted successfully (HTTP {delete_response.status_code})")
                
                # Now upload new SPK
                files_new_spk = {
                    "file": ("spk_new.pdf", BytesIO(valid_pdf), "application/pdf")
                }
                data_new_spk = {"kind": "spk"}
                
                new_spk_response = requests.post(
                    f"{BASE_URL}/workorders/{wo_id}/attachments",
                    files=files_new_spk,
                    data=data_new_spk,
                    headers=headers,
                    timeout=10
                )
                
                if new_spk_response.status_code == 200:
                    log_test("7b", "SPK replacement (delete + upload)", True, new_spk_response.status_code, 
                            "SPK replacement successful")
                else:
                    log_test("7b", "SPK replacement (delete + upload)", False, new_spk_response.status_code, 
                            new_spk_response.text)
            else:
                log_test("7b", "SPK replacement (delete + upload)", False, delete_response.status_code, 
                        f"Delete failed: {delete_response.text}")
        else:
            log_test("7b", "SPK replacement (delete + upload)", False, None, 
                    "No SPK attachment ID to delete")
        
        # Step 8: Cleanup - DELETE work order
        print("\n--- Step 8: Cleanup - DELETE work order ---")
        cleanup_response = requests.delete(
            f"{BASE_URL}/workorders/{wo_id}",
            headers=headers,
            timeout=10
        )
        
        if cleanup_response.status_code in [200, 204]:
            log_test(8, "Cleanup - DELETE work order", True, cleanup_response.status_code, 
                    "Work order deleted successfully")
        else:
            log_test(8, "Cleanup - DELETE work order", False, cleanup_response.status_code, 
                    cleanup_response.text)
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Network error: {e}")
        log_test("ERROR", "Network request", False, None, str(e))
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        log_test("ERROR", "Test execution", False, None, str(e))
    
    # Print summary
    print_summary()
    
    # Return exit code based on results
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
