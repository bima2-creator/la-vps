# LA Tracker — Product Requirements Document

## Original Problem Statement
> "Buat aplikasi powerful untuk entry data, pengolahan data, dan penyajian data report serta dashboard untuk data yang saya miliki."

User uploaded `data dump - LA.xlsx`: an Indonesian telecom provisioning work order tracker
with 68 columns following the workflow **Survey → Instalasi → Aktivasi**, plus SPK/WO
tracking, SLA (durasi vs target), Bill of Quantity (BoQ), and Invoice lifecycle.

## User Personas
- **Admin**: Full CRUD on work orders, manages users, sees everything.
- **Operator**: Enters and edits work orders. Cannot manage users or delete.
- **Viewer**: Read-only. Sees dashboard, workorder list, reports only.

## Core (Static) Requirements
1. Multi-role authentication (JWT + httpOnly cookies + Bearer fallback).
2. Import from the original Excel dump format (3-row grouped header) and from
   the app's own export format.
3. Export all workorders to Excel.
4. Multi-step data entry form covering all 60+ fields, grouped into 7 sections
   (Pelanggan, SPK, Timeline & SLA, Media & Kontak, Hasil Pekerjaan, Info
   Pelanggan, BoQ & Invoice).
5. Filterable table view with search, invoice/media filters, pagination.
6. Dashboard with KPIs (total, in-progress, completed, revenue paid, SLA %) and
   charts (jenis, media, invoice status).
7. Reports page with filters + Print/PDF and Excel export.
8. Admin user management page.

## Impor Bank Data + Sorot Auto-Isi (Jun 2026 — implemented)
- **Impor Excel** (`POST /api/perangkat/bank/import/xlsx`, admin-only): unggah
  file Excel untuk mengimpor banyak pasangan prefix→nama sekaligus. Dua layout
  otomatis terdeteksi dari header:
  1. Kolom **Prefix + Nama Perangkat** → impor langsung (validasi prefix 11-13
     char; baris tak valid masuk `skipped` + `errors[]`; duplikat dilewati).
  2. Kolom **Nomor Registrasi + Nama Perangkat** → prefix diturunkan otomatis
     via learning (`_learn_perangkat`, baris nomor <11 char dilewati).
  Respons `{ok, mode, imported, skipped, errors}`.
- **Template** (`GET /api/perangkat/bank/import/template.xlsx`, admin-only):
  unduh template kolom Prefix + Nama Perangkat dengan contoh baris.
- **Frontend** (`BankDataPage.jsx`): tombol **Template** (unduh) + **Import
  Excel** (input file tersembunyi `bank-import-input`), toast ringkasan
  (imported/skipped) + peringatan bila ada baris bermasalah, tabel auto-reload.
- **Sorot Auto-Isi** (`PerangkatEditor.jsx` + `index.css`): saat nama perangkat
  terisi otomatis (draft atau baris tabel), field nama diberi **kilatan hijau**
  (`@keyframes bank-flash` / class `.bank-flash`, ~1 detik) via perubahan `key`
  React agar operator langsung sadar sistem mengenali perangkat.
- **Status**: Tested end-to-end (backend 8/8 pytest impor + RBAC + template,
  frontend 4/4 flow termasuk kilatan draft & baris) — PASS.

## Kelola & Ekspor Bank Data + Auto-Isi di Tabel (Jun 2026 — implemented)
- **Halaman admin `/bank-data`** (`BankDataPage.jsx`, menu "Kelola Bank Data"
  grup Admin, admin-only): KPI (total entri, prefix unik, nama unik), pencarian
  (prefix/nama), tabel entri dengan **edit inline** (prefix + nama), **hapus**,
  dan **tambah entri manual**. Untuk memperbaiki entri prefix yang salah.
