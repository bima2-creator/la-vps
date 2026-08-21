"""Invoice NON_MAINTENANCE combined-category tests (iteration 8).

Rule under test: WO Survey/Instalasi/Aktivasi/Dismantle may be combined in ONE
invoice with jenis_pekerjaan=NON_MAINTENANCE. MAINTENANCE invoices must only
contain MAINTENANCE work orders.
"""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

PELANGGAN = "PT GABUNG TEST"
PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.fail(f"Admin login failed: {r.status_code} {r.text[:300]}")
    token = r.json().get("access_token") or r.json().get("token")
    assert token, "no access_token in login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def state():
    return {"wos": {}, "invoices": []}


@pytest.fixture(scope="module", autouse=True)
def cleanup(client, state):
    yield
    for inv_id in state["invoices"]:
        client.delete(f"{BASE_URL}/api/invoices/{inv_id}")
    for wid in state["wos"].values():
        client.delete(f"{BASE_URL}/api/workorders/{wid}")


def _create_wo(client, payload):
    r = client.post(f"{BASE_URL}/api/workorders", json=payload)
    assert r.status_code in (200, 201), f"WO create failed {r.status_code}: {r.text[:400]}"
    d = r.json()
    assert "_id" not in d
    return d["id"]


# --- SETUP: create 3 WOs with attachments ---
def test_setup_workorders(client, state):
    specs = {
        "A": {"si_id": "SI-GAB-01", "jenis_order": "PSB", "hasil_instalasi_status": "OK",
              "boq_jasa": 1000000, "boq_jumlah": 1000000},
        "B": {"si_id": "SI-GAB-02", "jenis_order": "DISMANTLE", "hasil_survey_status": "OK",
              "boq_jasa": 500000, "boq_jumlah": 500000},
        "C": {"si_id": "SI-GAB-03", "jenis_order": "MAINTENANCE", "hasil_survey_status": "OK",
              "boq_jasa": 300000, "boq_jumlah": 300000},
    }
    for key, extra in specs.items():
        payload = {"pelanggan": PELANGGAN, **extra}
        wid = _create_wo(client, payload)
        state["wos"][key] = wid
        files = {"file": (f"TEST_{key}.pdf", PDF_BYTES, "application/pdf")}
        r = client.post(f"{BASE_URL}/api/workorders/{wid}/attachments",
                        files=files, data={"kind": "general"})
        assert r.status_code in (200, 201), f"attachment upload failed {r.status_code}: {r.text[:300]}"
        lst = client.get(f"{BASE_URL}/api/workorders/{wid}/attachments")
        assert lst.status_code == 200
        assert len(lst.json()) >= 1
    assert len(state["wos"]) == 3


# --- Test 1: candidates for NON_MAINTENANCE ---
def test_candidates_non_maintenance(client, state):
    r = client.get(f"{BASE_URL}/api/invoices/candidates",
                   params={"jenis_pekerjaan": "NON_MAINTENANCE", "pelanggans": PELANGGAN})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    ids = {str(i.get("id")) for i in items}
    assert state["wos"]["A"] in ids, "PSB WO missing from NON_MAINTENANCE candidates"
    assert state["wos"]["B"] in ids, "DISMANTLE WO missing from NON_MAINTENANCE candidates"
    assert state["wos"]["C"] not in ids, "MAINTENANCE WO must NOT appear in NON_MAINTENANCE candidates"


def test_customers_non_maintenance(client, state):
    r = client.get(f"{BASE_URL}/api/invoices/customers", params={"jenis_pekerjaan": "NON_MAINTENANCE"})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    names = {i.get("pelanggan") if isinstance(i, dict) else i for i in items}
    assert PELANGGAN in names


# --- Test 2: combine PSB + DISMANTLE in one NON_MAINTENANCE invoice ---
def test_create_combined_invoice(client, state):
    payload = {
        "pelanggans": [PELANGGAN],
        "jenis_pekerjaan": "NON_MAINTENANCE",
        "invoice_no": "INV-GAB-TEST",
        "work_order_ids": [state["wos"]["A"], state["wos"]["B"]],
        "tanggal": "2026-06-21",
    }
    r = client.post(f"{BASE_URL}/api/invoices", json=payload)
    assert r.status_code == 200, f"combined invoice rejected {r.status_code}: {r.text[:400]}"
    d = r.json()
    state["invoices"].append(d["id"])
    assert d["jenis_pekerjaan"] == "NON_MAINTENANCE"
    assert set(d["work_order_ids"]) == {state["wos"]["A"], state["wos"]["B"]}
    assert float(d["grand_total"]) == 1500000.0
    assert "_id" not in d
    # verify persistence
    g = client.get(f"{BASE_URL}/api/invoices/{d['id']}")
    assert g.status_code == 200
    gd = g.json()
    assert gd["invoice_no"] == "INV-GAB-TEST"
    assert len(gd["work_order_ids"]) == 2


