import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  ChartLineUp,
  MagnifyingGlass,
  UsersThree,
  Buildings,
  DownloadSimple,
  X,
  ArrowSquareOut,
} from "@phosphor-icons/react";

function SummaryCard({ label, icon: Icon, accent, data }) {
  return (
    <div className="border border-border bg-card rounded-sm p-5">
      <div className="flex items-center gap-2 mb-3">
        <div className={`grid place-items-center h-8 w-8 rounded-lg ${accent}`}>
          <Icon size={16} weight="fill" />
        </div>
        <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      </div>
      <div className="grid grid-cols-2 gap-y-2 gap-x-3 text-sm">
        <div className="text-muted-foreground">Teknisi</div>
        <div className="mono text-right font-semibold">{data?.teknisi_count ?? 0}</div>
        <div className="text-muted-foreground">Total WO</div>
        <div className="mono text-right font-semibold">{data?.total ?? 0}</div>
        <div className="text-muted-foreground">Selesai - OK</div>
        <div className="mono text-right text-emerald-600">{data?.ok ?? 0}</div>
        <div className="text-muted-foreground">Selesai - Batal</div>
        <div className="mono text-right text-red-500">{data?.batal ?? 0}</div>
      </div>
    </div>
  );
}

export default function KpiTeknisiPage() {
  const [data, setData] = useState({ technicians: [], summary: {} });
  const [loading, setLoading] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [tim, setTim] = useState("");
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const [detail, setDetail] = useState(null); // { nama, tim }
  const [detailItems, setDetailItems] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (tim) params.tim = tim;
      const { data } = await api.get("/kpi/teknisi", { params });
      setData(data);
    } catch (e) {
      toast.error("Gagal memuat KPI teknisi");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, tim]);

  useEffect(() => {
    load();
  }, [load]);

  const openDetail = async (row) => {
    setDetail({ nama: row.nama, tim: row.tim });
    setDetailLoading(true);
    setDetailItems([]);
    try {
      const params = { nama: row.nama, tim: row.tim };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const { data } = await api.get("/kpi/teknisi/workorders", { params });
      setDetailItems(data.items || []);
    } catch {
      toast.error("Gagal memuat daftar WO teknisi");
    } finally {
      setDetailLoading(false);
    }
  };

  const exportXlsx = async () => {
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (tim) params.tim = tim;
      const resp = await api.get("/kpi/teknisi/export/xlsx", { params, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "kpi-teknisi.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Excel diunduh");
    } catch {
      toast.error("Gagal ekspor Excel");
    }
  };

  const rows = (data.technicians || []).filter((r) =>
    !q.trim() ? true : r.nama.toLowerCase().includes(q.trim().toLowerCase())
  );

  return (
    <div data-testid="kpi-teknisi-page" className="p-6 lg:p-8 space-y-5">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Performance
          </div>
          <h1 className="font-display text-4xl font-black tracking-tighter">KPI Teknisi</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Pencapaian per teknisi & tim (Internal vs Mitra). WO dihitung selesai bila status
            hasil pekerjaan <b>OK</b> atau <b>Batal</b>. Klik nama teknisi untuk melihat daftar WO.
          </p>
        </div>
        <button
          data-testid="kpi-export-xlsx"
          onClick={exportXlsx}
          className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
        >
          <DownloadSimple size={16} /> Export Excel
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 bg-card border border-border rounded-sm p-3">
        <label className="text-xs">
          <span className="block text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
            Dari Tanggal
          </span>
          <input
            data-testid="kpi-date-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-border rounded-sm px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="block text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
            Sampai Tanggal
          </span>
          <input
            data-testid="kpi-date-to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-border rounded-sm px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-xs">
          <span className="block text-[10px] uppercase tracking-widest text-muted-foreground mb-1">
            Tim
          </span>
          <select
            data-testid="kpi-tim-filter"
            value={tim}
            onChange={(e) => setTim(e.target.value)}
            className="border border-border rounded-sm px-2 py-1.5 text-sm bg-white"
          >
            <option value="">Semua</option>
            <option value="INTERNAL">Internal</option>
            <option value="MITRA">Mitra</option>
          </select>
        </label>
        <div className="relative flex-1 min-w-[200px]">
          <MagnifyingGlass
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            data-testid="kpi-search"
            placeholder="Cari nama teknisi…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full border border-border rounded-sm pl-9 pr-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          label="Internal"
          icon={UsersThree}
          accent="bg-blue-100 text-blue-700"
          data={data.summary?.internal}
        />
        <SummaryCard
          label="Mitra"
          icon={Buildings}
          accent="bg-amber-100 text-amber-700"
          data={data.summary?.mitra}
        />
        <SummaryCard
          label="Semua"
          icon={ChartLineUp}
          accent="bg-emerald-100 text-emerald-700"
          data={data.summary?.all}
        />
      </div>

      {/* Technician table */}
      <div className="border border-border rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              <th className="text-left px-3 py-2">Nama Teknisi</th>
              <th className="text-left px-3 py-2 w-24">Tim</th>
              <th className="text-right px-3 py-2 w-24">Total WO</th>
              <th className="text-right px-3 py-2 w-28 whitespace-nowrap">Selesai - OK</th>
              <th className="text-right px-3 py-2 w-28 whitespace-nowrap">Selesai - Batal</th>
              <th className="text-right px-3 py-2 w-24">Pending</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-10 text-center text-muted-foreground">
                  {loading ? "Memuat…" : "Belum ada data teknisi."}
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={`${r.nama}-${r.tim}`}
                  data-testid={`kpi-row-${r.nama}`}
                  className="border-b border-border last:border-0 hover:bg-slate-50/60"
                >
                  <td className="px-3 py-2 font-medium">
                    <button
                      data-testid={`kpi-open-${r.nama}`}
                      onClick={() => openDetail(r)}
                      className="text-blue-700 hover:underline text-left inline-flex items-center gap-1"
                    >
                      {r.nama}
                      <ArrowSquareOut size={13} className="opacity-60" />
                    </button>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-widest mono ${
                        r.tim === "INTERNAL"
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      }`}
                    >
                      {r.tim}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right mono font-semibold">{r.total}</td>
                  <td className="px-3 py-2 text-right mono text-emerald-600">{r.ok}</td>
                  <td className="px-3 py-2 text-right mono text-red-500">{r.batal}</td>
                  <td className="px-3 py-2 text-right mono text-muted-foreground">{r.pending}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-muted-foreground">
        Menampilkan {rows.length} teknisi.
      </div>

      {/* Detail WO per teknisi */}
      {detail && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 sm:p-8 overflow-y-auto"
          onClick={() => setDetail(null)}
          data-testid="kpi-detail-modal"
        >
          <div
            className="bg-white rounded-lg w-full max-w-3xl shadow-xl border border-border"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-border">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Detail WO Teknisi
                </div>
                <div className="font-display text-lg font-bold">
                  {detail.nama}{" "}
                  <span className="text-xs mono text-muted-foreground">({detail.tim})</span>
                </div>
              </div>
              <button
                data-testid="kpi-detail-close"
                onClick={() => setDetail(null)}
                className="p-1.5 rounded-sm hover:bg-slate-100 text-slate-500"
              >
                <X size={18} weight="bold" />
              </button>
            </div>
            <div className="max-h-[65vh] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-border sticky top-0">
                  <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
                    <th className="px-4 py-2">Pelanggan</th>
                    <th className="px-4 py-2">SA ID</th>
                    <th className="px-4 py-2">Jenis</th>
                    <th className="px-4 py-2">Media</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Tanggal</th>
                    <th className="px-4 py-2 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {detailLoading ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        Memuat…
                      </td>
                    </tr>
                  ) : detailItems.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                        Tidak ada WO.
                      </td>
                    </tr>
                  ) : (
                    detailItems.map((w) => (
                      <tr
                        key={w.id}
                        data-testid={`kpi-detail-row-${w.id}`}
                        className="border-b border-border/60 hover:bg-slate-50/60"
                      >
                        <td className="px-4 py-2 font-medium">{w.pelanggan || "—"}</td>
                        <td className="px-4 py-2 mono text-xs">{w.sa_id || "—"}</td>
                        <td className="px-4 py-2">{w.jenis_order || "—"}</td>
                        <td className="px-4 py-2">{w.media_jenis || "—"}</td>
                        <td className="px-4 py-2">
                          <span
                            className={`text-[10px] mono uppercase px-1.5 py-0.5 rounded-sm border ${
                              w.status === "OK"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : w.status === "BATAL"
                                ? "bg-red-50 text-red-600 border-red-200"
                                : "bg-slate-50 text-slate-500 border-slate-200"
                            }`}
                          >
                            {w.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 mono text-xs">{(w.created_at || "").slice(0, 10) || "—"}</td>
                        <td className="px-4 py-2">
                          <button
                            onClick={() => nav(`/workorders/${w.id}`)}
                            title="Buka WO"
                            className="p-1 rounded-sm text-blue-600 hover:bg-blue-50"
                          >
                            <ArrowSquareOut size={15} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-5 py-2.5 border-t border-border text-xs text-muted-foreground">
              Total {detailItems.length} WO
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