- **Endpoint admin** (`server.py`, semua `require_roles("admin")`):
  - `GET /api/perangkat/bank?q&page&page_size` — list + KPI.
  - `POST /api/perangkat/bank {prefix, nama}` — tambah (validasi prefix 11-13
    char; idempotent).
  - `PUT /api/perangkat/bank/{id}` — ubah prefix/nama; **auto-merge count** bila
    hasil edit bentrok dengan entri lain (`merged=true`).
  - `DELETE /api/perangkat/bank/{id}` — hapus entri.
  - `GET /api/perangkat/bank/export/xlsx` — unduh seluruh bank data ke Excel.
- **Auto-isi di tabel perangkat** (`PerangkatEditor.jsx`): saat operator
  mengedit `nomor_registrasi` pada baris perangkat yang sudah ada (bukan hanya
  saat menambah), lookup dijalankan (debounce 300ms). Match tunggal → nama
  terisi otomatis (tidak menimpa ketikan manual, dilindungi `rowAutoRef`);
  match ambigu → chip pilihan (`perangkat-row-bank-options-{i}`) untuk dipilih.
- **Status**: Tested end-to-end (backend 15/15 pytest, frontend 3/3 flow) — PASS.

## Bank Data Perangkat / Auto-Detect Registrasi (Jun 2026 — implemented)
- **Tujuan**: operator mengetik nomor registrasi perangkat → sistem otomatis
  mengenali NAMA perangkat dari prefix kode (11-13 karakter). Bank data
  **belajar**: setiap perangkat (nama + nomor registrasi) yang ditambahkan ke WO
  otomatis tersimpan jadi bank data (makin banyak input makin pintar).
- **Backend** (`server.py`):
  - Collection baru `perangkat_bank` `{prefix, plen, nama, count, updated_at}`,
    index compound `{prefix:1, plen:1}`.
  - `_learn_perangkat(items)` — dipanggil di `create_workorder` &
    `update_workorder`; untuk tiap item simpan prefix panjang 11/12/13 → nama
    (`$inc count`, upsert).
  - `_seed_perangkat_bank()` — di `on_startup`, seed dari
    `perangkat_bank_seed.json` (~99 baris dari `data perangkat.xlsx`) bila
    koleksi kosong (idempotent).
  - `GET /api/perangkat/bank/lookup?nomor=` — **longest-prefix match**: coba
    13 → 12 → 11 karakter, kembalikan `{matched, prefix, length, ambiguous,
    suggested, options[]}`. `<11` char → `matched=false`.
- **Frontend** (`PerangkatEditor.jsx`):
  - `useEffect` debounce 300ms pada `draft.nomor_registrasi` (min 11 char) →
    call lookup.
  - Match tunggal → auto-isi nama (bisa diedit; tidak menimpa ketikan manual)
    + hint hijau "Terdeteksi otomatis" (`perangkat-bank-detected`).
  - Match ambigu (mis. REMOTE HX50 vs MODEM HX50) → kotak amber berisi tombol
    pilihan (`perangkat-bank-options` / `perangkat-bank-option-*`), klik untuk
    isi nama.
- **Status**: Tested end-to-end (backend 8/8 pytest, frontend 2/2 flow) — PASS.

- Untuk jenis DISMANTLE, banyak field disembunyikan sesuai request:
  - Customer: `sa_id`, `lat`, `lng`, `bw`, `rfs_la`, `rfs_pelanggan` hidden.
  - SPK: hanya `spk_survey_nomor` + `spk_survey_tgl_doc` visible (sisanya
    disembunyikan; SPK Survey field digunakan sebagai "SPK Dismantle").
  - **Section Timeline & SLA lenyap** (semua field hidden → section
    auto-dropped oleh visibleSections filter).
  - Hasil Pekerjaan: hanya `hasil_survey_status` + perangkat_items editor
    (datek/npae + instalasi_* + aktivasi_* hidden).
- Constant `DISMANTLE_EXTRA_HIDDEN` di `workorder-schema.js` mengumpulkan
  semua field yang disembunyikan.

