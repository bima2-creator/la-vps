import React, { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ChartLineUp, MagnifyingGlass, UsersThree, Buildings } from "@phosphor-icons/react";

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
        <div className="text-muted-foreground">Selesai (OK/Batal)</div>
        <div className="mono text-right">{data?.selesai ?? 0}</div>
        <div className="text-muted-foreground">OK</div>
        <div className="mono text-right text-emerald-600">{data?.ok ?? 0}</div>
        <div className="text-muted-foreground">Batal</div>
        <div className="mono text-right text-red-500">{data?.batal ?? 0}</div>
        <div className="col-span-2 pt-2 mt-1 border-t border-border flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.15em] font-semibold">Success Rate</span>
          <span className="text-lg font-bold text-blue-700 mono">{data?.success_rate ?? 0}%</span>
        </div>
      </div>
    </div>
  );
}

function Bar({ pct }) {
  return (
    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
      <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Math.min(100, pct)}%` }} />
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
            hasil pekerjaan <b>OK</b> atau <b>Batal</b>; success rate = OK ÷ total.
          </p>
        </div>
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
              <th className="text-right px-3 py-2 w-24">Selesai</th>
              <th className="text-right px-3 py-2 w-20">OK</th>
              <th className="text-right px-3 py-2 w-20">Batal</th>
              <th className="text-right px-3 py-2 w-24">Pending</th>
              <th className="text-left px-3 py-2 w-52">Success Rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-muted-foreground">
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
                  <td className="px-3 py-2 font-medium">{r.nama}</td>
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
                  <td className="px-3 py-2 text-right mono">{r.selesai}</td>
                  <td className="px-3 py-2 text-right mono text-emerald-600">{r.ok}</td>
                  <td className="px-3 py-2 text-right mono text-red-500">{r.batal}</td>
                  <td className="px-3 py-2 text-right mono text-muted-foreground">{r.pending}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Bar pct={r.success_rate} />
                      <span className="mono text-xs w-12 text-right">{r.success_rate}%</span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-muted-foreground">
        Menampilkan {rows.length} teknisi.
      </div>
    </div>
  );
}
