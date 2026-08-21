"""Iteration 9 — Invoice lampiran PDF page-size normalization (A4) e2e tests.

Bug: pages in GET /api/invoices/{id}/pdf?part=lampiran had mixed page sizes
because uploaded scans had different dimensions.
Fix under test: _compress_pdf_bytes normalizes every page to A4 (595x842pt,
landscape pages -> 842x595) with proportional centered fit + image compression.
"""
import io
import os
import random

import pytest
import requests
from dotenv import dotenv_values

pymupdf = pytest.importorskip("pymupdf")

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

PELANGGAN = "PT UKURAN TEST"
INVOICE_NO = "INV-UKR-TEST"
TOL = 1.0


# ---------------- helpers: build PDFs with explicit page sizes ----------------
def make_sized_pdf(text: str, width: float, height: float, noise_image: bool = False) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    if noise_image:
        # large random-noise image -> incompressible unless rewrite_images runs
        w = h = 900
        buf = bytearray(random.getrandbits(8) for _ in range(w * h * 3))
        pix = pymupdf.Pixmap(pymupdf.csRGB, w, h, bytes(buf), False)
        page.insert_image(pymupdf.Rect(0, height * 0.25, width, height), pixmap=pix)
    page.insert_text((20, 60), text, fontsize=36)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"Admin login failed: {r.status_code} {r.text[:300]}")
    token = r.json().get("access_token") or r.json().get("token")
    assert token, "no access_token in login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def state():
    return {"wo": None, "inv": None, "input_bytes": 0, "lampiran": None}


@pytest.fixture(scope="module", autouse=True)
def cleanup(client, state):
    yield
    if state.get("inv"):
        client.delete(f"{API}/invoices/{state['inv']}", timeout=60)
    if state.get("wo"):
        client.delete(f"{API}/workorders/{state['wo']}", timeout=60)