## MAINTENANCE Flow (Feb 2026 — implemented)
- **Step 2 picker**: setelah pilih MAINTENANCE, user harus pilih **CM
  (Corrective)** vs **PM (Preventive)** via 2 card besar (mirip fase picker).
  Nilai disimpan di `maintenance_type` (kolom baru di `WorkOrderBase`).
- **Field baru**: `case_no` (No. Case) & `task_no` (No. Task), tagged
  `maintenanceOnly: true` di schema — otomatis hidden untuk non-MAINTENANCE
  order (via `getMaintenanceOnlyHidden`). **Wajib** untuk MAINTENANCE
  (client-side validation di `save()`).
- **Hidden fields**: `sa_id`, `lat`, `lng`, `bw`, `rfs_la`, `rfs_pelanggan`,
  `spk_instalasi_*`, `spk_survey_tgl_terima`, semua timeline/stop/sdt,
  `hasil_*_datek/npae`, `hasil_instalasi_*`, aktivasi_* — hanya `case_no`,
  `task_no`, `spk_survey_nomor` (relabeled "No. SPK"), `spk_survey_tgl_doc`
  (relabeled "Tanggal SPK"), status survey (relabeled "Status Maintenance"),
  dan `perangkat_items` (relabeled "Perangkat Terganggu / Diperbaiki")
  yang tampil.
- **Badge**: badge amber "CORRECTIVE"/"PREVENTIVE" tampil di header form.
  Badge "FASE:" disembunyikan untuk MAINTENANCE (bukan fase pekerjaan).
- **BoQ paket khusus**: BoQ picker otomatis switch source ke
  `/lib/paket-maintenance-data.json` (141 item dari KHS Gangguan
  — tower, kabel, cabut, PM Rutin, transportasi, dll) saat
  `jenis_order === "MAINTENANCE"`. Untuk jenis lain tetap pakai
  `paket-data.json` (master PKS).

## Reports Segmented per Jenis (Feb 2026 — implemented)
- **Endpoint**: `GET /api/reports/by-jenis?date_from&date_to&media_jenis`
  returns `segments[]` (5 jenis) + `totals`. Each segment has count,
  by_status (completed/in_progress/pending), by_media, revenue_total,
  revenue_paid, revenue_open, sla_hit/miss/pct. MAINTENANCE segment
  additionally includes `cm_count` & `pm_count`.
- **Frontend**: `ReportsPage.jsx` — new "Report per Jenis Pekerjaan"
  section with 5 segment cards (icon + count + CM/PM badges for
  MAINTENANCE + status split + revenue + SLA). Auto-refetches on
  Apply Filters using shared date/media filters. Total card summarises
  all jenis at once.

## Master Perangkat / Asset Registry (Feb 2026 — implemented)
- **Endpoints**:
  - `GET /api/perangkat/registry?q&jenis_wo&status&page&page_size` —
    aggregates `perangkat_items` across all WOs by `nomor_registrasi`.
    Returns KPI (total_devices, total_wo_links, by_status, by_jenis_order,
    by_media) + paged `items[]` with `wo_history`, `current_status`,
    `latest_pelanggan`, etc.
  - `GET /api/perangkat/export/csv` — same filters, streams CSV.
- **Frontend**: `/perangkat` route (`MasterPerangkatPage.jsx`) with 4
  KPI cards, filter bar (search + jenis + status), table of unique
  devices, right-side drill-down panel showing full WO history with
  clickable "Open WO" links. Sidebar nav updated.
- **Constraint relaxed**: `_validate_perangkat_uniqueness` now allows the
  same `nomor_registrasi` across multiple WOs when they share the same
  `sa_id` **or** `si_id` (rule: "1 perangkat = 1 SA/SI", not 1 WO). This
  is required so a device can appear in PSB → MAINTENANCE → DISMANTLE
  history for the same customer/service. Cross-owner reuse still blocked.
