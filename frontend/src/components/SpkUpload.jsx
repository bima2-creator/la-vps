import React, { useEffect, useRef, useState } from "react";
import { api, formatApiError, API_BASE } from "@/lib/api";
import { toast } from "sonner";
import { Upload, Trash, FilePdf, Download } from "@phosphor-icons/react";

/**
 * Dedicated "Upload SPK" widget for the SPK section of a Work Order.
 * SPK files are PDF-only and stored as work-order attachments with kind="spk"
 * so they are automatically included as lampiran (attachment) on the invoice.
 */
export default function SpkUpload({ workorderId, canEdit, onEnsureSaved }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const load = async (idArg) => {
    const wid = idArg || workorderId;
    if (!wid) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get(`/workorders/${wid}/attachments`);
      setItems((data || []).filter((a) => (a.kind || "general") === "spk"));
    } catch (e) {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [workorderId]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fname = (file.name || "").toLowerCase();
    const isPdf = file.type === "application/pdf" || fname.endsWith(".pdf");
    if (!isPdf) {
      toast.error("File SPK harus berformat PDF");
      e.target.value = "";
      return;
    }
    // If the work order hasn't been saved yet, create it on-the-fly first.
    let wid = workorderId;
    if (!wid && typeof onEnsureSaved === "function") {
      wid = await onEnsureSaved();
    }
    if (!wid) {
      e.target.value = "";
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", "spk");
    setUploading(true);
    try {
      await api.post(`/workorders/${wid}/attachments`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("SPK berhasil diupload");
      load(wid);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Upload SPK gagal");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const del = async (id) => {
    if (!window.confirm("Hapus file SPK ini?")) return;
    try {
      await api.delete(`/attachments/${id}`);
      toast.success("SPK dihapus");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal menghapus");
    }
  };

  const downloadUrl = (id) => {
    const token = localStorage.getItem("la_token") || "";
    return `${API_BASE}/attachments/${id}/download?auth=${encodeURIComponent(token)}`;
  };

  return (
    <div
      data-testid="spk-upload"
      className="mt-6 border border-blue-200 bg-blue-50/40 rounded-sm p-4"
    >
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-blue-700/80">
            Dokumen SPK
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Upload file SPK (PDF). File ini otomatis menjadi lampiran invoice.
          </div>
        </div>
        {canEdit && items.length === 0 && (
          <>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={upload}
              data-testid="spk-file-input"
            />
            <button
              type="button"
              data-testid="spk-upload-btn"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-2 rounded-sm disabled:opacity-60 transition-colors"
            >
              <Upload size={16} /> {uploading ? "Mengupload…" : "Upload SPK"}
            </button>
          </>
        )}
        {canEdit && items.length >= 1 && (
          <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded-sm">
            Hanya 1 file SPK. Hapus file lama untuk mengganti.
          </span>
        )}
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground mono">Memuat…</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-muted-foreground py-4 text-center border border-dashed border-blue-200 rounded-sm bg-white/60">
          Belum ada file SPK. Hanya file PDF yang diperbolehkan.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((a) => (
            <div
              key={a.id}
              data-testid="spk-item"
              className="flex items-center gap-3 bg-white border border-border rounded-sm px-3 py-2"
            >
              <FilePdf size={22} weight="duotone" className="text-red-500 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="text-sm truncate" title={a.original_filename}>
                  {a.original_filename}
                </div>
                <div className="text-[10px] mono text-muted-foreground">
                  {(a.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <a
                href={downloadUrl(a.id)}
                target="_blank"
                rel="noreferrer"
                className="text-xs inline-flex items-center gap-1 border border-border px-2 py-1 rounded-sm hover:bg-slate-100"
              >
                <Download size={12} /> Lihat
              </a>
              {canEdit && (
                <button
                  type="button"
                  data-testid="spk-delete-btn"
                  onClick={() => del(a.id)}
                  className="p-1.5 rounded-sm hover:bg-red-500/10 hover:text-red-500 border border-border"
                >
                  <Trash size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
