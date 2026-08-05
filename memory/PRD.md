# LA Tracker — Product Requirements (PRD)

## Problem Statement
Aplikasi manajemen Work Order (WO) & pengiriman proyek telekomunikasi Indonesia (Almar). Mengelola Work Orders, Invoices, KPI Teknisi, Reports, Perangkat (Device) Management, dan Attachments (SPK). Bahasa UI: **Indonesia**.

## Tech Stack
- Backend: FastAPI + MongoDB (Motor async), PyJWT, bcrypt. `backend/server.py` (~4000 baris, monolitik).
- Frontend: React + TailwindCSS + Axios. Auth via JWT Bearer di localStorage (`la_token`), `withCredentials: false`.
- Storage: Emergent Cloud Object Storage (lampiran SPK PDF/gambar), pakai Emergent LLM Key.

## Roles
Admin (`admin`/`admin123`), Operator (`operator`/`operator`), Guest/Viewer (`guest`/`guest`). Login pakai **username**.

## Key DB Schema
- `workorders`: { pelanggan, sa_id, si_id, jenis_order, media_perangkat, spk_survey_nomor, spk_instalasi_nomor, spk_aktivasi_nomor, perangkat_items: [{nomor_registrasi, nama_perangkat, status, role}], boq_* }
- `perangkat_bank`: { prefix(13 char), nama, plen }
- `users`: { username, password, role }

## Implemented (per June 2026)
- JWT auth, role-based access, WO CRUD, single & bulk delete + Undo + confirm modal.
- Emergent Object Storage attachments; download via `?auth=` JWT query param.
- Inline PDF preview SPK di form.
- Perangkat lifecycle: dismantle boleh dipakai ulang; dicabut/rusak diblokir permanen. Riwayat Perangkat, peringatan dini, badge "Tersedia".
- Auto-record nama perangkat baru ke registry + autocomplete. Admin "Kelola Nama Perangkat".
- Dashboard Media chart pakai `media_perangkat`.
- Prefix perangkat strict 13 char.
- **Excel Export** (`GET /api/workorders/export/xlsx`): sheet "Workorders" (+ kolom PERANGKAT DETAIL) & sheet "Perangkat".
- **Excel Import dedup** (`POST /api/workorders/import/xlsx`): dedup berdasarkan **nomor SPK per section** (survey/instalasi/aktivasi). Jika salah satu nomor SPK di baris impor sudah ada di DB → baris dilewati (skip). Response `{inserted, skipped}`. Frontend menampilkan jumlah baris yang dilewati. *Catatan: baris tanpa nomor SPK tidak bisa didedup dan akan selalu di-insert.* ✅ Diverifikasi via curl (35 skip saat re-import).

## Backlog / Future
- **P1**: Ekspor Riwayat Perangkat — tombol download riwayat tracking 1 nomor registrasi ke Excel.
- **P2**: Isi otomatis `media_jenis` dari mapping (GPON→FIBER, IDIRECT→SATELLITE) untuk data lama (butuh konfirmasi user).
- **Refactor (opsional)**: pecah `server.py` yang monolitik.

## Files of Reference
- `backend/server.py`: semua route & logic. Import/export xlsx ~baris 1715-1874.
- `frontend/src/pages/WorkOrdersPage.jsx`: onImport/onExport.
- `frontend/src/components/PerangkatEditor.jsx`, `pages/PerangkatHistoryPage.jsx`, `PerangkatNamesPage.jsx`, `DashboardPage.jsx`.
