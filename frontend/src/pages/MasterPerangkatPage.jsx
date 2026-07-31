import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  HardDrives,
  MagnifyingGlass,
  DownloadSimple,
  X,
  ArrowSquareOut,
  Package,
} from "@phosphor-icons/react";

const STATUS_STYLE = {
  TERPASANG_INSTAL: "bg-emerald-50 text-emerald-700 border-emerald-200",
  TERPASANG_MAINT: "bg-teal-50 text-teal-700 border-teal-200",
  MAINTENANCE: "bg-red-50 text-red-700 border-red-200",
  DISMANTLED: "bg-slate-100 text-slate-600 border-slate-200",
  UNKNOWN: "bg-slate-50 text-slate-500 border-slate-200",
  // legacy fallback
  TERPASANG: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

const STATUS_LABEL = {
  TERPASANG_INSTAL: "Terpasang untuk Instal/Aktivasi",
  TERPASANG_MAINT: "Terpasang untuk Maintenance",
  MAINTENANCE: "Problem/Rusak",
  DISMANTLED: "Dismantled",
  UNKNOWN: "Unknown",
  TERPASANG: "Terpasang",
};

const JENIS_STYLE = {
  PSB: "text-blue-700 bg-blue-50 border-blue-200",
  MUTASI: "text-indigo-700 bg-indigo-50 border-indigo-200",
  MIGRASI: "text-purple-700 bg-purple-50 border-purple-200",
  DISMANTLE: "text-slate-700 bg-slate-100 border-slate-300",
  MAINTENANCE: "text-amber-700 bg-amber-50 border-amber-200",
};

function KpiCard({ label, value, sub, testid, onClick, active }) {
  const clickable = typeof onClick === "function";
  return (
    <div
      data-testid={testid}
      onClick={onClick}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => (e.key === "Enter" || e.key === " ") && onClick() : undefined}
      className={`border bg-card p-5 rounded-sm transition-all ${
        clickable ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md" : ""
      } ${active ? "border-blue-500 ring-1 ring-blue-500" : "border-border"}`}
    >
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground leading-tight min-h-[24px]">
        {label}
      </div>
      <div className="mt-2 font-display font-black text-3xl mono">{value}</div>
      {sub && (
        <div className="text-[11px] text-muted-foreground mt-2 mono">{sub}</div>
      )}
    </div>
  );
}

