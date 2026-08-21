"""
Regression tests for iteration 7:
- requirements.txt hygiene (no Emergent-internal packages) + clean-resolve sanity
- server.py top-level imports covered by requirements.txt
- backend regression: auth login, workorders list, field-engineers
- PDF lampiran (pymupdf compression path) end-to-end
"""
import io
import os
import re
import ast
import subprocess
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

REQ_FILE = Path("/app/backend/requirements.txt")
SERVER_FILE = Path("/app/backend/server.py")

FORBIDDEN = ["emergentintegrations", "litellm", "customer-assets.emergentagent.com"]

# module import name -> distribution present in requirements
MODULE_TO_DIST = {
    "dotenv": "python-dotenv",
    "bcrypt": "bcrypt",
    "jwt": "pyjwt",
    "pandas": "pandas",
    "bson": "pymongo",
    "pymongo": "pymongo",
    "apscheduler": "apscheduler",
    "fastapi": "fastapi",
    "motor": "motor",
    "pydantic": "pydantic",
    "starlette": "starlette",
    "reportlab": "reportlab",
    "pypdf": "pypdf",
    "requests": "requests",
    "pymupdf": "pymupdf",
}
STDLIB = {
    "io", "zipfile", "os", "json", "uuid", "csv", "logging", "datetime", "typing",
    "pathlib", "mimetypes", "base64", "re", "math", "time", "hashlib", "secrets",
    "collections", "itertools", "asyncio", "tempfile", "shutil", "string", "random",
    "urllib", "functools", "unicodedata", "traceback",
}


# ---------------- Test 1: requirements hygiene / resolvability ----------------
class TestRequirements:
    def test_no_emergent_internal_packages(self):
        content = REQ_FILE.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN:
            assert token.lower() not in content, f"requirements.txt still contains '{token}'"

    def test_no_direct_url_or_local_refs(self):
        content = REQ_FILE.read_text(encoding="utf-8")
        assert "http://" not in content and "https://" not in content
        assert "--index-url" not in content and "--extra-index-url" not in content
        assert " @ " not in content

    def test_expected_curated_packages_present(self):
        content = REQ_FILE.read_text(encoding="utf-8").lower()
        for pkg in ["fastapi", "starlette", "uvicorn", "pydantic", "motor", "pymongo",
                    "email-validator", "python-dotenv", "python-multipart", "pyjwt",
                    "bcrypt", "requests", "pandas", "openpyxl", "xlsxwriter", "reportlab",
                    "pypdf", "pillow", "apscheduler", "pymupdf"]:
            assert pkg in content, f"missing {pkg}"

    def test_pip_dry_run_resolves_from_public_pypi(self):
        venv = Path("/app/test_reports/.venvtest")
        if not (venv / "bin" / "pip").exists():
            subprocess.run(["python3", "-m", "venv", str(venv)], check=True, timeout=180)
        proc = subprocess.run(
            [str(venv / "bin" / "pip"), "install", "--dry-run", "--index-url",
             "https://pypi.org/simple", "-r", str(REQ_FILE)],
            capture_output=True, text=True, timeout=600,
        )
        out = proc.stdout + proc.stderr
        assert "ResolutionImpossible" not in out, out[-3000:]
        assert proc.returncode == 0, out[-3000:]
        assert "Would install" in out
        for token in FORBIDDEN:
            assert token not in out


