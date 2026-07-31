# LA Tracker — Instalasi Lokal (Windows + Docker)

Paket ini menjalankan LA Tracker **100% di PC/notebook Anda**. Data tersimpan
di folder `.\data\` (MongoDB + attachment file). Aplikasi bisa diakses dari
PC itu sendiri **maupun** dari PC lain di jaringan LAN/WiFi kantor.

---

## 1. Persyaratan

- Windows 10 / 11 (64-bit)
- **Docker Desktop for Windows** — [download di sini](https://www.docker.com/products/docker-desktop/)
  - Setelah instalasi, buka Docker Desktop **sekali** sampai icon paus berwarna hijau di system tray.
- RAM minimum 4 GB untuk container (8 GB direkomendasikan)
- 2 GB ruang disk

> Tidak perlu install Node.js, Python, atau MongoDB terpisah. Semua otomatis
> lewat Docker.

---

## 2. Menjalankan pertama kali

1. Extract folder aplikasi ini (misal ke `C:\la-tracker\`).
2. Klik dua kali **`start.bat`**.
3. Skrip akan:
   - memeriksa Docker Desktop,
   - membuat `local.env` dari template (bila belum ada),
   - membuat folder `data\mongo` dan `data\attachments`,
   - **build image** (5–10 menit pertama kali),
   - menjalankan container,
   - membuka browser otomatis ke `http://localhost:3000`.

Login default:

| Field    | Value                    |
|----------|--------------------------|
| Email    | `admin@la-tracker.com`   |
| Password | `admin123`               |

Anda bisa ubah kredensial ini di file `local.env` **sebelum** startup pertama.
Setelah admin dibuat, ubah password lewat menu **Users** di aplikasi.

---

## 3. Akses dari PC lain di jaringan (LAN/WiFi kantor)

1. Pastikan `start.bat` sudah berjalan di PC "server".
2. Cek IPv4 PC server (skrip `start.bat` menampilkannya di akhir, atau ketik
   `ipconfig` di CMD).
3. Dari PC lain (dalam WiFi/LAN yang sama), buka browser ke:

   ```
   http://<IP-PC-SERVER>:3000
   ```

   Contoh: `http://192.168.1.25:3000`

4. Bila Windows Firewall memblokir, izinkan **Docker Desktop / vpnkit** saat
   diminta, atau tambahkan rule inbound untuk port `3000`.

> Untuk keamanan: hanya buka port 3000 di jaringan internal Anda. Jangan
> ekspos ke internet publik tanpa reverse proxy + HTTPS.

---

## 4. Skrip yang tersedia

| Skrip           | Fungsi                                                             |
|-----------------|--------------------------------------------------------------------|
| `start.bat`     | Menyalakan semua service dan buka browser                          |
| `stop.bat`      | Menghentikan semua service (data tetap aman)                       |
| `rebuild.bat`   | Rebuild image setelah update source code                           |
| `backup.bat`    | Backup MongoDB (`.archive.gz`) + attachments ke folder `backups\`  |

Log realtime: buka CMD di folder ini lalu jalankan:

```
docker compose logs -f
```

---

## 5. Struktur folder data (jangan dihapus)

```
la-tracker\
├── data\
│   ├── mongo\           ← database MongoDB
│   └── attachments\     ← file upload per work order
├── backups\             ← hasil backup.bat
└── local.env            ← konfigurasi (admin, JWT secret)
```

**Untuk pindah komputer:** copy folder `data\` + `local.env` ke PC baru,
lalu jalankan `start.bat` di sana.

---

## 6. Migrasi data dari environment Preview (Cloud)

Karena Anda ingin memindahkan data dari server preview yang lama:

1. Login ke aplikasi **preview** sebagai admin.
2. Buka menu **Work Orders → Export** (icon download). Simpan file `.xlsx`.
3. Jalankan `start.bat` di PC lokal, login dengan admin default.
4. Buka menu **Work Orders → Import**, pilih file `.xlsx` tadi.
5. (Opsional) Buat ulang user Operator/Viewer melalui menu **Users**.

> Attachment (foto/PDF di preview) saat ini tersimpan di object storage
> Emergent. Kalau butuh migrasi attachment, download satu per satu dari UI
> preview lalu unggah kembali di instalasi lokal, atau hubungi saya bila
> perlu skrip migrasi khusus.

---

## 7. Update aplikasi

Bila Anda menerima source code versi baru:

1. `stop.bat`
2. Timpa folder `backend\`, `frontend\`, `docker-compose.yml`, dan `.bat`
   dengan versi baru. **Jangan** hapus folder `data\` atau `local.env`.
3. `rebuild.bat`

---

## 8. Troubleshooting

- **"Docker Desktop belum berjalan"** → buka Docker Desktop, tunggu sampai
  icon hijau, lalu jalankan ulang `start.bat`.
- **Port 3000 dipakai aplikasi lain** → edit `docker-compose.yml`, ubah baris
  `"3000:80"` ke port lain, misal `"8080:80"`, lalu `rebuild.bat`.
- **App lambat pertama kali dibuka** → build image butuh waktu 5–10 menit.
  Setelahnya start.bat hanya butuh 10–15 detik.
- **Login berhasil tapi API 401** → kemungkinan cookie/token stale. Klik
  Logout dari menu profil lalu login ulang.
- **Attachment upload gagal** → pastikan folder `data\attachments\` bisa
  ditulis oleh Docker (Docker Desktop → Settings → Resources → File Sharing
  → tambahkan drive C:).

---

Selamat menggunakan LA Tracker versi lokal! 🇮🇩