- **Device status derivation**: latest WO's `jenis_order` → status:
  DISMANTLE → `DISMANTLED`, MAINTENANCE → `MAINTENANCE`, else `TERPASANG`.

## Perangkat Items + Fase Pekerjaan Picker (Feb 2026)
- **Perangkat Terpasang** dipindahkan dari section "Info Pelanggan" ke
  **"Hasil Pekerjaan"**.
- Field lama `perangkat_terpasang` (string) legacy; ditambahkan `perangkat_items:
  List[{nama_perangkat, nomor_registrasi}]`.
- Component `PerangkatEditor.jsx`: multi-row, autocomplete dari 32 master
  perangkat (extract dari `data perangkat-dump.xlsx`).
- **Uniqueness rule**: 1 nomor registrasi hanya bisa dimiliki 1 SA/SI ID
  (WO). Backend validate on create + update — return HTTP 400 dengan pesan
  yang menyebutkan WO/SA yang sudah pakai nomor tsb.
- Sparse index `perangkat_items.nomor_registrasi` di collection workorders.
- **DISMANTLE**: field `sa_id` disembunyikan (hanya SI ID). Dilakukan via
  `JENIS_ORDER_META.DISMANTLE.hidden = [...AKTIVASI_FIELDS, "sa_id"]`.

- **Fase Pekerjaan picker** untuk PSB/MUTASI/MIGRASI:
  - Setelah pilih Jenis Order, muncul Step 2 "Pilih Fase Pekerjaan" dengan
    3 kartu (Survey / Instalasi / Aktivasi).
  - Field disembunyikan by fase: pick Survey → hanya field `*_survey_*`
    tampil (SPK/Timeline&SLA/Hasil), sisanya disembunyikan.
  - New field `wo_jenis_pekerjaan` di WorkOrderBase menyimpan fase.
  - Badge "PSB" (biru) + "FASE: INSTALASI" (hijau) di header form.
  - DISMANTLE / MAINTENANCE tidak butuh fase (mereka sendiri = fase).

## Invoice Auto-Include & Title Cleanup (Feb 2026)
- Ketika Tambah Pelanggan, semua WO milik pelanggan tsb yang match jenis
  pekerjaan **otomatis ter-include** — tidak ada lagi step "Pilih Work Order"
  manual. Cocok untuk billing konsolidasi cepat.
- Section baru: **Ringkasan per Pelanggan** (tabel langsung dengan kolom
  Jumlah WO, Total Jasa, Total Material, Subtotal, tombol Hapus per baris).
- Warning `"Tidak ada WO {jenis} untuk pelanggan ini"` bila pelanggan tidak
  punya WO matching (tetap boleh dibiarkan atau dihapus).
- Modal title disingkat dari "Invoice Multi-Pelanggan" → **"Invoice"**.

## Multi-Pelanggan Invoice Flow (Feb 2026)
- Invoice sekarang bisa berisi **beberapa pelanggan** dalam satu tagihan.
- Backend `InvoiceIn.pelanggans: List[str]` (was `pelanggan: str`). Legacy
  `pelanggan` field tetap diisi (single name atau `Multiple (N): …`) untuk
  backward compat. GET responses selalu expose `pelanggans` array.
- `/invoices/candidates` endpoint: query param `pelanggans` (comma-separated)
  menggantikan `pelanggan` single. WO ditampilkan **grouped by pelanggan**.
- Frontend flow baru (di modal):
  - **Step 1 - Jenis Pekerjaan** (dipilih pertama)
  - **Step 2 - Pelanggan** dengan tombol **+ Tambah Pelanggan** (multi, chip UI)
  - **Step 3 - Pilih Work Order** — grouped by pelanggan, per-row checkbox
  - **Step 4 - Detail Invoice** (nomor, tanggal, status)
