"""Tests for GET /api/perangkat/registry nama resolution fix (nama_perangkat + bank fallback)."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

CREATED_WO_IDS = []


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("access_token")
    assert token, "no access_token in login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    yield s
    for wo_id in CREATED_WO_IDS:
        try:
            s.delete(f"{BASE_URL}/api/workorders/{wo_id}", timeout=30)
        except Exception:
            pass


def _create_wo(client, items, pelanggan):
    payload = {
        "pelanggan": pelanggan,
        "jenis_order": "PSB",
        "wo_jenis_pekerjaan": "INSTALASI",
        "sa_id": f"TESTSA-{uuid.uuid4().hex[:8]}",
        "perangkat_items": items,
    }
    r = client.post(f"{BASE_URL}/api/workorders", json=payload, timeout=60)
    assert r.status_code in (200, 201), f"create WO failed {r.status_code}: {r.text[:400]}"
    data = r.json()
    wo_id = data.get("id") or data.get("_id")
    assert wo_id, f"no id in create response: {data}"
    CREATED_WO_IDS.append(wo_id)
    return wo_id


def _registry(client, q):
    r = client.get(f"{BASE_URL}/api/perangkat/registry", params={"q": q}, timeout=60)
    assert r.status_code == 200, f"registry failed {r.status_code}: {r.text[:300]}"
    return r.json()


# Test 1: nama read from perangkat_items[].nama_perangkat
def test_registry_nama_from_nama_perangkat(client):
    nr = "TESTREG1234567890"
    _create_wo(client, [{"nomor_registrasi": nr, "nama_perangkat": "ROUTER TEST ABC", "role": ""}], "TEST_PELANGGAN_A")
    data = _registry(client, "TESTREG")
    items = data["items"]
    match = [d for d in items if d["nomor_registrasi"] == nr]
    assert match, f"device {nr} not found in registry; items={[d['nomor_registrasi'] for d in items]}"
    dev = match[0]
    assert dev["nama"] == "ROUTER TEST ABC", f"expected nama 'ROUTER TEST ABC', got {dev['nama']!r}"
    assert dev["wo_count"] >= 1
    assert dev["latest_pelanggan"] == "TEST_PELANGGAN_A"
    assert "_id" not in dev


# Test 2: nama fallback from perangkat_bank by 13-char prefix
def test_registry_nama_fallback_from_bank(client):
    r = client.get(f"{BASE_URL}/api/perangkat/bank", params={"page_size": 5}, timeout=60)
    assert r.status_code == 200, f"bank failed {r.status_code}: {r.text[:300]}"
    bank_items = r.json().get("items") or []
    if not bank_items:
        pytest.skip("perangkat_bank is empty - cannot test bank fallback")
    entry = bank_items[0]
    prefix = entry.get("prefix")
    expected_names = entry.get("nama") or entry.get("nama_list") or entry.get("names")
    assert prefix and len(prefix) == 13, f"unexpected bank prefix: {entry}"
    nr = f"{prefix}XX99"
    _create_wo(client, [{"nomor_registrasi": nr, "nama_perangkat": "", "role": ""}], "TEST_PELANGGAN_B")
    data = _registry(client, prefix)
    match = [d for d in data["items"] if d["nomor_registrasi"] == nr]
    assert match, f"device {nr} not found in registry"
    nama = match[0]["nama"]
    assert nama, f"nama empty; bank fallback did not resolve for prefix {prefix} (bank entry={entry})"
    print(f"bank fallback resolved nama={nama!r} (bank entry nama={expected_names!r})")


# Test 5 (regression): CSV export still works and includes nama
def test_export_csv_has_nama(client):
    r = client.get(f"{BASE_URL}/api/perangkat/export/csv", timeout=90)
    assert r.status_code == 200, f"csv export failed {r.status_code}: {r.text[:300]}"
    text = r.text
    assert "Nomor Registrasi" in text and "Nama Perangkat" in text
    lines = [l for l in text.splitlines() if l.strip()]
    assert len(lines) > 1, "csv has no data rows"
    # at least one row must have a non-empty nama column
    non_empty = 0
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > 1 and parts[1].strip().strip('"'):
            non_empty += 1
    assert non_empty > 0, "no rows with non-empty Nama Perangkat in csv"
    print(f"csv rows={len(lines)-1}, rows_with_nama={non_empty}")


# Sanity: existing known device still resolves nama
def test_existing_device_has_nama(client):
    data = _registry(client, "B2WS0200023MA0580")
    items = data["items"]
    if not items:
        pytest.skip("known device B2WS0200023MA0580 not in DB")
    assert items[0]["nama"], f"existing device nama empty: {items[0]}"
    print(f"existing device nama={items[0]['nama']!r}")


def test_cleanup_deletes_test_wos(client):
    # delete created WOs and verify they no longer appear in registry
    for wo_id in list(CREATED_WO_IDS):
        r = client.delete(f"{BASE_URL}/api/workorders/{wo_id}", timeout=60)
        assert r.status_code in (200, 204, 404), f"delete failed {r.status_code}: {r.text[:200]}"
        CREATED_WO_IDS.remove(wo_id)
    data = _registry(client, "TESTREG1234567890")
    assert not [d for d in data["items"] if d["nomor_registrasi"] == "TESTREG1234567890"], "test device still present after delete"
