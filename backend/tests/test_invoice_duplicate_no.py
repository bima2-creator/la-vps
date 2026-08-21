"""Edge case: duplicate invoice_no should not surface as unhandled 500."""
import io
import os
import pytest
import requests
from dotenv import dotenv_values

env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or env["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE_URL}/api"


def make_pdf(text):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def ctx():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=60)
    assert r.status_code == 200, r.text[:200]
    tok = r.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    state = {"wo": None, "inv": None}
    yield s, state
    if state["inv"]:
        s.delete(f"{API}/invoices/{state['inv']}", timeout=60)
    if state["wo"]:
        s.delete(f"{API}/workorders/{state['wo']}", timeout=60)


def test_duplicate_invoice_no_returns_4xx(ctx):
    s, state = ctx
    wo = s.post(f"{API}/workorders", json={
        "pelanggan": "PT DUP TEST", "si_id": "SI-DUP-01", "jenis_order": "PSB",
        "wo_jenis_pekerjaan": "INSTALASI", "hasil_instalasi_status": "OK",
        "boq_jasa": 500000, "boq_jumlah": 500000,
    }, timeout=60)
    assert wo.status_code in (200, 201), wo.text[:300]
    state["wo"] = wo.json()["id"]
    s.post(f"{API}/workorders/{state['wo']}/attachments",
           files={"file": ("a.pdf", make_pdf("DUP"), "application/pdf")},
           data={"kind": "general"}, timeout=120)
    payload = {"pelanggans": ["PT DUP TEST"], "jenis_pekerjaan": "INSTALASI",
               "invoice_no": "INV-DUP-TEST-IT7", "work_order_ids": [state["wo"]],
               "tanggal": "2026-06-21"}
    r1 = s.post(f"{API}/invoices", json=payload, timeout=60)
    assert r1.status_code in (200, 201), r1.text[:300]
    state["inv"] = r1.json()["id"]
    r2 = s.post(f"{API}/invoices", json=payload, timeout=60)
    assert r2.status_code < 500, f"duplicate invoice_no returned {r2.status_code} (unhandled DuplicateKeyError): {r2.text[:200]}"
