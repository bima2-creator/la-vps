import React, { useEffect, useRef, useState } from "react";
import { api, formatApiError, API_BASE } from "@/lib/api";
import { ATTACHMENTS } from "@/constants/testIds";
import { toast } from "sonner";
import { Upload, Trash, FileText, ImageSquare, Download } from "@phosphor-icons/react";

export default function Attachments({ workorderId, canEdit }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/workorders/${workorderId}/attachments`);
      setItems(data);
    } catch (e) {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workorderId) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workorderId]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fname = (file.name || "").toLowerCase();
    const isPdf = file.type === "application/pdf" || fname.endsWith(".pdf");
    if (!isPdf) {
      toast.error("Hanya file PDF yang diperbolehkan sebagai attachment");
      e.target.value = "";
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      await api.post(`/workorders/${workorderId}/attachments`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Uploaded");
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this attachment?")) return;
    try {
      await api.delete(`/attachments/${id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Delete failed");
    }
  };

  const downloadUrl = (id) => {
    const token = localStorage.getItem("la_token") || "";
    return `${API_BASE}/attachments/${id}/download?auth=${encodeURIComponent(token)}`;
  };

  const isImage = (ct) => (ct || "").startsWith("image/");

  return (
    <div data-testid={ATTACHMENTS.root} className="border border-border bg-card rounded-sm p-5 mt-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Attachments</div>
          <div className="text-xs text-muted-foreground mt-1 mono">
            {items.length} file{items.length === 1 ? "" : "s"}
          </div>
        </div>
        {canEdit && (
          <>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={upload}
              data-testid={ATTACHMENTS.fileInput}
            />
            <button
              data-testid={ATTACHMENTS.uploadButton}
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm disabled:opacity-60"
            >
              <Upload size={16} /> {uploading ? "Uploading…" : "Upload"}
            </button>
          </>
        )}
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground mono">Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-muted-foreground py-6 text-center border border-dashed border-border rounded-sm">
          No attachments yet. Upload BAST, SLA, or supporting documents in PDF format.
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {items.map((a) => (
            <div
              key={a.id}
              data-testid={ATTACHMENTS.item}
              className="border border-border bg-slate-50 rounded-sm p-3 flex flex-col gap-2 hover:border-blue-500/40 transition-colors"
            >
              <div className="h-24 flex items-center justify-center bg-black rounded-sm overflow-hidden">
                {isImage(a.content_type) ? (
                  <img src={downloadUrl(a.id)} alt={a.original_filename || "attachment"} className="max-h-full object-contain" />
                ) : (
                  <FileText size={40} weight="thin" className="text-muted-foreground" />
                )}
              </div>
              <div className="text-xs truncate" title={a.original_filename}>
                {a.original_filename}
              </div>
              <div className="text-[10px] mono text-muted-foreground">
                {(a.size / 1024).toFixed(1)} KB
              </div>
              <div className="flex gap-1">
                <a
                  href={downloadUrl(a.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex-1 text-xs inline-flex items-center justify-center gap-1 border border-border py-1 rounded-sm hover:bg-slate-100"
                >
                  <Download size={12} /> View
                </a>
                {canEdit && (
                  <button
                    data-testid={ATTACHMENTS.deleteButton}
                    onClick={() => del(a.id)}
                    className="p-1.5 rounded-sm hover:bg-red-500/10 hover:text-red-400 border border-border"
                  >
                    <Trash size={12} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
