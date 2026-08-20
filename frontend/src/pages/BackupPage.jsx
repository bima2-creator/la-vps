import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import {
  FloppyDisk,
  DownloadSimple,
  UploadSimple,
  FileZip,
  ArrowCounterClockwise,
  Trash,
  ArrowClockwise,
  Database,
  Clock,
} from "@phosphor-icons/react";

const fmtBytes = (n) => {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(n) / Math.log(1024));
  return `${(n / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`;
};

const fmtDate = (iso) => {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

export default function BackupPage() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState(null);
  const fileRef = useRef(null);
  const zipRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/backups");
      setBackups(data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const backupNow = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/backups");
      toast.success(`Backup dibuat: ${data.filename} (${data.total_docs} data)`);
      load();
    } catch (e) {
      toast.error(formatApiError(e) || "Gagal membuat backup");
    } finally {
      setBusy(false);
    }
  };

  const uploadBackup = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/backups/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Backup diunggah: ${data.filename} (${data.total_docs} data). Klik ikon Restore untuk memulihkan.`);
      load();
    } catch (err) {
      toast.error(formatApiError(err) || "Gagal mengunggah backup");
    } finally {
      setBusy(false);
    }
  };

  const uploadAttachmentsZip = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post("/backups/attachments/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(data.message || `${data.extracted} file lampiran diekstrak`);
    } catch (err) {
      toast.error(formatApiError(err) || "Gagal mengunggah ZIP lampiran");
    } finally {
      setBusy(false);
    }
  };

  const download = async (b) => {
    try {
      const resp = await api.get(`/backups/${b.id}/download`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = b.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      toast.error("Gagal mengunduh backup");
    }
  };

  const doRestore = async () => {
    const b = confirmRestore;
    setConfirmRestore(null);
    setBusy(true);
    try {
      const { data } = await api.post(`/backups/${b.id}/restore`);
      toast.success(data.message || "Restore selesai");
      load();
    } catch (e) {
      toast.error(formatApiError(e) || "Gagal restore");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (b) => {
    if (!window.confirm(`Hapus backup ${b.filename}?`)) return;
    try {
      await api.delete(`/backups/${b.id}`);
      toast.success("Backup dihapus");
      load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  return (
    <div data-testid="backup-page" className="p-6 lg:p-8 space-y-5">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Admin
          </div>
          <h1 className="font-display text-4xl font-black tracking-tighter flex items-center gap-3">
            <Database size={30} weight="duotone" className="text-blue-500" />
            Backup Data
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Cadangkan seluruh data (Work Order, Invoice, Perangkat, Users, dll) ke
            file JSON. Backup otomatis berjalan <b>setiap hari</b> &amp; sistem
            menyimpan <b>7 backup terakhir</b>.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="backup-refresh"
            onClick={load}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
          >
            <ArrowClockwise size={16} /> Muat Ulang
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            onChange={uploadBackup}
            className="hidden"
            data-testid="backup-upload-input"
          />
          <input
            ref={zipRef}
            type="file"
            accept=".zip,application/zip,application/x-zip-compressed"
            onChange={uploadAttachmentsZip}
            className="hidden"
            data-testid="backup-upload-zip-input"
          />
          <button
            data-testid="backup-upload-zip"
            onClick={() => zipRef.current?.click()}
            disabled={busy}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 disabled:opacity-60 text-sm px-3 py-2 rounded-sm"
            title="Unggah ZIP folder data/attachments dari PC lain — file lampiran diekstrak otomatis ke server"
          >
            <FileZip size={16} /> Upload Lampiran (ZIP)
          </button>
          <button
            data-testid="backup-upload"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 disabled:opacity-60 text-sm px-3 py-2 rounded-sm"
            title="Unggah file backup JSON dari instance/PC lain"
          >
            <UploadSimple size={16} /> Upload Backup
          </button>
          <button
            data-testid="backup-now"
            onClick={backupNow}
            disabled={busy}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm px-4 py-2 rounded-sm"
          >
            <FloppyDisk size={16} weight="bold" />
            {busy ? "Memproses…" : "Backup Sekarang"}
          </button>
        </div>
      </div>

      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead className="bg-slate-50 border-b border-border">
              <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                <th className="px-3 py-2">Nama File</th>
                <th className="px-3 py-2">Tipe</th>
                <th className="px-3 py-2">Waktu</th>
                <th className="px-3 py-2 text-right">Jumlah Data</th>
                <th className="px-3 py-2 text-right">Ukuran</th>
                <th className="px-3 py-2 w-40 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted-foreground">
                    Memuat…
                  </td>
                </tr>
              ) : backups.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12">
                    <Database size={30} weight="duotone" className="mx-auto text-muted-foreground mb-2" />
                    <div className="text-sm text-muted-foreground">
                      Belum ada backup. Klik <b>Backup Sekarang</b> untuk membuat
                      backup pertama.
                    </div>
                  </td>
                </tr>
              ) : (
                backups.map((b, i) => (
                  <tr
                    key={b.id}
                    data-testid={`backup-row-${i}`}
                    className={`border-b border-border/60 hover:bg-blue-50/40 ${i % 2 ? "bg-slate-50/40" : ""}`}
                  >
                    <td className="px-3 py-2 mono text-blue-700">{b.filename}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono ${
                          b.kind === "auto"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : b.kind === "uploaded"
                            ? "bg-purple-50 text-purple-700 border-purple-200"
                            : b.kind === "pre-restore"
                            ? "bg-amber-50 text-amber-700 border-amber-200"
                            : "bg-blue-50 text-blue-700 border-blue-200"
                        }`}
                      >
                        {b.kind === "auto" ? <Clock size={11} weight="fill" /> : null}
                        {b.kind === "auto"
                          ? "Otomatis"
                          : b.kind === "uploaded"
                          ? "Upload"
                          : b.kind === "pre-restore"
                          ? "Pra-Restore"
                          : "Manual"}
                      </span>
                    </td>
                    <td className="px-3 py-2 mono text-xs">{fmtDate(b.created_at)}</td>
                    <td className="px-3 py-2 text-right mono">{b.total_docs}</td>
                    <td className="px-3 py-2 text-right mono text-xs">{fmtBytes(b.size)}</td>
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      <button
                        data-testid={`backup-download-${i}`}
                        onClick={() => download(b)}
                        className="p-1 mr-1 text-slate-600 hover:text-blue-600"
                        title="Unduh JSON"
                      >
                        <DownloadSimple size={16} />
                      </button>
                      <button
                        data-testid={`backup-restore-${i}`}
                        onClick={() => setConfirmRestore(b)}
                        className="p-1 mr-1 text-amber-600 hover:text-amber-700"
                        title="Pulihkan data dari backup ini"
                      >
                        <ArrowCounterClockwise size={16} />
                      </button>
                      <button
                        data-testid={`backup-delete-${i}`}
                        onClick={() => remove(b)}
                        className="p-1 text-slate-500 hover:text-red-600"
                        title="Hapus backup"
                      >
                        <Trash size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Restore confirmation */}
      {confirmRestore && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            data-testid="backup-restore-confirm"
            className="bg-card border border-border rounded-md w-full max-w-md shadow-xl"
          >
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-display text-lg font-bold flex items-center gap-2 text-amber-600">
                <ArrowCounterClockwise size={20} weight="bold" /> Konfirmasi Restore
              </h3>
            </div>
            <div className="px-5 py-4 text-sm space-y-2">
              <p>
                Anda akan memulihkan data dari{" "}
                <b className="mono">{confirmRestore.filename}</b>.
              </p>
              <p className="text-red-600 font-medium">
                ⚠️ Semua data saat ini (Work Order, Invoice, Perangkat, dll) akan
                DITIMPA dengan isi backup ini. Tindakan tidak dapat dibatalkan.
              </p>
              <p className="text-muted-foreground text-xs">
                Aman: sistem otomatis membuat backup "Pra-Restore" dari kondisi
                saat ini sebelum data ditimpa.
              </p>
            </div>
            <div className="px-5 py-4 border-t border-border flex justify-end gap-2 bg-slate-50">
              <button
                data-testid="backup-restore-cancel"
                onClick={() => setConfirmRestore(null)}
                className="border border-border bg-white hover:bg-slate-100 rounded-sm px-4 py-2 text-sm"
              >
                Batal
              </button>
              <button
                data-testid="backup-restore-confirm-btn"
                onClick={doRestore}
                disabled={busy}
                className="bg-amber-600 hover:bg-amber-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-sm"
              >
                {busy ? "Memulihkan…" : "Ya, Restore Sekarang"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