- Kode invoice auto-generate untuk multi: `INV-{ACT}-MULTI{N}-{YYYYMMDD}-{RAND}`
  (contoh `INV-INS-MULTI2-20260730-702`).
- List page kolom Pelanggan: bila single → nama; bila multi → "N Pelanggan"
  + list truncated di baris kedua.

## Standalone Invoice Module (Feb 2026)
- New sidebar menu **Invoices** at `/invoices`.
- Invoice model driven by **Pelanggan × Jenis Pekerjaan**. One invoice can
  consolidate multiple work orders.
- Backend:
  - New `invoices` collection with `pelanggan`, `jenis_pekerjaan`,
    `work_order_ids[]`, `work_orders_snapshot[]`, `total_jasa`,
    `total_material`, `grand_total`, dates & status.
  - Endpoints: `GET /api/invoices/customers`, `GET /api/invoices/candidates`,
    full CRUD `GET/POST/PUT/DELETE /api/invoices`.
  - `candidates` filters WOs by pelanggan + matching activity phase completion,
    and flags WOs already billed in another invoice (`already_billed_invoice_id`).
- Frontend `InvoicesPage.jsx` with list, filters (jenis / status / search),
  and a 4-step create/edit modal (Pelanggan → Jenis → Pilih WO → Detail).
- Invoice number auto-generator: `INV-{ACT}-{PELANGGAN_TAG}-{YYYYMMDD}-{RAND}`.
- WO's per-record Invoice section:
  - **Auto-fill button REMOVED** per user request.
  - Activity picker now shows **ALL 5 options** (SURVEY / INSTALASI / AKTIVASI
    / DISMANTLE / MAINTENANCE) regardless of WO jenis_order.
  - Summary card now links to `/invoices` module.

## Table Columns + Invoice-per-Activity + BoQ Flow Swap (Feb 2026)
- **Work Orders list**: kolom `Invoice` (status) dan `No Inv` **dihapus**, diganti:
  - `No SPK` — virtual: SPK Survey/Instalasi/Aktivasi non-empty dengan prefix
    `S:` / `I:` / `A:`.
  - `Activity` — virtual: fase aktif saat ini + state badge (On-going / Done /
    Complete). DISMANTLE/MAINTENANCE hanya Survey+Instalasi.
  - Helpers: `deriveSpkSummary`, `deriveCurrentActivity`, `activityPhasesFor`.
- **Invoice per activity type**: field `inv_jenis_pekerjaan` (SURVEY /
  INSTALASI / AKTIVASI / DISMANTLE / MAINTENANCE). Opsi filter per jenis WO —
  DISMANTLE hanya DISMANTLE, MAINTENANCE hanya MAINTENANCE.
  Invoice number pola: `INV-{ACT}-{SA_ID}-{YYYYMMDD}-{RAND}`, contoh
  `INV-INS-SAJP001-20260730-563`.
- **BoQ Add flow swap**: Step 1 pilih paket dari master PKS → Step 2 pilih
  jenis biaya (dengan preview harga per opsi).

## Multi-Paket BoQ + IDR Formatting (Feb 2026)
- One work order can now have **multiple paket rows** (same code can repeat).
- New `BoqItemsEditor` component with:
  - Add Paket button → searchable PaketPicker inline
  - Per-row: Kode, Nama, Mode (Jasa/Material/Both), Qty, Jasa, Material, Subtotal, Delete
  - Footer: Total Jasa + Total Material + Grand Total (bold, blue Rp)
- Legacy single-value fields (`boq_paket`, `boq_jasa`, `boq_material`,
  `boq_jumlah`, `boq_mode`) auto-derived on save for backward compat with
  Excel/PDF exports and old dashboard aggregates.
- Backward compat: opening an old work order (single-value BoQ) auto-migrates
  it into one row in `boq_items[]` on edit.
