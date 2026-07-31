"""Tests for the Perangkat Bank Data auto-detect feature."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def lookup(headers, nomor):
    r = requests.get(f"{BASE_URL}/api/perangkat/bank/lookup", params={"nomor": nomor}, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- Seed lookup tests ----------------
def test_lookup_canister_12char_fallback(headers):
    data = lookup(headers, "B2WS0100010305999")
    assert data["matched"] is True
    assert data["ambiguous"] is False
    assert data["suggested"] == "CANISTER 1.8 DIAMETER 4 INCHI"


def test_lookup_evolution_router(headers):
    data = lookup(headers, "B2WS02A7020109999")
    assert data["matched"] is True
    assert data["suggested"] == "EVOLUTION X3 SATELLITE ROUTER ( PN - )"


def test_lookup_antenna_prodelin(headers):
    data = lookup(headers, "B2WS010Q010199999")
    assert data["matched"] is True
    assert data["suggested"] == "ANTENNA/REFLECTOR 1.8 PRODELIN"


def test_lookup_lnb_cband(headers):
    data = lookup(headers, "B2WS0100010I99999")
    assert data["matched"] is True
    assert data["suggested"] == "LNB,C-BAND LS EXTD BAND ( PN - 1024573-0001 )"


def test_lookup_ambiguous_remote_modem(headers):
    data = lookup(headers, "B2WS020O011609999")
    assert data["matched"] is True
    assert data["ambiguous"] is True
    names = {o["nama"] for o in data["options"]}
    assert "REMOTE HX50-IDU- C-BAND HUGHES" in names
    assert "MODEM HX50" in names


def test_lookup_unknown_prefix(headers):
    data = lookup(headers, "ZZZZ00000000")
    assert data["matched"] is False
    assert data["options"] == []


def test_lookup_too_short(headers):
    data = lookup(headers, "ABC123")
    assert data["matched"] is False


# ---------------- Learning test ----------------
def test_learning_persists_from_workorder(headers):
    sa_id = "TEST-SA-BANK-LEARN"
    new_nama = "TEST DEVICE XYZ"
    new_nomor = "QWERTYUIOP123456"
    payload = {
        "pelanggan": "TEST_BANK_LEARN",
        "alamat": "TEST",
        "sa_id": sa_id,
        "bw": "1",
        "perangkat_items": [{"nama_perangkat": new_nama, "nomor_registrasi": new_nomor}],
    }
    r = requests.post(f"{BASE_URL}/api/workorders", headers=headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), r.text
    wo_id = r.json().get("id") or r.json().get("_id")

    # Small delay for eventual consistency
    time.sleep(0.5)

    # Query with a nomor sharing 13-char prefix
    data = lookup(headers, "QWERTYUIOP123999")
    assert data["matched"] is True, data
    assert data["suggested"] == new_nama

    # Cleanup: delete the workorder we created
    if wo_id:
        requests.delete(f"{BASE_URL}/api/workorders/{wo_id}", headers=headers, timeout=30)