# --- Test 3a: MAINTENANCE invoice with a non-maintenance WO must be rejected ---
def test_maintenance_invoice_rejects_non_maintenance_wo(client, state):
    payload = {
        "pelanggans": [PELANGGAN],
        "jenis_pekerjaan": "MAINTENANCE",
        "invoice_no": "INV-MAINT-BAD",
        "work_order_ids": [state["wos"]["A"]],
        "tanggal": "2026-06-21",
    }
    r = client.post(f"{BASE_URL}/api/invoices", json=payload)
    if r.status_code == 200:
        state["invoices"].append(r.json()["id"])
    assert r.status_code == 400, (
        f"Expected 400 rejecting PSB WO in MAINTENANCE invoice, got {r.status_code}: {r.text[:300]}"
    )


# --- Test 3b: valid MAINTENANCE invoice ---
def test_create_maintenance_invoice(client, state):
    payload = {
        "pelanggans": [PELANGGAN],
        "jenis_pekerjaan": "MAINTENANCE",
        "invoice_no": "INV-MAINT-TEST",
        "work_order_ids": [state["wos"]["C"]],
        "tanggal": "2026-06-21",
    }
    r = client.post(f"{BASE_URL}/api/invoices", json=payload)
    assert r.status_code == 200, f"maintenance invoice failed {r.status_code}: {r.text[:400]}"
    d = r.json()
    state["invoices"].append(d["id"])
    assert float(d["grand_total"]) == 300000.0


# --- Duplicate invoice_no should be 409 ---
def test_duplicate_invoice_no_conflict(client, state):
    # WO baru (belum ter-invoice) agar tidak tertahan guard double-billing (400)
    wid = _create_wo(client, {"pelanggan": PELANGGAN, "si_id": "SI-GAB-04",
                              "jenis_order": "MAINTENANCE", "hasil_survey_status": "OK",
                              "boq_jasa": 100000, "boq_jumlah": 100000})
    state["wos"]["D"] = wid
    files = {"file": ("TEST_D.pdf", PDF_BYTES, "application/pdf")}
    client.post(f"{BASE_URL}/api/workorders/{wid}/attachments", files=files, data={"kind": "general"})
    payload = {
        "pelanggans": [PELANGGAN],
        "jenis_pekerjaan": "MAINTENANCE",
        "invoice_no": "INV-MAINT-TEST",
        "work_order_ids": [wid],
        "tanggal": "2026-06-21",
    }
    r = client.post(f"{BASE_URL}/api/invoices", json=payload)
    if r.status_code == 200:
        state["invoices"].append(r.json()["id"])
    assert r.status_code == 409, f"expected 409 duplicate, got {r.status_code}: {r.text[:300]}"


# --- Guard baru: WO yang sudah ter-invoice ditolak 400 saat dipakai lagi ---
def test_reused_wo_rejected(client, state):
    payload = {
        "pelanggans": [PELANGGAN],
        "jenis_pekerjaan": "MAINTENANCE",
        "invoice_no": "INV-MAINT-DOUBLE",
        "work_order_ids": [state["wos"]["C"]],
        "tanggal": "2026-06-21",
    }
    r = client.post(f"{BASE_URL}/api/invoices", json=payload)
    if r.status_code == 200:
        state["invoices"].append(r.json()["id"])
    assert r.status_code == 400, f"expected 400 double-billing, got {r.status_code}: {r.text[:300]}"
    assert "dipakai" in r.text.lower()


# --- Candidates should exclude already-invoiced WOs ---
def test_candidates_exclude_invoiced(client, state):
    r = client.get(f"{BASE_URL}/api/invoices/candidates",
                   params={"jenis_pekerjaan": "NON_MAINTENANCE", "pelanggans": PELANGGAN})
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    ids = {str(i.get("id")) for i in items}
    assert state["wos"]["A"] not in ids, "already-invoiced WO still offered as candidate"
    assert state["wos"]["B"] not in ids, "already-invoiced WO still offered as candidate"


# --- Invalid jenis_pekerjaan ---
def test_invalid_jenis_pekerjaan(client, state):
    r = client.post(f"{BASE_URL}/api/invoices", json={
        "pelanggans": [PELANGGAN], "jenis_pekerjaan": "BOGUS",
        "invoice_no": "INV-BOGUS-TEST", "work_order_ids": [state["wos"]["C"]]})
    if r.status_code == 200:
        state["invoices"].append(r.json()["id"])
    assert r.status_code == 400