- Backend `WorkOrderBase.boq_items: List[Any] = []`.
- Rupiah formatting applied everywhere:
  - `/app/frontend/src/lib/format.js` (`formatIDR`, `formatIDRCompact`)
  - Work Orders list column "Total" → `formatIDR`
  - Reports table + KPI cards → `formatIDR`
  - Dashboard revenue KPI (existing)
  - PDF export (list + detail) → `_fmt_rp("Rp 1.234.567")`
  - Excel export → xlsxwriter `num_format='"Rp" #,##0'` on BOQ JASA / MATERIAL
    / JUMLAH columns.

## BoQ Master Paket + Mode Selector (Feb 2026)
- Imported 81 paket rows from `Harga PKS PSB Cabut 2014.xls` into
  `/app/frontend/src/lib/paket-data.json` (code, name, satuan, keterangan,
  jasa, material, total).
- New `PaketPicker` component: searchable dropdown showing kode + nama +
  keterangan + harga (Total, breakdown Jasa & Material).
- BoQ section changes:
  - `boq_paket` → paket-picker widget (typeahead over 81 paket).
  - `boq_paket_code` — persists the selected paket code (e.g. "P008").
  - `boq_mode` — segmented control: **Jasa saja / Material saja / Jasa +
    Material**. Jumlah Total auto-recomputes on jenis/material/mode change.
- Backend `WorkOrderBase` extended with `boq_paket_code` + `boq_mode`.
- Light theme applied globally (index.css vars, chart colors, hover states,
  table shading).

## Jenis Order Picker Step (Feb 2026)
- New Work Order form now opens with a **mandatory Jenis Order picker** (step 1 of 2).
- Options: **PSB, MUTASI, MIGRASI, DISMANTLE, MAINTENANCE** (UPGRADE removed,
  MAINTENANCE added).
- After pick, `jenis_order` is **locked** (read-only with 🔒 badge). To change:
  cancel + start over.
- **DISMANTLE / MAINTENANCE** hide all `*_aktivasi` fields across SPK,
  Timeline & SLA, and Hasil Pekerjaan sections — BoQ & Invoice remains.
- Dashboard slice filter dropdown updated to match (UPGRADE → MAINTENANCE).
- New helpers in `workorder-schema.js`: `JENIS_ORDER_META`,
  `JENIS_ORDER_LIST`, `getHiddenFields(jenis)`.
- Verified end-to-end via Playwright: picker renders, DISMANTLE hides aktivasi,
  MAINTENANCE keeps BoQ, PSB shows everything, save persists jenis_order.

## Detail WO per Teknisi + Export KPI Excel (Jun 2026 — implemented)
- **Detail WO per Teknisi**: di halaman KPI Teknisi, klik nama teknisi
  (`kpi-open-<nama>`) → modal (`kpi-detail-modal`) menampilkan daftar WO yang
  ditangani (pelanggan, SA ID, jenis, media, status OK/Batal, tanggal) + tombol
  buka WO ke `/workorders/:id`. Endpoint `GET /api/kpi/teknisi/workorders?nama=&tim=&date_from&date_to`.
- **Export KPI Excel**: tombol `kpi-export-xlsx` unduh rekap KPI ke `.xlsx`
  (2 sheet: Ringkasan Internal/Mitra/Semua + Per Teknisi). Endpoint
  `GET /api/kpi/teknisi/export/xlsx`. Agregasi direfactor ke helper
  `_compute_kpi_teknisi` (dipakai bersama endpoint kpi & export).
- **Status**: Backend diuji via curl (WO-list & export xlsx valid), UI via
  screenshot (modal 2 WO OK/Batal, tombol export). teknisi_master dibersihkan
  dari data uji (0 entri).

## KPI Teknisi + Autocomplete + Layout Media (Jun 2026 — implemented)
- **Layout Media & Kontak**: urutan diatur → (CP LA | CP Pelanggan), lalu
  (CP Pelaksana | Tim Pelaksana).
