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

## Media Akses & Perangkat dependent dropdown (June 2026)
- Hapus jenis media "OTHER" (dropdown + migrasi WO existing media_jenis OTHER → kosong).
- Jenis Media Akses: WIRELINE, WIRELESS, SATELLITE, PIHAK KE 3 (FIBER dihapus, folded ke WIRELINE karena perangkat duplikat; migrasi FIBER→WIRELINE & "Stand Alone"→"Standalone").
- Perangkat jadi dropdown dependent (`MEDIA_PERANGKAT_OPTIONS` di workorder-schema.js):
  - WIRELINE: M2M, Open Port, AIR Fiber, GPON, Standalone, Back to Back, SDWAN, Router
  - WIRELESS: BWA, Radio Link
  - FIBER: GPON, Stand Alone, Back to Back
  - SATELLITE: Idirect, Hughes, Starlink
  - PIHAK KE 3: tanpa perangkat (dropdown disabled, perangkat dikosongkan)
- Ganti media_jenis mereset media_perangkat bila tak valid. Terverifikasi UI.

## SI ID prefill saat create WO (June 2026)
- Saat input SI ID di form WO baru, jika SI ID sudah terdaftar → muncul banner info + tombol "Isi Otomatis".
- Backend `GET /workorders/lookup-by-si?si_id=` → WO terakhir dgn SI ID sama. Prefill: Pelanggan (kecuali RFS & jenis_order & si_id), Media & Kontak (kecuali tim_pelaksana/teknisi), dan perangkat_items terakhir terpasang. Response juga berisi `matches[]` = seluruh riwayat WO untuk SI ID tsb (id, jenis_order, created_at, pelanggan, spk, perangkat_count, prefill) agar user bisa memilih WO mana untuk prefill.
- Frontend `WorkOrderFormPage.jsx`: debounce lookup, banner biru menampilkan daftar riwayat WO dengan tombol "Pilih" per item; `applySiPrefill(prefill)`. Terverifikasi curl + UI.

## Badge menu & index MongoDB (June 2026)
- Sidebar "Work Orders" menampilkan badge amber jumlah WO belum invoice. Endpoint baru `GET /workorders/pending-invoice-count` → {total, belum, sudah}. Layout fetch saat pindah route. Badge dapat diklik → `/workorders?invoiced=belum` (WorkOrdersPage sync filter dari URL). Terverifikasi UI.
- Index MongoDB ditambah: workorders(jenis_order, created_at desc), invoices(work_order_ids). Terverifikasi (badge=35, index terpasang).

## Invoice filter, badge link, query cap (June 2026)
- Work Orders: filter cepat "Sudah/Belum Invoice" (`GET /workorders?invoiced=sudah|belum`, cocokkan via invoices.work_order_ids + legacy inv_no). Badge No Invoice kini bisa diklik → `/invoices?q=<no>` (InvoicesPage baca `?q=` dari URL). Field `invoice_id` ditambahkan di output list.
- Optimasi query: dashboard stats & `_compute_kpi_teknisi` pakai projection field + cap `STATS_SCAN_LIMIT` (env, default 50000). Terverifikasi curl + UI.

## No Invoice column di Work Orders (June 2026)
- Halaman Work Orders: tambah kolom "No Invoice". Backend `GET /workorders` menghitung nomor invoice per WO dari `invoices.work_order_ids` (fallback ke field legacy `inv_no`), field `invoice_no_display`/`invoice_nos`.
- Frontend: kolom baru badge hijau (nomor invoice) bila sudah dibuatkan invoice, atau "BELUM" abu-abu. Terverifikasi curl + UI.

## KPI angka bisa diklik (June 2026)
- Halaman KPI Teknisi: semua nilai angka (Total WO, Selesai-OK, Selesai-Batal, Pending) di tabel per-teknisi DAN di kartu ringkasan (Internal/Mitra/Semua) kini dapat diklik → membuka modal daftar WO yang sudah difilter sesuai status.
- Backend: `/api/kpi/teknisi/workorders` kini `nama` opsional (mendukung query tingkat tim untuk kartu ringkasan). `teknisi_pelaksana` = List (match array membership).
- Frontend `KpiTeknisiPage.jsx`: komponen `NumLink` + `openDetail({nama,tim,status,title})` + filter client-side. Terverifikasi UI (klik angka tabel & kartu → modal terfilter benar).

## Backup Otomatis (June 2026)
- Backend: APScheduler `AsyncIOScheduler` menjalankan `_run_auto_backup` tiap 24 jam. `create_backup()` mengekspor koleksi (workorders, invoices, perangkat_bank, teknisi_master, users, audit_logs, attachments) ke JSON (bson.json_util → roundtrip ObjectId/datetime) & simpan ke object storage `backups/`. Metadata di koleksi `backups`. Retensi 7 terakhir (`_prune_backups`, env `BACKUP_RETENTION`).
- Endpoints (admin): `GET/POST /api/backups`, `GET /api/backups/{id}/download`, `POST /api/backups/{id}/restore` (delete_many+insert_many lalu seed_fixed_users), `DELETE /api/backups/{id}`.
- Frontend: halaman admin `/backup` (`BackupPage.jsx`, nav "Backup Data") — Backup Sekarang, Unduh JSON, Restore (dengan modal konfirmasi timpa data), Hapus. Terverifikasi curl (create/list/download/restore, data & login intact) + UI.

## Invoice PDF split (June 2026)
- `GET /invoices/{id}/pdf?part=invoice` → PDF Invoice saja (gate: ada pelanggan + Nomor Invoice + Nomor EPROC).
- `GET /invoices/{id}/pdf?part=lampiran` → PDF Lampiran saja: Faktur Pajak + Bukti Potong + SPK & Berita Acara (gate: file Faktur Pajak & Bukti Potong sudah diupload). Dokumen invoice TIDAK ikut.
- Frontend: 2 tombol per baris invoice (FilePdf = invoice, Paperclip = lampiran) dengan gating & toast. Terverifikasi curl + UI.

## Deployment & Docs (June 2026)
- Panduan instalasi Windows dibuat: `/app/PANDUAN_INSTALASI_WINDOWS.md` (Bahasa Indonesia, lengkap: prasyarat, .env lokal STORAGE_MODE=local, jalankan backend/frontend, akses LAN, troubleshooting).
- Deployment: blocker CORS diperbaiki (`backend/.env` CORS_ORIGINS="*"). deployment_agent status READY. App tinggal di-deploy lewat tombol Deploy platform.

## Backlog / Future
- **P1**: Ekspor Riwayat Perangkat — tombol download riwayat tracking 1 nomor registrasi ke Excel.
- **P2**: Isi otomatis `media_jenis` dari mapping (GPON→FIBER, IDIRECT→SATELLITE) untuk data lama (butuh konfirmasi user).
- **Refactor (opsional)**: pecah `server.py` yang monolitik.

## Files of Reference
- `backend/server.py`: semua route & logic. Import/export xlsx ~baris 1715-1874.
- `frontend/src/pages/WorkOrdersPage.jsx`: onImport/onExport.
- `frontend/src/components/PerangkatEditor.jsx`, `pages/PerangkatHistoryPage.jsx`, `PerangkatNamesPage.jsx`, `DashboardPage.jsx`.