function Badge({ children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-[0.15em] mono ${className}`}
    >
      {children}
    </span>
  );
}

function DrillPanel({ device, onClose }) {
  const nav = useNavigate();
  if (!device) return null;
  return (
    <div
      data-testid="perangkat-drill-overlay"
      className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl h-full bg-white border-l border-border overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        data-testid="perangkat-drill-panel"
      >
        <div className="p-5 border-b border-border flex items-start justify-between gap-4 sticky top-0 bg-white z-10">
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Perangkat
            </div>
            <div className="font-display text-2xl font-bold tracking-tight truncate">
              {device.nama || "(tanpa nama)"}
            </div>
            <div className="mono text-sm text-blue-600 mt-1">
              {device.nomor_registrasi}
            </div>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <Badge className={STATUS_STYLE[device.current_status] || STATUS_STYLE.UNKNOWN}>
                {STATUS_LABEL[device.current_status] || device.current_status}
              </Badge>
              <Badge className="bg-slate-50 text-slate-700 border-slate-200">
                {device.wo_count} WO
              </Badge>
              {device.latest_media && (
                <Badge className="bg-cyan-50 text-cyan-700 border-cyan-200">
                  {device.latest_media}
                </Badge>
              )}
            </div>
          </div>
          <button
            data-testid="perangkat-drill-close"
            onClick={onClose}
            className="p-2 rounded-sm hover:bg-slate-100 text-muted-foreground"
          >
            <X size={16} />
          </button>
        </div>

        <div className="p-5">
          <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-3">
            Riwayat Work Order ({device.wo_count})
          </div>
          <ol className="space-y-2">
            {(device.wo_history || []).map((h, i) => {
              const jClass = JENIS_STYLE[h.jenis_order] || "bg-slate-50 text-slate-700 border-slate-200";
              return (
                <li
                  key={h.wo_id + i}
                  data-testid={`perangkat-history-row-${i}`}
                  className="border border-border rounded-sm p-3 bg-slate-50/50 hover:bg-blue-50/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className={jClass}>{h.jenis_order || "-"}</Badge>
                        {h.wo_jenis_pekerjaan && h.jenis_order !== "MAINTENANCE" && (
                          <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">
                            Tipro: {h.wo_jenis_pekerjaan}
                          </Badge>
                        )}
                        {h.maintenance_type && (
                          <Badge className="bg-amber-50 text-amber-700 border-amber-200">
                            {h.maintenance_type === "CM" ? "Corrective" : "Preventive"}
                          </Badge>
                        )}
                        {h.role && (
                          <Badge
                            className={
                              h.role === "dicabut"
                                ? "bg-red-50 text-red-700 border-red-200"
                                : h.role === "pengganti"
                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                : "bg-emerald-50 text-emerald-700 border-emerald-200"
                            }
                          >
                            {h.role === "dicabut"
                              ? "Dicabut/Rusak"
                              : h.role === "pengganti"
                              ? "Pengganti"
                              : "Eksisting"}
                          </Badge>
                        )}
                        {i === 0 && (
                          <Badge className="bg-blue-600 text-white border-blue-600">
                            Latest
                          </Badge>
                        )}
                      </div>
                      <div className="mt-2 text-sm font-medium truncate">
                        {h.pelanggan || "(no customer)"}
                      </div>
                      <div className="text-[11px] text-muted-foreground mono mt-0.5">
                        SA {h.sa_id || "-"} · SI {h.si_id || "-"} ·{" "}
                        {(h.created_at || "").slice(0, 10)}
                      </div>
                    </div>
                    <button
                      data-testid={`perangkat-history-open-wo-${i}`}
                      onClick={() => nav(`/workorders/${h.wo_id}`)}
                      className="text-xs inline-flex items-center gap-1 border border-border bg-white hover:bg-blue-50 hover:text-blue-700 px-2 py-1 rounded-sm transition-colors"
                    >
                      Open WO <ArrowSquareOut size={12} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </div>
  );
}

export default function MasterPerangkatPage() {
  const [q, setQ] = useState("");
  const [jenisWO, setJenisWO] = useState("");
  const [status, setStatus] = useState("");
  const [data, setData] = useState({ kpi: {}, items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [drill, setDrill] = useState(null);

  const load = async (overrides = {}) => {
    setLoading(true);
    try {
      const eff = { q, jenisWO, status, ...overrides };
      const params = { page: 1, page_size: 500 };
      if (eff.q) params.q = eff.q;
      if (eff.jenisWO) params.jenis_wo = eff.jenisWO;
      if (eff.status) params.status = eff.status;
      const { data } = await api.get("/perangkat/registry", { params });
      setData(data);
    } catch (e) {
      toast.error("Gagal memuat registry perangkat");
    } finally {
      setLoading(false);
    }
  };

  const filterByStatus = (val) => {
    const next = status === val ? "" : val; // toggle off if already active
    setStatus(next);
    load({ status: next });
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exportCsv = async () => {
    try {
      const params = {};
      if (q) params.q = q;
      if (jenisWO) params.jenis_wo = jenisWO;
      if (status) params.status = status;
      const resp = await api.get("/perangkat/export/csv", {
        params,
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "perangkat-registry.csv";
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("CSV diunduh");
    } catch (e) {
      toast.error("Gagal ekspor CSV");
    }
  };

  const byStatus = data.kpi?.by_status || {};
  const terpasangInstal = byStatus.TERPASANG_INSTAL || 0;
  const terpasangMaint = byStatus.TERPASANG_MAINT || 0;
  const problem = byStatus.MAINTENANCE || 0;
  const dismantled = byStatus.DISMANTLED || 0;

  const items = data.items || [];

  return (
    <div data-testid="master-perangkat-page" className="p-6 lg:p-8 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Asset Tracking
          </div>
          <h1 className="font-display text-4xl font-black tracking-tighter">
            Flow Perangkat
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Registry unik perangkat berdasarkan nomor registrasi, di-aggregate
            dari semua Work Order. Klik baris untuk melihat riwayat WO.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="perangkat-export-csv"
            onClick={exportCsv}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
          >
            <DownloadSimple size={16} /> Export CSV
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <KpiCard
          testid="perangkat-kpi-total"
          label="Total Perangkat"
          value={data.kpi?.total_devices ?? 0}
          active={status === ""}
          onClick={() => filterByStatus("")}
        />
        <KpiCard
          testid="perangkat-kpi-terpasang-instal"
          label="Terpasang untuk Instal/Aktivasi"
          value={terpasangInstal}
          active={status === "TERPASANG_INSTAL"}
          onClick={() => filterByStatus("TERPASANG_INSTAL")}
        />
        <KpiCard
          testid="perangkat-kpi-terpasang-maint"
          label="Terpasang untuk Maintenance"
          value={terpasangMaint}
          active={status === "TERPASANG_MAINT"}
          onClick={() => filterByStatus("TERPASANG_MAINT")}
        />
        <KpiCard
          testid="perangkat-kpi-problem"
          label="Problem/Rusak"
          value={problem}
          active={status === "MAINTENANCE"}
          onClick={() => filterByStatus("MAINTENANCE")}
        />
        <KpiCard
          testid="perangkat-kpi-dismantled"
          label="Dismantled"
          value={dismantled}
          active={status === "DISMANTLED"}
          onClick={() => filterByStatus("DISMANTLED")}
        />
      </div>

      {/* Filters */}
      <div className="border border-border bg-card rounded-sm p-4">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <div className="md:col-span-3 relative">
            <MagnifyingGlass
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              data-testid="perangkat-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") load();
              }}
              placeholder="Cari nomor registrasi, nama perangkat, pelanggan…"
              className="w-full bg-secondary border border-border rounded-sm pl-9 pr-3 py-2 text-sm"
            />
          </div>
          <select
            data-testid="perangkat-filter-jenis"
            value={jenisWO}
            onChange={(e) => setJenisWO(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          >
            <option value="">Semua Jenis (latest)</option>
            <option>PSB</option>
            <option>MUTASI</option>
            <option>MIGRASI</option>
            <option>DISMANTLE</option>
            <option>MAINTENANCE</option>
          </select>
          <select
            data-testid="perangkat-filter-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          >
            <option value="">Semua Status</option>
            <option value="TERPASANG_INSTAL">Terpasang untuk Instal/Aktivasi</option>
            <option value="TERPASANG_MAINT">Terpasang untuk Maintenance</option>
            <option value="MAINTENANCE">Problem/Rusak</option>
            <option value="DISMANTLED">Dismantled</option>
          </select>
          <button
            data-testid="perangkat-apply-filters"
            onClick={() => load()}
            className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm"
          >
            {loading ? "Memuat…" : "Terapkan"}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th className="px-3 py-2">Nomor Registrasi</th>
              <th className="px-3 py-2">Nama Perangkat</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Jenis Latest</th>
              <th className="px-3 py-2">Pelanggan Terakhir</th>
              <th className="px-3 py-2 text-right">Jumlah WO</th>
              <th className="px-3 py-2 w-16"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-8 text-muted-foreground">
                  Memuat…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12">
                  <Package
                    size={32}
                    weight="duotone"
                    className="mx-auto text-muted-foreground mb-2"
                  />
                  <div className="text-sm text-muted-foreground">
                    Belum ada perangkat. Isi <b>Perangkat Terpasang</b> pada
                    Work Order untuk mulai membangun registry.
                  </div>
                </td>
              </tr>
            ) : (
              items.map((d, i) => {
                const jClass =
                  JENIS_STYLE[d.latest_jenis_order] ||
                  "bg-slate-50 text-slate-700 border-slate-200";
                return (
                  <tr
                    key={d.nomor_registrasi}
                    data-testid={`perangkat-row-${i}`}
                    onClick={() => setDrill(d)}
                    className={`border-b border-border/60 cursor-pointer hover:bg-blue-50/40 ${
                      i % 2 ? "bg-slate-50/40" : ""
                    }`}
                  >
                    <td className="px-3 py-2 mono text-blue-700 font-medium">
                      {d.nomor_registrasi}
                    </td>
                    <td className="px-3 py-2">{d.nama || "-"}</td>
                    <td className="px-3 py-2">
                      <Badge
                        className={
                          STATUS_STYLE[d.current_status] || STATUS_STYLE.UNKNOWN
                        }
                      >
                        {STATUS_LABEL[d.current_status] || d.current_status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      <Badge className={jClass}>
                        {d.latest_jenis_order || "-"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 truncate max-w-xs">
                      {d.latest_pelanggan || "-"}
                    </td>
                    <td className="px-3 py-2 mono text-right">{d.wo_count}</td>
                    <td className="px-3 py-2 text-right text-muted-foreground">
                      <ArrowSquareOut size={14} />
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <DrillPanel device={drill} onClose={() => setDrill(null)} />
    </div>
  );
}