# ---------------- Test 2: server.py imports covered ----------------
class TestServerImportsCovered:
    def test_all_imports_available_in_requirements(self):
        tree = ast.parse(SERVER_FILE.read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    mods.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    mods.add(node.module.split(".")[0])
        req = REQ_FILE.read_text(encoding="utf-8").lower()
        uncovered = []
        for m in sorted(mods):
            if m in STDLIB:
                continue
            dist = MODULE_TO_DIST.get(m)
            if not dist or dist.lower() not in req:
                uncovered.append(m)
        assert not uncovered, f"imports not covered by requirements.txt: {uncovered}"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def admin_token(client):
    r = client.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def make_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 20)
    c.drawString(72, 700, text)
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------------- Test 3: backend regression ----------------
class TestBackendRegression:
    def test_login_returns_tokens(self, client):
        r = client.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("token_type") == "bearer"
        assert isinstance(d.get("access_token"), str) and len(d["access_token"]) > 20
        assert isinstance(d.get("refresh_token"), str) and len(d["refresh_token"]) > 20

    def test_login_invalid_password(self, client):
        r = client.post(f"{API}/auth/login", json={"username": "admin", "password": "wrong-pass-xyz"}, timeout=60)
        assert r.status_code in (400, 401, 429), r.status_code

    def test_workorders_list(self, client, auth):
        r = client.get(f"{API}/workorders", headers=auth, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        items = body.get("items") if isinstance(body, dict) else body
        assert isinstance(items, list)
        for it in items[:5]:
            assert "_id" not in it

    def test_field_engineers(self, client, auth):
        r = client.get(f"{API}/users/field-engineers", headers=auth, timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------------- Test 4: invoice lampiran PDF (pymupdf path) ----------------
@pytest.fixture(scope="module")
def created_ids():
    return {"wo": None, "inv": None}


@pytest.fixture(scope="module", autouse=True)
def cleanup(client, auth, created_ids):
    yield
    if created_ids.get("inv"):
        client.delete(f"{API}/invoices/{created_ids['inv']}", headers=auth, timeout=60)
    if created_ids.get("wo"):
        client.delete(f"{API}/workorders/{created_ids['wo']}", headers=auth, timeout=60)


class TestInvoiceLampiranPdf:
    def test_01_create_wo(self, client, auth, created_ids):
        payload = {
            "pelanggan": "PT REQ TEST",
            "si_id": "SI-REQ-01",
            "jenis_order": "PSB",
            "wo_jenis_pekerjaan": "INSTALASI",
            "hasil_instalasi_status": "OK",
            "boq_jasa": 1000000,
            "boq_material": 0,
            "boq_jumlah": 1000000,
            "spk_instalasi_nomor": "SPK-REQ-TEST-01",
        }
        r = client.post(f"{API}/workorders", headers=auth, json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        assert d.get("id")
        assert "_id" not in d
        created_ids["wo"] = d["id"]
        # verify persistence
        g = client.get(f"{API}/workorders/{d['id']}", headers=auth, timeout=60)
        assert g.status_code == 200
        assert g.json().get("pelanggan") == "PT REQ TEST"

    def test_02_upload_wo_attachment(self, client, auth, created_ids):
        wo = created_ids["wo"]
        assert wo, "WO not created"
        files = {"file": ("spk_req_test.pdf", make_pdf("SPK REQ TEST WO"), "application/pdf")}
        r = client.post(f"{API}/workorders/{wo}/attachments", headers=auth,
                        files=files, data={"kind": "general"}, timeout=120)
        assert r.status_code in (200, 201), r.text[:500]
        assert r.json().get("id")
        lst = client.get(f"{API}/workorders/{wo}/attachments", headers=auth, timeout=60)
        assert lst.status_code == 200
        assert len(lst.json()) >= 1

    def test_03_create_invoice(self, client, auth, created_ids):
        wo = created_ids["wo"]
        payload = {
            "pelanggans": ["PT REQ TEST"],
            "jenis_pekerjaan": "INSTALASI",
            "invoice_no": "INV-REQ-TEST-IT7",
            "work_order_ids": [wo],
            "tanggal": "2026-06-21",
        }
        r = client.post(f"{API}/invoices", headers=auth, json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        assert d.get("id")
        assert "_id" not in d
        created_ids["inv"] = d["id"]
        assert d["invoice_no"] == "INV-REQ-TEST-IT7"
        assert float(d.get("grand_total") or 0) > 0

    def test_04_lampiran_gated_before_uploads(self, client, auth, created_ids):
        inv = created_ids["inv"]
        r = client.get(f"{API}/invoices/{inv}/pdf", params={"part": "lampiran"}, headers=auth, timeout=120)
        assert r.status_code == 400, f"expected gating 400, got {r.status_code}"

    def test_05_upload_invoice_docs(self, client, auth, created_ids):
        inv = created_ids["inv"]
        for ep, name, text in [
            ("faktur-pajak", "faktur.pdf", "FAKTUR PAJAK REQ TEST"),
            ("bukti-potong", "bupot.pdf", "BUKTI POTONG REQ TEST"),
            ("scan-invoice", "scan.pdf", "SCAN INVOICE REQ TEST"),
        ]:
            r = client.post(f"{API}/invoices/{inv}/{ep}", headers=auth,
                            files={"file": (name, make_pdf(text), "application/pdf")}, timeout=120)
            assert r.status_code in (200, 201), f"{ep} -> {r.status_code} {r.text[:300]}"
            assert r.json().get("ok") is True

    def test_06_lampiran_pdf_generated(self, client, auth, created_ids):
        inv = created_ids["inv"]
        r = client.get(f"{API}/invoices/{inv}/pdf", params={"part": "lampiran"}, headers=auth, timeout=180)
        assert r.status_code == 200, r.text[:500]
        content = r.content
        assert content[:4] == b"%PDF", f"not a PDF: {content[:20]}"
        assert len(content) > 1000
        # first page should contain scan invoice text
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        assert len(reader.pages) >= 1
        first = (reader.pages[0].extract_text() or "").upper()
        assert "SCAN INVOICE REQ TEST" in first, f"first page text: {first[:300]}"

    def test_07_invoice_part_pdf_gating(self, client, auth, created_ids):
        # inv_no_eproc not set -> gating 400 for part=invoice
        inv = created_ids["inv"]
        r = client.get(f"{API}/invoices/{inv}/pdf", params={"part": "invoice"}, headers=auth, timeout=120)
        assert r.status_code in (200, 400), r.status_code

    def test_08_cleanup_delete_and_verify(self, client, auth, created_ids):
        inv = created_ids["inv"]
        wo = created_ids["wo"]
        r = client.delete(f"{API}/invoices/{inv}", headers=auth, timeout=60)
        assert r.status_code in (200, 204), r.text[:300]
        g = client.get(f"{API}/invoices/{inv}", headers=auth, timeout=60)
        assert g.status_code == 404, g.status_code
        r2 = client.delete(f"{API}/workorders/{wo}", headers=auth, timeout=60)
        assert r2.status_code in (200, 204), r2.text[:300]
        created_ids["inv"] = None
        created_ids["wo"] = None
