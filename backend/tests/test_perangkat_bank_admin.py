"""Tests for the Perangkat Bank Data admin CRUD + Export + RBAC (iteration 3)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


def _login(username, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def operator_headers():
    return {"Authorization": f"Bearer {_login('operator', 'operator')}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def guest_headers():
    return {"Authorization": f"Bearer {_login('guest', 'guest')}", "Content-Type": "application/json"}


# -------------- List / KPI --------------
def test_list_returns_items_and_kpi(admin_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and isinstance(data["items"], list)
    assert "kpi" in data
    kpi = data["kpi"]
    for k in ("total_entries", "total_prefixes", "total_namas"):
        assert k in kpi
    assert kpi["total_entries"] > 0


def test_list_search_by_prefix(admin_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": "B2WS01"}, headers=admin_headers, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) > 0
    assert all(("B2WS01" in (it["prefix"] or "").upper()) or ("b2ws01" in (it["nama"] or "").lower()) for it in items)


def test_list_search_by_nama_case_insensitive(admin_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": "canister"}, headers=admin_headers, timeout=30)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("CANISTER" in it["nama"].upper() for it in items)


# -------------- RBAC --------------
def test_rbac_operator_forbidden_on_list(operator_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", headers=operator_headers, timeout=30)
    assert r.status_code == 403, r.status_code


def test_rbac_guest_forbidden_on_list(guest_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", headers=guest_headers, timeout=30)
    assert r.status_code == 403


def test_rbac_operator_forbidden_on_create(operator_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=operator_headers,
        json={"prefix": "TEST12345678", "nama": "TEST_RBAC"},
        timeout=30,
    )
    assert r.status_code == 403


def test_rbac_operator_forbidden_on_export(operator_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/export/xlsx", headers=operator_headers, timeout=30)
    assert r.status_code == 403


# -------------- Create validation --------------
def test_create_rejects_short_prefix(admin_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": "SHORT", "nama": "TEST_SHORT"},
        timeout=30,
    )
    assert r.status_code == 400


def test_create_rejects_long_prefix(admin_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": "THISISWAYTOOLONGPREFIX", "nama": "TEST_LONG"},
        timeout=30,
    )
    assert r.status_code == 400


def test_create_rejects_empty_nama(admin_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": "TESTPREFIX01", "nama": "   "},
        timeout=30,
    )
    assert r.status_code == 400


# -------------- CRUD happy path + idempotency + merge --------------
TEST_PREFIX_A = "TESTPREFIXA1"   # 12 chars
TEST_PREFIX_B = "TESTPREFIXB1"   # 12 chars
TEST_NAMA = "TEST_BANK_ENTRY"
TEST_NAMA_2 = "TEST_BANK_ENTRY_2"


@pytest.fixture(scope="module")
def created_entry(admin_headers):
    # ensure clean
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": "TESTPREFIX"}, headers=admin_headers, timeout=30)
    for it in r.json().get("items", []):
        requests.delete(f"{BASE_URL}/api/perangkat/bank/{it['id']}", headers=admin_headers, timeout=30)

    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": TEST_PREFIX_A, "nama": TEST_NAMA},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["prefix"] == TEST_PREFIX_A
    assert data["nama"] == TEST_NAMA
    assert data["plen"] == 12
    yield data
    # cleanup all TEST_ prefixed entries
    lst = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": "TESTPREFIX"}, headers=admin_headers, timeout=30).json().get("items", [])
    for it in lst:
        requests.delete(f"{BASE_URL}/api/perangkat/bank/{it['id']}", headers=admin_headers, timeout=30)


def test_create_idempotent(admin_headers, created_entry):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": TEST_PREFIX_A, "nama": TEST_NAMA},
        timeout=30,
    )
    assert r.status_code == 200
    assert r.json()["id"] == created_entry["id"]


def test_update_nama(admin_headers, created_entry):
    r = requests.put(
        f"{BASE_URL}/api/perangkat/bank/{created_entry['id']}",
        headers=admin_headers,
        json={"nama": TEST_NAMA_2},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    assert r.json()["nama"] == TEST_NAMA_2
    # verify GET
    lst = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": TEST_NAMA_2}, headers=admin_headers, timeout=30).json()["items"]
    assert any(it["id"] == created_entry["id"] and it["nama"] == TEST_NAMA_2 for it in lst)
    # revert
    requests.put(
        f"{BASE_URL}/api/perangkat/bank/{created_entry['id']}",
        headers=admin_headers,
        json={"nama": TEST_NAMA},
        timeout=30,
    )


def test_update_merge(admin_headers, created_entry):
    # create a second entry (different prefix, same nama family)
    r2 = requests.post(
        f"{BASE_URL}/api/perangkat/bank",
        headers=admin_headers,
        json={"prefix": TEST_PREFIX_B, "nama": TEST_NAMA},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    e2 = r2.json()
    # update e2 to have the same (prefix, plen, nama) as created_entry -> should merge
    r = requests.put(
        f"{BASE_URL}/api/perangkat/bank/{e2['id']}",
        headers=admin_headers,
        json={"prefix": TEST_PREFIX_A, "nama": TEST_NAMA},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("merged") is True
    assert data["id"] == created_entry["id"]
    # e2 should be gone
    r_del = requests.delete(f"{BASE_URL}/api/perangkat/bank/{e2['id']}", headers=admin_headers, timeout=30)
    assert r_del.status_code == 404


def test_delete_missing_returns_404(admin_headers):
    fake_id = "0" * 24
    r = requests.delete(f"{BASE_URL}/api/perangkat/bank/{fake_id}", headers=admin_headers, timeout=30)
    assert r.status_code == 404


# -------------- Export --------------
def test_export_xlsx(admin_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/export/xlsx", headers=admin_headers, timeout=60)
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "spreadsheetml" in ctype or "officedocument" in ctype, ctype
    assert len(r.content) > 200
    # xlsx is a zip file -> starts with PK
    assert r.content[:2] == b"PK"