- **Autocomplete**:
  - Field Perangkat (`media_perangkat`) → datalist dari nilai yang pernah
    diinput (`GET /api/media/perangkat-names`, self-clean atas workorders).
  - Nama Teknisi → datalist dari master yang otomatis terkumpul saat WO disimpan
    (`_learn_teknisi` → koleksi `teknisi_master`; `GET /api/teknisi/master?tim=`).
- **KPI Teknisi** (`GET /api/kpi/teknisi?date_from&date_to&tim`): agregasi per
  teknisi + ringkasan Internal/Mitra/Semua. WO "selesai" = status hasil (fase
  aktivasi>instalasi>survey) **OK atau BATAL**. Metrik dipisah **Selesai - OK**
  dan **Selesai - Batal** + Pending + Total WO.
  - Catatan: field `success_rate` masih dikembalikan backend tapi **tidak
    ditampilkan** (dihapus dari UI atas permintaan user).
- **Tampilan**: halaman baru **KPI Teknisi** (`/kpi-teknisi`, menu semua role),
  section ringkas di **Dashboard** (data-testid `dashboard-kpi-teknisi`), dan
  **Rekap per Teknisi** di **Reports** (`report-kpi-teknisi`).
- **Status**: Backend 9/9 pytest (`tests/test_kpi_teknisi.py`, jalankan `-n0`),
  UI diverifikasi via screenshot.

## Tim Pelaksana + CP Pelaksana (Jun 2026 — implemented)
- Section **Media & Kontak** di semua Work Order:
  - Label **"CP Mitra" → "CP Pelaksana"** (field `cp_mitra`, label saja).
  - Field baru **Tim Pelaksana** (`tim_pelaksana`: INTERNAL | MITRA).
  - Field baru **Nama Teknisi** (`teknisi_pelaksana`: List) dengan tipe kustom
    `teknisi-list`: **INTERNAL → 4 input**, **MITRA → 1 input**. Ganti pilihan
    otomatis menyesuaikan jumlah entri (`onChange` me-resize array).
- Backend `WorkOrderBase`: `tim_pelaksana: str`, `teknisi_pelaksana: List[Any]`.
- Tujuan: data tim pelaksana menjadi dasar penilaian pencapaian **KPI & target**
  (implementasi KPI menyusul).
- **Status**: Diverifikasi — backend persist (curl create/update INTERNAL↔MITRA),
  frontend (4 vs 1 input, label CP Pelaksana) via screenshot.

## Fix Docker Build: yarn.lock not found (Jun 2026)
- **Gejala**: `docker build` frontend gagal — `"/yarn.lock": not found` /
  `failed to compute cache key`.
- **Akar masalah**: `frontend/yarn.lock` tidak ikut ter-commit ke Git (untracked,
  meski tidak di-ignore), sehingga hilang saat kode di-push/di-download →
  `COPY package.json yarn.lock ./` gagal.
- **Perbaikan**: `frontend/Dockerfile` → `COPY package.json yarn.lock* ./`
  (wildcard, opsional) + `yarn install` (tanpa `--frozen-lockfile`), sehingga
  build tetap sukses walau yarn.lock tidak ada (lockfile dibuat ulang di image).

## Panduan Instalasi Windows (Docker) + PDF (Jun 2026 — updated)
- **README-LOCAL.md** ditulis ulang: metode Docker Desktop, database MongoDB
  otomatis (container `la-tracker-mongo`, data persisten di `.\data\mongo`),
  bagian Database (lokasi/backup/restore), akses LAN, skrip, update, troubleshoot.
- **Login diperbaiki**: username-based (admin/admin123, operator/operator,
  guest/guest) — bukan email lagi. `local.env.example` + `start.bat` diperbarui
  (tambah OPERATOR_PASSWORD & GUEST_PASSWORD; ADMIN_EMAIL jadi alamat notifikasi).
