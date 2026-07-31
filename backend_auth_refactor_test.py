#!/usr/bin/env python3
"""
LA Tracker Backend AUTH REFACTOR Test Suite
Tests username-based authentication with 3 fixed users (admin/operator/guest).
"""

import sys
import time
import requests
from typing import Optional, Dict, Any

# Backend URL from environment
BASE_URL = "https://project-bootstrap-18.preview.emergentagent.com/api"

# Test credentials (username-based)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
OPERATOR_USERNAME = "operator"
OPERATOR_PASSWORD = "operator"
GUEST_USERNAME = "guest"
GUEST_PASSWORD = "guest"

# Global token storage
ADMIN_TOKEN: Optional[str] = None
OPERATOR_TOKEN: Optional[str] = None
GUEST_TOKEN: Optional[str] = None

# Test data
TEST_WO_ID: Optional[str] = None
TEST_RUN_ID = str(int(time.time()))


def log(msg: str, level: str = "INFO"):
    """Print formatted log message."""
    print(f"[{level}] {msg}")


def test_1_login_admin() -> bool:
    """Test 1: Login with admin/admin123 - expect 200, token, username=admin, role=admin, email=support@almar.co.id"""
    global ADMIN_TOKEN
    log("=" * 80)
    log("TEST 1: Login with admin/admin123")
    log("=" * 80)
    
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Expected 200, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        log(f"Response data: {data}")
        
        # Check required fields
        if "token" not in data:
            log("❌ FAIL: Missing 'token' field", "ERROR")
            return False
        
        if data.get("username") != "admin":
            log(f"❌ FAIL: Expected username='admin', got '{data.get('username')}'", "ERROR")
            return False
        
        if data.get("role") != "admin":
            log(f"❌ FAIL: Expected role='admin', got '{data.get('role')}'", "ERROR")
            return False
        
        if data.get("email") != "support@almar.co.id":
            log(f"❌ FAIL: Expected email='support@almar.co.id', got '{data.get('email')}'", "ERROR")
            return False
        
        ADMIN_TOKEN = data["token"]
        log(f"✅ PASS: Admin login successful")
        log(f"  - Token: {ADMIN_TOKEN[:30]}...")
        log(f"  - Username: {data['username']}")
        log(f"  - Role: {data['role']}")
        log(f"  - Email: {data['email']}")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_2_login_operator() -> bool:
    """Test 2: Login with operator/operator - expect 200, role=operator"""
    global OPERATOR_TOKEN
    log("=" * 80)
    log("TEST 2: Login with operator/operator")
    log("=" * 80)
    
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": OPERATOR_USERNAME, "password": OPERATOR_PASSWORD},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Expected 200, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        log(f"Response data: {data}")
        
        if "token" not in data:
            log("❌ FAIL: Missing 'token' field", "ERROR")
            return False
        
        if data.get("username") != "operator":
            log(f"❌ FAIL: Expected username='operator', got '{data.get('username')}'", "ERROR")
            return False
        
        if data.get("role") != "operator":
            log(f"❌ FAIL: Expected role='operator', got '{data.get('role')}'", "ERROR")
            return False
        
        OPERATOR_TOKEN = data["token"]
        log(f"✅ PASS: Operator login successful")
        log(f"  - Token: {OPERATOR_TOKEN[:30]}...")
        log(f"  - Username: {data['username']}")
        log(f"  - Role: {data['role']}")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_3_login_guest() -> bool:
    """Test 3: Login with guest/guest - expect 200, role=viewer"""
    global GUEST_TOKEN
    log("=" * 80)
    log("TEST 3: Login with guest/guest")
    log("=" * 80)
    
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": GUEST_USERNAME, "password": GUEST_PASSWORD},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Expected 200, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        log(f"Response data: {data}")
        
        if "token" not in data:
            log("❌ FAIL: Missing 'token' field", "ERROR")
            return False
        
        if data.get("username") != "guest":
            log(f"❌ FAIL: Expected username='guest', got '{data.get('username')}'", "ERROR")
            return False
        
        if data.get("role") != "viewer":
            log(f"❌ FAIL: Expected role='viewer', got '{data.get('role')}'", "ERROR")
            return False
        
        GUEST_TOKEN = data["token"]
        log(f"✅ PASS: Guest login successful")
        log(f"  - Token: {GUEST_TOKEN[:30]}...")
        log(f"  - Username: {data['username']}")
        log(f"  - Role: {data['role']}")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_4_login_wrong_password() -> bool:
    """Test 4: Login with wrong password - expect 401 with detail 'Invalid username or password'"""
    log("=" * 80)
    log("TEST 4: Login with wrong password")
    log("=" * 80)
    
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": "wrong"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 401:
            log(f"❌ FAIL: Expected 401, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        data = resp.json()
        log(f"Response data: {data}")
        
        detail = data.get("detail", "")
        if "Invalid username or password" not in detail:
            log(f"❌ FAIL: Expected detail 'Invalid username or password', got '{detail}'", "ERROR")
            return False
        
        log(f"✅ PASS: Wrong password correctly rejected with 401")
        log(f"  - Detail: {detail}")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_5_auth_me() -> bool:
    """Test 5: GET /api/auth/me with admin token - expect user object with username, role, actor"""
    log("=" * 80)
    log("TEST 5: GET /api/auth/me with admin token")
    log("=" * 80)
    
    if not ADMIN_TOKEN:
        log("❌ FAIL: Admin token not available (test 1 must pass first)", "ERROR")
        return False
    
    try:
        resp = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Expected 200, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        user = resp.json()
        log(f"Response data: {user}")
        
        # Check required fields
        if "username" not in user:
            log("❌ FAIL: Missing 'username' field", "ERROR")
            return False
        
        if "role" not in user:
            log("❌ FAIL: Missing 'role' field", "ERROR")
            return False
        
        if "actor" not in user:
            log("❌ FAIL: Missing 'actor' field", "ERROR")
            return False
        
        if user.get("username") != "admin":
            log(f"❌ FAIL: Expected username='admin', got '{user.get('username')}'", "ERROR")
            return False
        
        if user.get("role") != "admin":
            log(f"❌ FAIL: Expected role='admin', got '{user.get('role')}'", "ERROR")
            return False
        
        log(f"✅ PASS: /api/auth/me returned correct user object")
        log(f"  - Username: {user['username']}")
        log(f"  - Role: {user['role']}")
        log(f"  - Actor: {user['actor']}")
        log(f"  - Email: {user.get('email', 'N/A')}")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_6_rbac_users() -> bool:
    """Test 6: RBAC - GET /api/users as admin (200 with 3 users), as guest (403)"""
    log("=" * 80)
    log("TEST 6: RBAC - GET /api/users")
    log("=" * 80)
    
    if not ADMIN_TOKEN:
        log("❌ FAIL: Admin token not available", "ERROR")
        return False
    
    if not GUEST_TOKEN:
        log("❌ FAIL: Guest token not available", "ERROR")
        return False
    
    try:
        # Test 6a: Admin can access /api/users
        log("Test 6a: GET /api/users as admin (expect 200)")
        resp = requests.get(
            f"{BASE_URL}/users",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Expected 200, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        users = resp.json()
        log(f"Response data: {users}")
        
        if not isinstance(users, list):
            log(f"❌ FAIL: Expected list, got {type(users)}", "ERROR")
            return False
        
        # Check that we have 3 users (admin, operator, guest)
        if len(users) != 3:
            log(f"❌ FAIL: Expected 3 users, got {len(users)}", "ERROR")
            return False
        
        # Check that each user has a username field
        usernames = [u.get("username") for u in users]
        expected_usernames = ["admin", "operator", "guest"]
        
        for expected in expected_usernames:
            if expected not in usernames:
                log(f"❌ FAIL: Missing expected username '{expected}'", "ERROR")
                return False
        
        log(f"✅ PASS: Admin can access /api/users")
        log(f"  - Users: {usernames}")
        
        # Test 6b: Guest cannot access /api/users
        log("\nTest 6b: GET /api/users as guest (expect 403)")
        resp = requests.get(
            f"{BASE_URL}/users",
            headers={"Authorization": f"Bearer {GUEST_TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 403:
            log(f"❌ FAIL: Expected 403, got {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        log(f"✅ PASS: Guest correctly denied access with 403")
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def test_7_created_by_username() -> bool:
    """Test 7: Spot-check created_by uses username - create WO as admin, verify created_by='admin', then delete"""
    global TEST_WO_ID
    log("=" * 80)
    log("TEST 7: Spot-check created_by uses username")
    log("=" * 80)
    
    if not ADMIN_TOKEN:
        log("❌ FAIL: Admin token not available", "ERROR")
        return False
    
    try:
        # Step 1: Create a minimal work order as admin
        log("Step 1: Creating work order as admin...")
        wo_data = {
            "pelanggan": "AUTH TEST WO",
            "jenis_order": "PSB",
            "sa_id": f"AUTH_TEST_{TEST_RUN_ID}"
        }
        
        resp = requests.post(
            f"{BASE_URL}/workorders",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            json=wo_data,
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Work order creation failed with {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        wo = resp.json()
        TEST_WO_ID = wo.get("id")
        log(f"Work order created with ID: {TEST_WO_ID}")
        
        # Step 2: GET the work order and check created_by
        log("\nStep 2: Getting work order to verify created_by...")
        resp = requests.get(
            f"{BASE_URL}/workorders/{TEST_WO_ID}",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"❌ FAIL: Work order retrieval failed with {resp.status_code}", "ERROR")
            log(f"Response: {resp.text}", "ERROR")
            return False
        
        wo = resp.json()
        created_by = wo.get("created_by")
        log(f"Work order data: {wo}")
        log(f"created_by field: {created_by}")
        
        if created_by != "admin":
            log(f"❌ FAIL: Expected created_by='admin' (username), got '{created_by}'", "ERROR")
            return False
        
        log(f"✅ PASS: created_by correctly set to username 'admin'")
        
        # Step 3: Delete the work order to clean up
        log("\nStep 3: Deleting work order to clean up...")
        resp = requests.delete(
            f"{BASE_URL}/workorders/{TEST_WO_ID}",
            headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
            timeout=10
        )
        
        log(f"Response status: {resp.status_code}")
        
        if resp.status_code != 200:
            log(f"⚠️  WARNING: Work order deletion failed with {resp.status_code}", "WARN")
            log(f"Response: {resp.text}", "WARN")
            # Don't fail the test if cleanup fails
        else:
            log(f"✅ Work order deleted successfully")
        
        return True
        
    except Exception as e:
        log(f"❌ FAIL: Exception during test: {e}", "ERROR")
        return False


def main():
    """Run all auth refactor tests."""
    log("=" * 80)
    log("LA TRACKER AUTH REFACTOR TEST SUITE")
    log("=" * 80)
    log(f"Base URL: {BASE_URL}")
    log(f"Test Run ID: {TEST_RUN_ID}")
    log("")
    
    results = []
    
    # Run all tests in sequence
    tests = [
        ("Test 1: Login admin", test_1_login_admin),
        ("Test 2: Login operator", test_2_login_operator),
        ("Test 3: Login guest", test_3_login_guest),
        ("Test 4: Wrong password", test_4_login_wrong_password),
        ("Test 5: GET /api/auth/me", test_5_auth_me),
        ("Test 6: RBAC /api/users", test_6_rbac_users),
        ("Test 7: created_by username", test_7_created_by_username),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            log("")
        except Exception as e:
            log(f"❌ CRITICAL ERROR in {test_name}: {e}", "ERROR")
            results.append((test_name, False))
            log("")
    
    # Print summary
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log("")
    log(f"Total: {passed}/{total} tests passed")
    log("=" * 80)
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
