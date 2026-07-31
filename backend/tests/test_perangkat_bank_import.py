"""Tests for Perangkat Bank Data XLSX import (iteration 4).

Covers:
 - RBAC on POST /api/perangkat/bank/import/xlsx and GET template.xlsx
 - Template download shape (200, .xlsx, columns)
 - Prefix-format import + idempotent re-import (skips all)
 - Registrasi-format import + learning (lookup returns nama for new serial with same prefix)
 - Bad file (no Prefix / no Nomor) -> 400
"""
import io
import os
import requests
import pandas as pd
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


def _login(u, p):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="session")
def operator_headers():
    return {"Authorization": f"Bearer {_login('operator', 'operator')}"}


@pytest.fixture(scope="session")
def guest_headers():
    return {"Authorization": f"Bearer {_login('guest', 'guest')}"}


# Test prefixes (12 chars). Kept unique to avoid collision with the ~83 seed rows.
IMP_PREFIX_1 = "TSTIMP0PRFX1"
IMP_PREFIX_2 = "TSTIMP0PRFX2"
IMP_PREFIX_3 = "TSTIMP0PRFX3"  # for registrasi mode

IMP_NAMA_1 = "TEST_IMPORT_ENTRY_1"
IMP_NAMA_2 = "TEST_IMPORT_ENTRY_2"
IMP_NAMA_3 = "TEST_IMPORT_REGISTRASI"


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name="Sheet1")
    buf.seek(0)
    return buf.read()


def _cleanup_prefix_like(admin_headers, needle):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": needle, "limit": 200},
                     headers=admin_headers, timeout=30)
    if r.status_code != 200:
        return
    for it in r.json().get("items", []):
        requests.delete(f"{BASE_URL}/api/perangkat/bank/{it['id']}", headers=admin_headers, timeout=30)


@pytest.fixture(scope="module", autouse=True)
def cleanup_around_module(admin_headers):
    for n in ("TSTIMP", "TEST_IMPORT"):
        _cleanup_prefix_like(admin_headers, n)
    yield
    for n in ("TSTIMP", "TEST_IMPORT"):
        _cleanup_prefix_like(admin_headers, n)


# ---------------- Template ----------------
def test_template_download_ok(admin_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/import/template.xlsx",
                     headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    ctype = r.headers.get("content-type", "")
    assert "spreadsheetml" in ctype or "officedocument" in ctype, ctype
    assert len(r.content) > 200
    assert r.content[:2] == b"PK"
    # Verify columns
    df = pd.read_excel(io.BytesIO(r.content))
    cols = [str(c).strip().lower() for c in df.columns]
    assert "prefix" in cols
    assert any("nama" in c for c in cols)


def test_template_rbac_operator_forbidden(operator_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/import/template.xlsx",
                     headers=operator_headers, timeout=30)
    assert r.status_code == 403


def test_template_rbac_guest_forbidden(guest_headers):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/import/template.xlsx",
                     headers=guest_headers, timeout=30)
    assert r.status_code == 403


# ---------------- RBAC on import ----------------
def _dummy_xlsx():
    return _xlsx_bytes(pd.DataFrame([{"Prefix": IMP_PREFIX_1, "Nama Perangkat": IMP_NAMA_1}]))


def test_import_rbac_operator_forbidden(operator_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=operator_headers,
        files={"file": ("test.xlsx", _dummy_xlsx(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r.status_code == 403


def test_import_rbac_guest_forbidden(guest_headers):
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=guest_headers,
        files={"file": ("test.xlsx", _dummy_xlsx(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r.status_code == 403


# ---------------- Prefix-format import ----------------
def test_import_prefix_format_success_and_idempotency(admin_headers):
    df = pd.DataFrame([
        {"Prefix": IMP_PREFIX_1, "Nama Perangkat": IMP_NAMA_1},
        {"Prefix": IMP_PREFIX_2, "Nama Perangkat": IMP_NAMA_2},
        {"Prefix": "SHORT", "Nama Perangkat": "BAD"},           # too short (5) -> error+skipped
        {"Prefix": "", "Nama Perangkat": "EMPTY_PREFIX"},        # empty -> skipped
    ])
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=admin_headers,
        files={"file": ("import.xlsx", _xlsx_bytes(df),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["mode"] == "prefix"
    assert data["imported"] == 2
    assert data["skipped"] >= 2
    assert isinstance(data["errors"], list) and any("SHORT" in e for e in data["errors"])

    # Verify persisted
    lst = requests.get(f"{BASE_URL}/api/perangkat/bank", params={"q": "TSTIMP"},
                       headers=admin_headers, timeout=30).json()["items"]
    prefixes = {it["prefix"] for it in lst}
    assert IMP_PREFIX_1 in prefixes and IMP_PREFIX_2 in prefixes

    # Idempotency: re-upload the same good rows -> imported == 0, all skipped as duplicates
    df_dup = pd.DataFrame([
        {"Prefix": IMP_PREFIX_1, "Nama Perangkat": IMP_NAMA_1},
        {"Prefix": IMP_PREFIX_2, "Nama Perangkat": IMP_NAMA_2},
    ])
    r2 = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=admin_headers,
        files={"file": ("import.xlsx", _xlsx_bytes(df_dup),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["mode"] == "prefix"
    assert d2["imported"] == 0
    assert d2["skipped"] == 2


# ---------------- Registrasi-format import + learning ----------------
def test_import_registrasi_format_and_lookup_learning(admin_headers):
    # Use unique prefix so learning creates it. 12-char prefix + 6-digit suffix = 18 chars.
    serial_a = IMP_PREFIX_3 + "000001"
    serial_b = IMP_PREFIX_3 + "000002"
    short_serial = "SHORT"  # <11 chars -> skipped
    df = pd.DataFrame([
        {"Nomor Registrasi": serial_a, "Nama Perangkat": IMP_NAMA_3},
        {"Nomor Registrasi": serial_b, "Nama Perangkat": IMP_NAMA_3},
        {"Nomor Registrasi": short_serial, "Nama Perangkat": "IGNORED"},
    ])
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=admin_headers,
        files={"file": ("reg.xlsx", _xlsx_bytes(df),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "registrasi"
    assert data["imported"] == 2
    assert data["skipped"] >= 1

    # Lookup a *new* serial with the same prefix -> should return the imported nama
    new_serial = IMP_PREFIX_3 + "999999"
    r_lu = requests.get(f"{BASE_URL}/api/perangkat/bank/lookup",
                        params={"nomor": new_serial}, headers=admin_headers, timeout=30)
    assert r_lu.status_code == 200, r_lu.text
    lu = r_lu.json()
    # Response shape may be {found, nama} or {matches:[...]} - handle both
    found_nama = lu.get("suggested") or lu.get("nama") or (
        lu.get("options", [{}])[0].get("nama") if lu.get("options") else None
    )
    assert found_nama == IMP_NAMA_3, f"Expected learned nama, got: {lu}"


# ---------------- Bad file ----------------
def test_import_bad_file_no_recognized_columns(admin_headers):
    df = pd.DataFrame([{"Foo": "bar", "Baz": "qux"}])
    r = requests.post(
        f"{BASE_URL}/api/perangkat/bank/import/xlsx",
        headers=admin_headers,
        files={"file": ("bad.xlsx", _xlsx_bytes(df),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        timeout=30,
    )
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert isinstance(detail, str) and len(detail) > 0
