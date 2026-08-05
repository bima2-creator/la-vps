import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { WORKORDERS } from "@/constants/testIds";
import { TABLE_COLUMNS, deriveSpkSummary, deriveCurrentActivity, deriveJenisPekerjaan } from "@/lib/workorder-schema";
import { formatIDR } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
} from "@/components/ui/alert-dialog";
import {
  MagnifyingGlass,
  Upload,
  DownloadSimple,
  Plus,
  PencilSimple,
  Trash,
  X,
} from "@phosphor-icons/react";

function StatusChip({ value }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const v = String(value).toUpperCase();
  const map = {
    PAID: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    LUNAS: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    DONE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    OK: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    OPEN: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    PENDING: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    SENT: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    REVISI: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    OVERDUE: "bg-red-500/10 text-red-400 border-red-500/30",
    BATAL: "bg-red-500/10 text-red-400 border-red-500/30",
  };
  const cls = map[v] || "bg-slate-100 text-muted-foreground border-border";
  return <span className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-widest border rounded-sm ${cls}`}>{v}</span>;
}

export default function WorkOrdersPage() {
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const canEdit = user && (user.role === "admin" || user.role === "operator");
  const canDelete = user && user.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [q, setQ] = useState("");
  const [invStatus, setInvStatus] = useState(searchParams.get("inv_status") || "");
  const [media, setMedia] = useState(searchParams.get("media_jenis") || "");
  const [mediaPerangkat, setMediaPerangkat] = useState(searchParams.get("media_perangkat") || "");
  const [jenisOrder, setJenisOrder] = useState(searchParams.get("jenis_order") || "");
  const [jenisPekerjaan, setJenisPekerjaan] = useState(searchParams.get("jenis_pekerjaan") || "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState([]);
  const [confirm, setConfirm] = useState({ open: false, ids: [], names: [] });
  const [deleting, setDeleting] = useState(false);
  const fileInput = useRef(null);

  // Sync filters to URL so links can be shared / user can bookmark filter state.
  useEffect(() => {
    const sp = new URLSearchParams();
    if (invStatus) sp.set("inv_status", invStatus);
    if (media) sp.set("media_jenis", media);
    if (mediaPerangkat) sp.set("media_perangkat", mediaPerangkat);
    if (jenisOrder) sp.set("jenis_order", jenisOrder);
    if (jenisPekerjaan) sp.set("jenis_pekerjaan", jenisPekerjaan);
    if (statusFilter) sp.set("status", statusFilter);
    setSearchParams(sp, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invStatus, media, mediaPerangkat, jenisOrder, jenisPekerjaan, statusFilter]);

  const activeChips = [];
  if (jenisOrder)
    activeChips.push({ key: "jenisOrder", label: `Jenis: ${jenisOrder}`, clear: () => setJenisOrder("") });
  if (jenisPekerjaan)
    activeChips.push({ key: "jenisPekerjaan", label: `Pekerjaan: ${jenisPekerjaan}`, clear: () => setJenisPekerjaan("") });
  if (statusFilter)
    activeChips.push({ key: "status", label: `Status: ${statusFilter.replace("_", " ")}`, clear: () => setStatusFilter("") });
  if (invStatus)
    activeChips.push({ key: "invStatus", label: `Invoice: ${invStatus}`, clear: () => setInvStatus("") });
  if (media) activeChips.push({ key: "media", label: `Media: ${media}`, clear: () => setMedia("") });
  if (mediaPerangkat)
    activeChips.push({ key: "mediaPerangkat", label: `Media Perangkat: ${mediaPerangkat}`, clear: () => setMediaPerangkat("") });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (q) params.q = q;
      if (invStatus) params.inv_status = invStatus;
      if (media) params.media_jenis = media;
      if (mediaPerangkat) params.media_perangkat = mediaPerangkat;
      if (jenisOrder) params.jenis_order = jenisOrder;
      if (jenisPekerjaan) params.jenis_pekerjaan = jenisPekerjaan;
      if (statusFilter) params.status = statusFilter;
      const { data } = await api.get("/workorders", { params });
      setItems(data.items);
      setTotal(data.total);
      setSelected([]);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, q, invStatus, media, mediaPerangkat, jenisOrder, jenisPekerjaan, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const onImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/workorders/import/xlsx", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Imported ${data.inserted} rows`);
      setPage(1);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Import failed");
    } finally {
      e.target.value = "";
    }
  };

  const onExport = async () => {
    try {
      const resp = await api.get("/workorders/export/xlsx", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "workorders.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Export failed");
    }
  };

  const onTemplate = async () => {
    try {
      const resp = await api.get("/workorders/import/template.xlsx", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "workorders_import_template.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Template download failed");
    }
  };

  const restoreDocs = async (docs) => {
    if (!docs || docs.length === 0) return;
    try {
      await api.post("/workorders/restore", { items: docs });
      toast.success(docs.length > 1 ? `${docs.length} work order dipulihkan` : "Work order dipulihkan");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal memulihkan");
    }
  };

  const askDelete = (ids, names) => setConfirm({ open: true, ids, names });

  const performDelete = async () => {
    const { ids } = confirm;
    if (!ids || ids.length === 0) return;
    setDeleting(true);
    try {
      let deletedDocs = [];
      if (ids.length === 1) {
        const { data } = await api.delete(`/workorders/${ids[0]}`);
        if (data?.deleted) deletedDocs = [data.deleted];
      } else {
        const { data } = await api.post("/workorders/bulk-delete", { ids });
        deletedDocs = data?.deleted || [];
      }
      setConfirm({ open: false, ids: [], names: [] });
      setSelected([]);
      load();
      const n = deletedDocs.length || ids.length;
      toast.success(n > 1 ? `${n} work order dihapus` : "Work order dihapus", {
        duration: 8000,
        action: deletedDocs.length
          ? { label: "Batalkan", onClick: () => restoreDocs(deletedDocs) }
          : undefined,
      });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal menghapus");
    } finally {
      setDeleting(false);
    }
  };

  const toggleSelect = (id) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const pageIds = items.map((it) => it.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.includes(id));
  const toggleSelectAll = () =>
    setSelected((prev) => (allSelected ? prev.filter((id) => !pageIds.includes(id)) : Array.from(new Set([...prev, ...pageIds]))));

  const nameFor = (id) => {
    const it = items.find((x) => x.id === id);
    return (it && it.pelanggan) || id;
  };

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div data-testid={WORKORDERS.root} className="p-6 lg:p-8 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Data</div>
          <h1 className="font-display text-4xl font-black tracking-tighter">Work Orders</h1>
          <p className="text-sm text-muted-foreground mt-1">
            <span className="mono">{total}</span> total · page{" "}
            <span className="mono">{page}</span>/<span className="mono">{pages}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canEdit && (
            <>
              <input
                ref={fileInput}
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={onImport}
                data-testid={WORKORDERS.importFileInput}
              />
              <button
                data-testid={WORKORDERS.importButton}
                onClick={() => fileInput.current?.click()}
                className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm transition-colors"
              >
                <Upload size={16} /> Import Excel
              </button>
              <button
                data-testid="wo-template-button"
                onClick={onTemplate}
                title="Download an Excel template ready to fill and import"
                className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm transition-colors"
              >
                <DownloadSimple size={16} /> Template
              </button>
            </>
          )}
          <button
            data-testid={WORKORDERS.exportButton}
            onClick={onExport}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm transition-colors"
          >
            <DownloadSimple size={16} /> Export
          </button>
          {canEdit && (
            <button
              data-testid={WORKORDERS.createButton}
              onClick={() => nav("/workorders/new")}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-2 rounded-sm transition-colors"
            >
              <Plus size={16} weight="bold" /> New Order
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <MagnifyingGlass
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            data-testid={WORKORDERS.searchInput}
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="Search pelanggan, SA ID, SPK, invoice…"
            className="w-full bg-secondary border border-border rounded-sm pl-9 pr-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          />
        </div>
        <select
          data-testid={WORKORDERS.invStatusFilter}
          value={invStatus}
          onChange={(e) => {
            setPage(1);
            setInvStatus(e.target.value);
          }}
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
        >
          <option value="">All Invoice Status</option>
          <option>OPEN</option>
          <option>SENT</option>
          <option>PAID</option>
          <option>OVERDUE</option>
        </select>
        <select
          data-testid={WORKORDERS.mediaFilter}
          value={media}
          onChange={(e) => {
            setPage(1);
            setMedia(e.target.value);
          }}
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
        >
          <option value="">All Media</option>
          <option>WIRELINE</option>
          <option>WIRELESS</option>
          <option>FIBER</option>
          <option>SATELLITE</option>
        </select>
        <select
          data-testid="workorders-jenis-filter"
          value={jenisOrder}
          onChange={(e) => {
            setPage(1);
            setJenisOrder(e.target.value);
          }}
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
        >
          <option value="">All Jenis Order</option>
          <option>PSB</option>
          <option>MUTASI</option>
          <option>MIGRASI</option>
          <option>DISMANTLE</option>
          <option>MAINTENANCE</option>
        </select>
        <select
          data-testid="workorders-jenis-pekerjaan-filter"
          value={jenisPekerjaan}
          onChange={(e) => {
            setPage(1);
            setJenisPekerjaan(e.target.value);
          }}
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
        >
          <option value="">All Jenis Pekerjaan</option>
          <option value="SURVEY">Survey</option>
          <option value="INSTALASI">Instalasi</option>
          <option value="AKTIVASI">Aktivasi</option>
          <option value="DISMANTLE">Dismantle</option>
          <option value="MAINTENANCE">Maintenance (all)</option>
          <option value="CM">— CM (Corrective)</option>
          <option value="PM">— PM (Preventive)</option>
        </select>
        <select
          data-testid="workorders-status-filter"
          value={statusFilter}
          onChange={(e) => {
            setPage(1);
            setStatusFilter(e.target.value);
          }}
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      {activeChips.length > 0 && (
        <div
          data-testid="workorders-active-filters"
          className="flex items-center gap-2 flex-wrap"
        >
          <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mono">
            Active filters:
          </span>
          {activeChips.map((c) => (
            <button
              key={c.key}
              data-testid={`workorders-active-chip-${c.key}`}
              onClick={() => {
                setPage(1);
                c.clear();
              }}
              className="inline-flex items-center gap-1.5 px-2 py-1 text-[11px] mono border border-blue-300 bg-blue-50 text-blue-700 rounded-sm hover:bg-blue-100"
            >
              {c.label} <X size={11} weight="bold" />
            </button>
          ))}
          <button
            data-testid="workorders-clear-all-filters"
            onClick={() => {
              setPage(1);
              setJenisOrder("");
              setJenisPekerjaan("");
              setStatusFilter("");
              setInvStatus("");
              setMedia("");
              setMediaPerangkat("");
            }}
            className="text-[11px] text-muted-foreground hover:text-red-600 underline underline-offset-2 ml-1"
          >
            clear all
          </button>
        </div>
      )}

      {canDelete && selected.length > 0 && (
        <div
          data-testid="workorders-bulk-bar"
          className="flex items-center gap-3 flex-wrap border border-red-300 bg-red-50 text-red-700 rounded-sm px-3 py-2"
        >
          <span className="text-sm font-medium">
            <span className="mono">{selected.length}</span> dipilih
          </span>
          <button
            data-testid="workorders-bulk-delete-button"
            onClick={() => askDelete(selected, selected.map(nameFor))}
            className="inline-flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white text-sm px-3 py-1.5 rounded-sm"
          >
            <Trash size={14} weight="bold" /> Hapus terpilih
          </button>
          <button
            onClick={() => setSelected([])}
            className="text-xs text-red-700/80 hover:text-red-900 underline underline-offset-2"
          >
            batalkan pilihan
          </button>
        </div>
      )}

      <div className="border border-border rounded-sm overflow-hidden bg-card">
        <div className="overflow-x-auto">
          <table className="w-full data-table text-sm">
            <thead className="bg-slate-50 sticky top-0 border-b border-border">
              <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                {canDelete && (
                  <th className="w-10 pl-3">
                    <input
                      type="checkbox"
                      data-testid="workorders-select-all"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="h-4 w-4 cursor-pointer accent-red-600"
                      aria-label="Select all"
                    />
                  </th>
                )}
                {TABLE_COLUMNS.map((c) => (
                  <th key={c.key} className="font-medium">
                    {c.label}
                  </th>
                ))}
                <th className="w-24"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={TABLE_COLUMNS.length + 1 + (canDelete ? 1 : 0)} className="text-center py-10 text-muted-foreground mono">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={TABLE_COLUMNS.length + 1 + (canDelete ? 1 : 0)} className="text-center py-10 text-muted-foreground">
                    No data. Import Excel or create your first Work Order.
                  </td>
                </tr>
              )}
              {items.map((it, i) => (
                <tr
                  key={it.id}
                  data-testid={WORKORDERS.row}
                  className={`border-b border-border/60 hover:bg-slate-100 ${i % 2 ? "bg-slate-50/60" : ""} ${selected.includes(it.id) ? "bg-red-50/70" : ""}`}
                >
                  {canDelete && (
                    <td className="pl-3">
                      <input
                        type="checkbox"
                        data-testid={`workorders-select-${it.id}`}
                        checked={selected.includes(it.id)}
                        onChange={() => toggleSelect(it.id)}
                        className="h-4 w-4 cursor-pointer accent-red-600"
                        aria-label="Select row"
                      />
                    </td>
                  )}
                  {TABLE_COLUMNS.map((c) => (
                    <td key={c.key} className={c.mono ? "mono text-[13px]" : ""}>
                      {c.key === "spk_summary" ? (
                        (() => {
                          const parts = deriveSpkSummary(it);
                          if (parts.length === 0)
                            return <span className="text-muted-foreground">—</span>;
                          return (
                            <div className="flex flex-col gap-0.5 text-[11px] mono">
                              {parts.map((p, idx) => (
                                <span key={idx}>{p}</span>
                              ))}
                            </div>
                          );
                        })()
                      ) : c.key === "jenis_pekerjaan" ? (
                        (() => {
                          const jp = deriveJenisPekerjaan(it);
                          if (!jp || jp === "—")
                            return <span className="text-muted-foreground">—</span>;
                          const jo = (it.jenis_order || "").toUpperCase();
                          const cls =
                            jo === "MAINTENANCE"
                              ? "bg-amber-50 text-amber-800 border-amber-200"
                              : jo === "DISMANTLE"
                              ? "bg-slate-100 text-slate-700 border-slate-300"
                              : "bg-blue-50 text-blue-700 border-blue-200";
                          return (
                            <span
                              className={`inline-flex px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono ${cls}`}
                            >
                              {jp}
                            </span>
                          );
                        })()
                      ) : c.key === "current_activity" ? (
                        (() => {
                          const a = deriveCurrentActivity(it);
                          if (!a.phase)
                            return <span className="text-muted-foreground">—</span>;
                          const label = a.phase[0].toUpperCase() + a.phase.slice(1);
                          const cls =
                            a.state === "on-going"
                              ? "bg-amber-100 text-amber-800 border-amber-200"
                              : a.state === "complete"
                              ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                              : "bg-slate-100 text-slate-700 border-slate-200";
                          const sub =
                            a.state === "on-going"
                              ? "On-going"
                              : a.state === "complete"
                              ? "Complete"
                              : "Done";
                          return (
                            <div className="inline-flex flex-col leading-tight">
                              <span
                                className={`inline-flex px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono ${cls}`}
                              >
                                {label}
                              </span>
                              <span className="text-[10px] text-muted-foreground mt-0.5">
                                {sub}
                              </span>
                            </div>
                          );
                        })()
                      ) : c.key === "inv_status" || c.key === "hasil_aktivasi_status" ? (
                        <StatusChip value={it[c.key]} />
                      ) : c.key === "pelanggan" ? (
                        it.pelanggan ? (
                          <button
                            type="button"
                            data-testid={`workorders-row-open-${it.id}`}
                            onClick={() => nav(`/workorders/${it.id}`)}
                            className="text-blue-600 hover:text-blue-800 hover:underline underline-offset-2 font-medium text-left"
                            title="Buka detail Work Order"
                          >
                            {it.pelanggan}
                          </button>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )
                      ) : c.numeric ? (
                        c.key === "boq_jumlah" ? (
                          formatIDR(it[c.key])
                        ) : (
                          Number(it[c.key] || 0).toLocaleString("id-ID")
                        )
                      ) : (
                        it[c.key] || <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  ))}
                  <td className="text-right pr-3">
                    <div className="inline-flex gap-1">
                      {canEdit && (
                        <button
                          data-testid={WORKORDERS.editRowButton}
                          onClick={() => nav(`/workorders/${it.id}`)}
                          className="p-1.5 rounded-sm hover:bg-blue-500/10 hover:text-blue-400"
                          title="Edit"
                        >
                          <PencilSimple size={14} />
                        </button>
                      )}
                      {canDelete && (
                        <button
                          data-testid={WORKORDERS.deleteRowButton}
                          onClick={() => askDelete([it.id], [it.pelanggan || it.id])}
                          className="p-1.5 rounded-sm hover:bg-red-500/10 hover:text-red-400"
                          title="Delete"
                        >
                          <Trash size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
          <div className="mono">
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </div>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 border border-border rounded-sm hover:bg-slate-100 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              className="px-3 py-1.5 border border-border rounded-sm hover:bg-slate-100 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <AlertDialog
        open={confirm.open}
        onOpenChange={(o) => !deleting && setConfirm((c) => ({ ...c, open: o }))}
      >
        <AlertDialogContent data-testid="workorders-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm.ids.length > 1
                ? `Hapus ${confirm.ids.length} Work Order?`
                : "Hapus Work Order ini?"}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p className="mb-2">
                  Tindakan ini menghapus data berikut. Anda masih bisa membatalkan
                  lewat tombol <span className="font-medium">Batalkan</span> selama
                  beberapa detik setelah dihapus.
                </p>
                <ul className="max-h-40 overflow-auto rounded-sm border border-border bg-secondary/50 p-2 text-sm space-y-0.5">
                  {confirm.names.slice(0, 8).map((n, i) => (
                    <li key={i} className="mono truncate">• {n}</li>
                  ))}
                  {confirm.names.length > 8 && (
                    <li className="text-muted-foreground">
                      …dan {confirm.names.length - 8} lainnya
                    </li>
                  )}
                </ul>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <button
              data-testid="workorders-delete-cancel"
              onClick={() => setConfirm({ open: false, ids: [], names: [] })}
              disabled={deleting}
              className="border border-border bg-secondary hover:bg-slate-100 text-sm px-4 py-2 rounded-sm disabled:opacity-60"
            >
              Batal
            </button>
            <button
              data-testid="workorders-delete-confirm"
              onClick={performDelete}
              disabled={deleting}
              className="inline-flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60"
            >
              <Trash size={15} weight="bold" />
              {deleting ? "Menghapus…" : "Ya, hapus"}
            </button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
