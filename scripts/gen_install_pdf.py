#!/usr/bin/env python3
"""Generate a printable PDF install guide (Bahasa Indonesia) for LA Tracker."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, HRFlowable,
)

OUT = "/app/Panduan-Instalasi-LA-Tracker-Windows.pdf"

BLUE = colors.HexColor("#1d4ed8")
DARK = colors.HexColor("#0f172a")
GREY = colors.HexColor("#475569")
LIGHT = colors.HexColor("#eef2ff")
BORDER = colors.HexColor("#cbd5e1")
AMBER_BG = colors.HexColor("#fffbeb")
AMBER_BD = colors.HexColor("#fcd34d")

styles = getSampleStyleSheet()

h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=15, textColor=BLUE, spaceBefore=14, spaceAfter=6, leading=18)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=11.5, textColor=DARK, spaceBefore=8, spaceAfter=3, leading=14)
body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica",
                      fontSize=9.5, textColor=DARK, leading=14, spaceAfter=4, alignment=TA_LEFT)
small = ParagraphStyle("Small", parent=body, fontSize=8.5, textColor=GREY)
mono = ParagraphStyle("Mono", parent=body, fontName="Courier", fontSize=8.5,
                      textColor=DARK, backColor=colors.HexColor("#f1f5f9"), leading=12,
                      leftIndent=6, rightIndent=6, spaceBefore=2, spaceAfter=6, borderPadding=4)
note = ParagraphStyle("Note", parent=body, fontSize=9, textColor=colors.HexColor("#92400e"),
                      backColor=AMBER_BG, borderColor=AMBER_BD, borderWidth=0.6,
                      borderPadding=6, leading=13, spaceBefore=4, spaceAfter=8)
cell = ParagraphStyle("Cell", parent=body, fontSize=8.8, leading=12, spaceAfter=0)
cellb = ParagraphStyle("CellB", parent=cell, fontName="Helvetica-Bold")
cellm = ParagraphStyle("CellM", parent=cell, fontName="Courier")

story = []


def P(txt, s=body):
    story.append(Paragraph(txt, s))


def bullets(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(t, body), leftIndent=6) for t in items],
        bulletType="bullet", start="•", leftIndent=12, bulletColor=BLUE,
    ))
    story.append(Spacer(1, 3))


def numbered(items):
    story.append(ListFlowable(
        [ListItem(Paragraph(t, body), leftIndent=6) for t in items],
        bulletType="1", leftIndent=14,
    ))
    story.append(Spacer(1, 3))


def make_table(rows, widths, header=True):
    data = []
    for r_i, row in enumerate(rows):
        st = cellb if (header and r_i == 0) else cell
        data.append([Paragraph(str(c), cellm if (c.startswith("`") or "mono:" in c) else st)
                     for c in [x.replace("mono:", "").strip("`") for x in row]])
    t = Table(data, colWidths=widths, hAlign="LEFT")
    ts = [
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        ts += [("BACKGROUND", (0, 0), (-1, 0), BLUE),
               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        data[0] = [Paragraph(x, ParagraphStyle("hd", parent=cellb, textColor=colors.white))
                   for x in [c.strip("`") for c in rows[0]]]
        t = Table(data, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Spacer(1, 6))


# ---------------- Cover header ----------------
story.append(Spacer(1, 6))
title_tbl = Table([[Paragraph(
    "<b>LA TRACKER</b><br/><font size=12 color='#e0e7ff'>Panduan Instalasi di PC Windows (Docker) + Database</font>",
    ParagraphStyle("t", parent=body, textColor=colors.white, fontSize=20, leading=24))]],
    colWidths=[170 * mm])
title_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), BLUE),
    ("TOPPADDING", (0, 0), (-1, -1), 16),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ("LEFTPADDING", (0, 0), (-1, -1), 14),
]))
story.append(title_tbl)
story.append(Spacer(1, 10))
P("Panduan ini menjelaskan cara menginstal dan menjalankan <b>LA Tracker</b> "
  "secara 100% lokal di PC/laptop Windows, <b>lengkap dengan database MongoDB</b> "
  "yang terpasang otomatis. Data tersimpan di folder <b>.\\data\\</b> pada PC Anda. "
  "Aplikasi dapat diakses dari PC itu sendiri maupun PC lain di jaringan LAN/WiFi kantor.")
P("Metode: <b>Docker Desktop</b>. Anda tidak perlu menginstal MongoDB, Python, "
  "atau Node.js satu per satu — semuanya sudah dibungkus otomatis oleh Docker.", note)

# 1
P("1. Persyaratan Sistem", h1)
make_table([
    ["Kebutuhan", "Keterangan"],
    ["Sistem operasi", "Windows 10 / 11 (64-bit)"],
    ["Aplikasi wajib", "Docker Desktop for Windows"],
    ["RAM", "Minimum 4 GB (disarankan 8 GB)"],
    ["Ruang disk", "Minimal 2 GB kosong"],
    ["Internet", "Hanya saat instalasi / build pertama kali"],
], widths=[45 * mm, 125 * mm])

# 2
P("2. Instal Docker Desktop (sekali saja)", h1)
numbered([
    "Buka halaman unduhan: <font name='Courier'>https://www.docker.com/products/docker-desktop/</font>",
    "Klik <b>Download for Windows</b>, lalu jalankan <font name='Courier'>Docker Desktop Installer.exe</font>.",
    "Ikuti proses instalasi (biarkan opsi default → OK / Install). Bila diminta mengaktifkan <b>WSL 2</b>, setujui.",
    "<b>Restart</b> komputer bila diminta.",
    "Buka <b>Docker Desktop</b> dari Start Menu. Tunggu hingga ikon paus di system tray <b>berwarna hijau / \"Running\"</b>.",
])
P("Docker Desktop harus dalam keadaan <b>Running</b> setiap kali Anda ingin menjalankan aplikasi.", note)

# 3
P("3. Menyiapkan Folder Aplikasi", h1)
numbered([
    "Ekstrak folder aplikasi LA Tracker yang Anda terima, misalnya ke <font name='Courier'>C:\\la-tracker\\</font>",
    "Pastikan di dalamnya ada file <font name='Courier'>start.bat, stop.bat, docker-compose.yml</font> serta folder <font name='Courier'>backend\\</font> dan <font name='Courier'>frontend\\</font>.",
])

# 4
P("4. Menjalankan Aplikasi (Pertama Kali)", h1)
numbered([
    "Pastikan <b>Docker Desktop</b> sudah berjalan (ikon hijau).",
    "Klik dua kali file <b>start.bat</b>.",
    "Skrip akan otomatis: memeriksa Docker, membuat <font name='Courier'>local.env</font>, membuat folder database "
    "<font name='Courier'>data\\mongo</font> &amp; lampiran <font name='Courier'>data\\attachments</font>, "
    "<b>build image</b> (5–10 menit pertama kali), menjalankan MongoDB + backend + frontend, "
    "lalu membuka browser ke <b>http://localhost:3000</b>.",
])
P("Menjalankan berikutnya hanya butuh 10–15 detik karena image sudah dibangun.", note)

# 5
P("5. Login ke Aplikasi", h1)
P("Login memakai <b>USERNAME</b> (bukan email). Tersedia 3 akun bawaan:")
make_table([
    ["Username", "Password", "Peran", "Hak Akses"],
    ["`admin", "`admin123", "Administrator", "Akses penuh, kelola user & bank data"],
    ["`operator", "`operator", "Operator", "Input & edit Work Order / Invoice"],
    ["`guest", "`guest", "Viewer", "Hanya melihat (read-only)"],
], widths=[28 * mm, 28 * mm, 34 * mm, 80 * mm])
P("Password dapat diubah di file <b>local.env</b>, lalu jalankan <b>rebuild.bat</b>. "
  "Untuk keamanan, ganti password default setelah instalasi.", small)

# 6
P("6. Database (MongoDB) — Lokasi, Backup & Restore", h1)
P("Database berjalan otomatis dalam container Docker <font name='Courier'>la-tracker-mongo</font>. "
  "Anda <b>tidak perlu</b> menginstal MongoDB terpisah.")
P("6.1 Lokasi data (persisten di PC Anda)", h2)
story.append(Paragraph(
    "la-tracker\\<br/>├── data\\<br/>│&nbsp;&nbsp;&nbsp;├── mongo\\ &nbsp;&nbsp;&nbsp;&larr; isi database (Work Order, Invoice, Bank Data, User)<br/>"
    "│&nbsp;&nbsp;&nbsp;└── attachments\\ &nbsp;&larr; file lampiran (PDF/SPK/faktur)<br/>"
    "├── backups\\ &nbsp;&nbsp;&nbsp;&larr; hasil backup.bat<br/>└── local.env &nbsp;&larr; konfigurasi (password, JWT secret)", mono))
P("JANGAN menghapus folder <b>data\\</b> — di situlah seluruh database Anda berada.", note)
P("6.2 Backup database", h2)
P("Klik dua kali <b>backup.bat</b>. Skrip menyimpan salinan database MongoDB (<font name='Courier'>.archive.gz</font>) "
  "dan folder lampiran ke <font name='Courier'>backups\\</font> dengan penanda tanggal. Lakukan backup berkala.")
P("6.3 Pindah komputer / restore", h2)
numbered([
    "Matikan aplikasi (<b>stop.bat</b>).",
    "Salin folder <b>data\\</b> dan file <b>local.env</b> ke folder aplikasi di PC baru.",
    "Jalankan <b>start.bat</b> di PC baru — data langsung tersedia.",
])
P("6.4 Akses database langsung (opsional, untuk teknisi)", h2)
story.append(Paragraph("docker compose exec mongo mongosh la_tracker", mono))
P("Nama database: <b>la_tracker</b>.", small)

# 7
P("7. Akses dari PC Lain (LAN/WiFi Kantor)", h1)
numbered([
    "Pastikan <b>start.bat</b> berjalan di PC \"server\".",
    "Cari IPv4 PC server (ditampilkan di akhir start.bat, atau ketik <font name='Courier'>ipconfig</font>).",
    "Dari PC lain di jaringan yang sama, buka browser ke <font name='Courier'>http://&lt;IP-PC-SERVER&gt;:3000</font> "
    "(contoh <font name='Courier'>http://192.168.1.25:3000</font>).",
    "Bila diblokir Windows Firewall, izinkan Docker Desktop atau tambahkan aturan inbound port 3000.",
])
P("Keamanan: hanya buka port 3000 di jaringan internal. Jangan diekspos ke internet publik tanpa reverse proxy + HTTPS.", note)

# 8
P("8. Skrip yang Tersedia", h1)
make_table([
    ["Skrip", "Fungsi"],
    ["`start.bat", "Menyalakan semua layanan + buka browser"],
    ["`stop.bat", "Menghentikan semua layanan (data tetap aman)"],
    ["`rebuild.bat", "Membangun ulang setelah update / ubah local.env"],
    ["`backup.bat", "Backup database + lampiran ke folder backups\\"],
], widths=[35 * mm, 135 * mm])
P("Melihat log realtime (CMD di folder aplikasi):", small)
story.append(Paragraph("docker compose logs -f", mono))

# 9
P("9. Update Aplikasi (versi baru)", h1)
numbered([
    "Jalankan <b>stop.bat</b>.",
    "Timpa folder <font name='Courier'>backend\\, frontend\\, docker-compose.yml</font> dan file .bat dengan versi baru. "
    "JANGAN hapus folder <b>data\\</b> atau <b>local.env</b>.",
    "Jalankan <b>rebuild.bat</b>.",
])

# 10
P("10. Troubleshooting", h1)
make_table([
    ["Masalah", "Solusi"],
    ["\"Docker Desktop belum berjalan\"", "Buka Docker Desktop, tunggu ikon hijau, jalankan ulang start.bat."],
    ["Port 3000 dipakai aplikasi lain", "Edit docker-compose.yml: \"3000:80\" → mis. \"8080:80\", lalu rebuild.bat."],
    ["Build lama saat pertama kali", "Wajar (5–10 menit). Berikutnya hanya 10–15 detik."],
    ["Login gagal / API 401", "Logout dari menu profil, login ulang. Pastikan username & password benar."],
    ["Upload lampiran gagal", "Docker Desktop → Settings → Resources → File Sharing → tambahkan drive C:."],
    ["Lupa password admin", "Ubah ADMIN_PASSWORD di local.env, lalu rebuild.bat."],
    ["Ingin mulai dari database kosong", "stop.bat, hapus isi data\\mongo\\, lalu start.bat (semua data hilang)."],
], widths=[55 * mm, 115 * mm])

# TLDR
story.append(HRFlowable(width="100%", color=BORDER, spaceBefore=6, spaceAfter=6))
P("Ringkasan Cepat (TL;DR)", h1)
numbered([
    "Instal & jalankan <b>Docker Desktop</b> (tunggu ikon hijau).",
    "Klik <b>start.bat</b>.",
    "Buka <b>http://localhost:3000</b>.",
    "Login: <b>admin / admin123</b>.",
    "Backup rutin dengan <b>backup.bat</b>.",
])
P("Selamat menggunakan LA Tracker versi lokal!", small)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(20 * mm, 10 * mm, "LA Tracker — Panduan Instalasi Windows (Docker)")
    canvas.drawRightString(190 * mm, 10 * mm, "Halaman %d" % doc.page)
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=16 * mm, bottomMargin=20 * mm,
                        title="Panduan Instalasi LA Tracker (Windows)")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("PDF written:", OUT)
