import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { REPORTS } from "@/constants/testIds";
import { formatIDR } from "@/lib/format";
import { toast } from "sonner";
import { FileText, DownloadSimple, Printer, Wrench, Lightning, ArrowsClockwise, ShareNetwork, HardDrives } from "@phosphor-icons/react";

const JENIS_ICON = {
  PSB: Lightning,
  MUTASI: ArrowsClockwise,
  MIGRASI: ShareNetwork,
  DISMANTLE: HardDrives,
  MAINTENANCE: Wrench,
};

const JENIS_ACCENT = {
  PSB: "border-blue-200 bg-blue-50/40",
  MUTASI: "border-indigo-200 bg-indigo-50/40",
  MIGRASI: "border-purple-200 bg-purple-50/40",
  DISMANTLE: "border-slate-300 bg-slate-50",
  MAINTENANCE: "border-amber-200 bg-amber-50/40",
};

function fmtIDR(n) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n || 0);
}

function SegmentCard({ seg }) {
  const Icon = JENIS_ICON[seg.jenis] || FileText;
  const accent = JENIS_ACCENT[seg.jenis] || "border-border bg-card";
  const s = seg.by_status || {};
  return (
    <div
      data-testid={`report-segment-${seg.jenis}`}
      className={`border rounded-sm p-4 ${accent} print:break-inside-avoid`}
    >
      <div className="flex items-start justify-between">
        <Icon size={22} weight="duotone" className="text-blue-600" />
        <span className="mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {seg.jenis}
        </span>
      </div>
      <div className="mt-3">
        <div className="font-display text-3xl font-black tracking-tighter mono">
          {seg.count}
        </div>
        <div className="text-[11px] uppercase tracking-widest text-muted-foreground mt-0.5">
          Work Orders
        </div>
      </div>

      {/* CM/PM breakdown for MAINTENANCE */}
      {seg.jenis === "MAINTENANCE" && (seg.count > 0) && (
        <div className="mt-3 flex gap-2 flex-wrap">
          <span
            data-testid="report-maintenance-cm"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-amber-300 bg-amber-100 text-amber-800 text-[10px] mono uppercase tracking-widest"
          >
            CM · {seg.cm_count}
          </span>
          <span
            data-testid="report-maintenance-pm"
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border border-emerald-300 bg-emerald-100 text-emerald-800 text-[10px] mono uppercase tracking-widest"
          >
            PM · {seg.pm_count}
          </span>
        </div>
      )}

      {/* Status split */}
      <div className="mt-4 grid grid-cols-3 gap-1.5 text-[10px] mono">
        <div className="border border-emerald-200 bg-white rounded-sm px-2 py-1.5">
          <div className="text-emerald-700 font-semibold">{s.completed || 0}</div>
          <div className="text-muted-foreground uppercase tracking-widest">Done</div>
        </div>
        <div className="border border-amber-200 bg-white rounded-sm px-2 py-1.5">
          <div className="text-amber-700 font-semibold">{s.in_progress || 0}</div>
          <div className="text-muted-foreground uppercase tracking-widest">Ongoing</div>
        </div>
        <div className="border border-slate-200 bg-white rounded-sm px-2 py-1.5">
          <div className="text-slate-700 font-semibold">{s.pending || 0}</div>
          <div className="text-muted-foreground uppercase tracking-widest">Pending</div>
        </div>
      </div>

      {/* Revenue + SLA */}
      <div className="mt-4 pt-3 border-t border-black/5 space-y-1.5">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground uppercase tracking-widest">Revenue</span>
          <span className="mono font-semibold text-foreground">
            {fmtIDR(seg.revenue_total)}
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground uppercase tracking-widest">Paid</span>
          <span className="mono text-emerald-700">
            {fmtIDR(seg.revenue_paid)}
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-muted-foreground uppercase tracking-widest">SLA</span>
          <span className="mono text-blue-700 font-semibold">
            {seg.sla_pct}% ({seg.sla_hit}/{seg.sla_hit + seg.sla_miss})
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [filters, setFilters] = useState({
    q: "",
    inv_status: "",
    media_jenis: "",
    jenis_order: "",
    date_from: "",
    date_to: "",
  });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [segments, setSegments] = useState([]);
  const [segTotals, setSegTotals] = useState(null);
  const [segLoading, setSegLoading] = useState(true);

  const loadSegments = async () => {
    setSegLoading(true);
    try {
      const params = {};
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.media_jenis) params.media_jenis = filters.media_jenis;
      const { data } = await api.get("/reports/by-jenis", { params });
      setSegments(data.segments || []);
      setSegTotals(data.totals || null);
    } catch (e) {
      toast.error("Gagal memuat report per jenis");
    } finally {
      setSegLoading(false);
    }
  };

  useEffect(() => {
    loadSegments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const apply = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.q) params.q = filters.q;
      if (filters.inv_status) params.inv_status = filters.inv_status;
      if (filters.media_jenis) params.media_jenis = filters.media_jenis;
      if (filters.jenis_order) params.jenis_order = filters.jenis_order;
      params.page = 1;
      params.page_size = 500;
      const { data } = await api.get("/workorders", { params });
      let rows = data.items;
      if (filters.date_from) rows = rows.filter((r) => (r.inv_tgl || "") >= filters.date_from);
      if (filters.date_to) rows = rows.filter((r) => (r.inv_tgl || "") <= filters.date_to);
      setItems(rows);
      setTotal(rows.length);
      // Also refresh segmented cards using same date/media filters
      await loadSegments();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  const exportXlsx = async () => {
    try {
      const resp = await api.get("/workorders/export/xlsx", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "report.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      toast.error("Export failed");
    }
  };

  const totalRevenue = items.reduce((sum, r) => sum + (Number(r.boq_jumlah) || 0), 0);
  const paidRevenue = items
    .filter((r) => ["PAID", "LUNAS"].includes((r.inv_status || "").toUpperCase()))
    .reduce((sum, r) => sum + (Number(r.boq_jumlah) || 0), 0);

  return (
    <div data-testid={REPORTS.root} className="p-6 lg:p-8 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-4 print:hidden">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Analytics</div>
          <h1 className="font-display text-4xl font-black tracking-tighter">Reports</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Filter dataset, ekspor Excel, cetak PDF via print dialog.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid={REPORTS.exportXlsxButton}
            onClick={exportXlsx}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
          >
            <DownloadSimple size={16} /> Excel
          </button>
          <button
            data-testid={REPORTS.exportPdfButton}
            onClick={async () => {
              try {
                const resp = await api.get("/workorders/export/pdf", {
                  responseType: "blob",
                  params: {
                    q: filters.q || undefined,
                    inv_status: filters.inv_status || undefined,
                    media_jenis: filters.media_jenis || undefined,
                  },
                });
                const url = window.URL.createObjectURL(new Blob([resp.data], { type: "application/pdf" }));
                window.open(url, "_blank");
              } catch (e) {
                toast.error("PDF export failed");
              }
            }}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
          >
            <Printer size={16} /> PDF
          </button>
        </div>
      </div>

      <div className="border border-border bg-card rounded-sm p-4 print:hidden">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <input
            placeholder="Search"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm md:col-span-2"
          />
          <select
            value={filters.inv_status}
            onChange={(e) => setFilters({ ...filters, inv_status: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          >
            <option value="">All Invoice</option>
            <option>OPEN</option>
            <option>SENT</option>
            <option>PAID</option>
            <option>LUNAS</option>
            <option>OVERDUE</option>
          </select>
          <select
            value={filters.media_jenis}
            onChange={(e) => setFilters({ ...filters, media_jenis: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          >
            <option value="">All Media</option>
            <option>WIRELINE</option>
            <option>WIRELESS</option>
            <option>FIBER</option>
            <option>SATELLITE</option>
          </select>
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm mono"
          />
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm mono"
          />
        </div>
        <div className="mt-3 flex justify-end">
          <button
            data-testid={REPORTS.applyButton}
            onClick={apply}
            className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm"
          >
            {loading ? "Loading…" : "Apply Filters"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="border border-border bg-card p-5 rounded-sm">
          <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Records</div>
          <div className="mt-2 font-display font-black text-3xl mono">{total}</div>
        </div>
        <div className="border border-border bg-card p-5 rounded-sm">
          <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Total Value</div>
          <div className="mt-2 font-display font-black text-2xl mono">{fmtIDR(totalRevenue)}</div>
        </div>
        <div className="border border-border bg-card p-5 rounded-sm">
          <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">Paid</div>
          <div className="mt-2 font-display font-black text-2xl mono text-emerald-400">{fmtIDR(paidRevenue)}</div>
        </div>
      </div>

      {/* Segmented Report per Jenis Order */}
      <div className="space-y-3" data-testid="report-by-jenis-section">
        <div className="flex items-end justify-between flex-wrap gap-2 print:hidden">
          <div>
            <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
              Segmented
            </div>
            <h2 className="font-display text-2xl font-bold tracking-tight">
              Report per Jenis Pekerjaan
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Volume, revenue &amp; SLA per jenis order. MAINTENANCE terpecah lagi
              menjadi CM (Corrective) &amp; PM (Preventive). Gunakan filter tanggal
              &amp; media di atas untuk mempersempit periode.
            </p>
          </div>
          {segTotals && (
            <div
              data-testid="report-segment-totals"
              className="text-right border border-border bg-card rounded-sm px-4 py-2"
            >
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                Total (semua jenis)
              </div>
              <div className="mono text-lg font-bold text-foreground">
                {segTotals.count} WO
              </div>
              <div className="mono text-[11px] text-muted-foreground">
                {fmtIDR(segTotals.revenue_total)} · SLA {segTotals.sla_pct}%
              </div>
            </div>
          )}
        </div>

        {segLoading ? (
          <div className="text-sm text-muted-foreground p-6 border border-dashed border-border rounded-sm text-center">
            Memuat segmentasi…
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {segments.map((seg) => (
              <SegmentCard key={seg.jenis} seg={seg} />
            ))}
          </div>
        )}
      </div>

      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <table className="w-full data-table text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th>Pelanggan</th>
              <th>SA ID</th>
              <th>Jenis</th>
              <th>Media</th>
              <th>Aktivasi</th>
              <th>Invoice</th>
              <th className="text-right">Jumlah</th>
              <th>Tgl Invoice</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-8 text-muted-foreground">
                  Apply filters to see the report.
                </td>
              </tr>
            )}
            {items.map((r, i) => (
              <tr key={r.id} className={`border-b border-border/60 ${i % 2 ? "bg-slate-50/60" : ""}`}>
                <td>{r.pelanggan || "—"}</td>
                <td className="mono">{r.sa_id || "—"}</td>
                <td>{r.jenis_order || "—"}</td>
                <td>{r.media_jenis || "—"}</td>
                <td>{r.hasil_aktivasi_status || "—"}</td>
                <td>{r.inv_status || "—"}</td>
                <td className="mono text-right">{formatIDR(r.boq_jumlah)}</td>
                <td className="mono">{r.inv_tgl || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