class TestLampiranPageSizeNormalization:
    def test_01_setup_wo(self, client, state):
        payload = {
            "pelanggan": PELANGGAN,
            "si_id": "SI-UKR-01",
            "jenis_order": "PSB",
            "wo_jenis_pekerjaan": "INSTALASI",
            "hasil_instalasi_status": "OK",
            "boq_jasa": 1000000,
            "boq_material": 0,
            "boq_jumlah": 1000000,
        }
        r = client.post(f"{API}/workorders", json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        assert d.get("id") and "_id" not in d
        state["wo"] = d["id"]
        g = client.get(f"{API}/workorders/{d['id']}", timeout=60)
        assert g.status_code == 200
        assert g.json().get("pelanggan") == PELANGGAN

    def test_02_upload_big_wo_attachment(self, client, state):
        pdf = make_sized_pdf("WO BESAR", 2000, 2800, noise_image=True)
        state["input_bytes"] += len(pdf)
        # sanity: source page really is 2000x2800
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        assert (round(doc[0].rect.width), round(doc[0].rect.height)) == (2000, 2800)
        doc.close()
        r = client.post(f"{API}/workorders/{state['wo']}/attachments",
                        files={"file": ("wo_besar.pdf", pdf, "application/pdf")},
                        data={"kind": "general"}, timeout=180)
        assert r.status_code in (200, 201), r.text[:500]
        assert r.json().get("id")

    def test_03_create_invoice(self, client, state):
        payload = {
            "pelanggans": [PELANGGAN],
            "jenis_pekerjaan": "NON_MAINTENANCE",
            "invoice_no": INVOICE_NO,
            "work_order_ids": [state["wo"]],
            "tanggal": "2026-06-21",
        }
        r = client.post(f"{API}/invoices", json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text[:500]
        d = r.json()
        assert d.get("id") and "_id" not in d
        assert d["invoice_no"] == INVOICE_NO
        state["inv"] = d["id"]

    def test_04_upload_invoice_docs_various_sizes(self, client, state):
        inv = state["inv"]
        uploads = [
            ("faktur-pajak", "faktur.pdf", "FAKTUR", 595, 842),
            ("bukti-potong", "bupot.pdf", "BUPOT", 300, 500),
            ("scan-invoice", "scan.pdf", "SCAN", 1200, 600),
        ]
        for ep, name, text, w, h in uploads:
            pdf = make_sized_pdf(text, w, h)
            state["input_bytes"] += len(pdf)
            r = client.post(f"{API}/invoices/{inv}/{ep}",
                            files={"file": (name, pdf, "application/pdf")}, timeout=120)
            assert r.status_code in (200, 201), f"{ep} -> {r.status_code} {r.text[:300]}"
            assert r.json().get("ok") is True

    def test_05_lampiran_generated(self, client, state):
        r = client.get(f"{API}/invoices/{state['inv']}/pdf", params={"part": "lampiran"}, timeout=240)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        state["lampiran"] = r.content

    def test_06_all_pages_normalized_to_a4(self, state):
        content = state["lampiran"]
        assert content, "lampiran not generated"
        doc = pymupdf.open(stream=content, filetype="pdf")
        sizes = [(round(p.rect.width, 2), round(p.rect.height, 2)) for p in doc]
        doc.close()
        assert len(sizes) >= 4, f"expected >=4 pages, got {len(sizes)}: {sizes}"
        bad = []
        for i, (w, h) in enumerate(sizes):
            if w > h:
                ok = abs(w - 842) <= TOL and abs(h - 595) <= TOL
            else:
                ok = abs(w - 595) <= TOL and abs(h - 842) <= TOL
            if not ok:
                bad.append((i, w, h))
        print(f"INFO lampiran page sizes: {sizes}")
        assert not bad, f"pages not A4-normalized: {bad} (all sizes={sizes})"
        # no original odd sizes remain
        for w, h in sizes:
            assert (round(w), round(h)) not in [(2000, 2800), (300, 500), (1200, 600)], sizes

    def test_07_landscape_page_uses_a4_landscape(self, state):
        doc = pymupdf.open(stream=state["lampiran"], filetype="pdf")
        try:
            landscape_pages = []
            for p in doc:
                if "SCAN" in (p.get_text() or "").upper():
                    landscape_pages.append((round(p.rect.width), round(p.rect.height)))
            assert landscape_pages, "SCAN page not found"
            assert (842, 595) in landscape_pages, f"SCAN page sizes: {landscape_pages}"
        finally:
            doc.close()

    def test_08_page_order_and_text_readable(self, state):
        doc = pymupdf.open(stream=state["lampiran"], filetype="pdf")
        try:
            texts = [(p.get_text() or "").upper() for p in doc]
        finally:
            doc.close()
        expected = ["SCAN", "FAKTUR", "BUPOT", "WO BESAR"]
        found_order = []
        for kw in expected:
            for i, t in enumerate(texts):
                if kw in t:
                    found_order.append((kw, i))
                    break
            else:
                pytest.fail(f"text '{kw}' missing from lampiran pages: {[t[:40] for t in texts]}")
        idxs = [i for _, i in found_order]
        assert idxs == sorted(idxs), f"page order wrong: {found_order}"
        assert idxs[0] == 0, f"first page must be scan invoice, got order {found_order}"

    def test_09_compression_applied(self, state):
        out = len(state["lampiran"])
        inp = state["input_bytes"]
        assert inp > 0
        print(f"INFO input_total={inp} bytes, lampiran_output={out} bytes, ratio={out/inp:.3f}")
        assert out < inp * 0.6, f"output {out} not much smaller than input {inp}"

    def test_10_cleanup(self, client, state):
        r = client.delete(f"{API}/invoices/{state['inv']}", timeout=60)
        assert r.status_code in (200, 204), r.text[:300]
        g = client.get(f"{API}/invoices/{state['inv']}", timeout=60)
        assert g.status_code == 404
        r2 = client.delete(f"{API}/workorders/{state['wo']}", timeout=60)
        assert r2.status_code in (200, 204), r2.text[:300]
        state["inv"] = None
        state["wo"] = None