- **PDF cetak**: `Panduan-Instalasi-LA-Tracker-Windows.pdf` dibuat via reportlab
  (`scripts/gen_install_pdf.py`) — 10 bagian + ringkasan, siap dibagikan/dicetak.

## Local / Offline Deployment (Feb 2026)
- Full Docker Compose bundle: MongoDB + FastAPI backend + React/nginx frontend.
- New backend `STORAGE_MODE=local` writes attachments to `/data/attachments`
  (mounted host volume `./data/attachments`). Cloud mode preserved.
- New `/api/` health endpoint for readiness probes.
- CORS supports wildcard (`CORS_ORIGINS=*`) for LAN access in local mode.
- Windows launcher scripts: `start.bat`, `stop.bat`, `rebuild.bat`,
  `backup.bat`. `start.bat` auto-creates `local.env`, `data/mongo`,
  `data/attachments`, waits for backend health, detects LAN IPv4, opens
  browser.
- Frontend built with `REACT_APP_BACKEND_URL=""` so it calls `/api/...`
  same-origin via nginx reverse proxy (`frontend/nginx.conf`).
- Data persistence in `./data/`. Migration from preview via Excel
  Export → local Excel Import.
- Docs: `README-LOCAL.md` (Bahasa Indonesia) covers install, LAN, backup,
  update, troubleshooting.

## What's Been Implemented (Feb 2026)
- Backend (FastAPI + MongoDB): full auth (`/api/auth/*`), users
  (`/api/users`), workorders CRUD (`/api/workorders`), Excel import
  (`/api/workorders/import/xlsx` — auto-detects original 3-row layout), Excel
  export, dashboard stats (`/api/dashboard/stats`), RBAC via
  `require_roles()`.
- Frontend (React + Tailwind + Shadcn + Recharts + Phosphor):
  - Dark "command center" theme (Chivo display + IBM Plex Sans/Mono).
  - Login page with decorative left panel.
  - Sidebar layout with collapsible nav and role-filtered menu.
  - Dashboard with 5 KPI cards and 3 recharts.
  - Work Orders table (search, filters, pagination, import/export, edit/delete).
  - Multi-tab Work Order form covering every field of the original dump.
  - Reports page with filters, KPI summary, printable table.
  - Users administration (create/delete, role chips).
- Admin seeded on startup: `admin@la-tracker.com / admin123`.

## Prioritized Backlog / Next Actions
- **P2** – Auto-generated Berita Acara (BAST) PDF.
- **P2** – Bulk edit / bulk status update on selected rows.
- **P2** – Attachments per work order (photos, BAST, SLA reports) using
  object storage.
- **P2** – Audit trail (who changed what, when).
- **P3** – Notifications (email or Telegram) for SLA breaches / paid invoices.
- **P3** – Public shareable read-only report link with a token.
- **P3** – Refactor: split `backend/server.py` (~2150 LOC) into modules and
  `frontend/src/pages/InvoicesPage.jsx` (~1000 LOC) into sub-components.

## Recent Changes
- 2026-07-30 — Invoice PDF: layout ulang mengikuti sample "INV 011 PSB
  SAMPLE.pdf": logo Almar Networks (di-extract & di-render dari sample PDF
  ke `backend/static/almar_logo.png`), title "INVOICE" biru di kanan,
  header perusahaan biru, banner **BILL TO / INVOICE # / DATE**, banner
  opsional **INVOICE EPROC #**, header tabel biru. Endpoint tetap
  `GET /api/invoices/{inv_id}/pdf`.

## Architecture Tasks Done
- Kubernetes-friendly `/api` prefix everywhere.
- httpOnly cookies (SameSite=None, Secure) + Bearer fallback for previews.
- CORS locked to `FRONTEND_URL` with credentials allowed.
- MongoDB indexes on `users.email` (unique), `workorders.pelanggan`,
  `workorders.sa_id`, `workorders.inv_status`, `workorders.media_jenis`.
