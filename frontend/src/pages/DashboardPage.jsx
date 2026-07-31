import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { DASHBOARD } from "@/constants/testIds";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from "recharts";
import { TrendUp, TrendDown, ClockClockwise, CheckCircle, Money, Waveform, ArrowUpRight } from "@phosphor-icons/react";

const CHART_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#0EA5E9", "#A855F7"];

function Kpi({ label, value, hint, testid, icon: Icon, tone = "blue", onClick }) {
  const toneMap = {
    blue: "text-blue-400",
    green: "text-emerald-400",
    amber: "text-amber-400",
    red: "text-red-400",
  };
  const clickable = typeof onClick === "function";
  return (
    <div
      data-testid={testid}
      onClick={clickable ? onClick : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={
        clickable
          ? (e) => (e.key === "Enter" || e.key === " ") && onClick()
          : undefined
      }
      className={`border border-border bg-card p-5 rounded-sm relative overflow-hidden transition-all ${
        clickable
          ? "cursor-pointer hover:border-blue-500 hover:shadow-md hover:-translate-y-0.5"
          : "hover:border-blue-500/40"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">{label}</div>
        {Icon && <Icon size={18} weight="duotone" className={toneMap[tone]} />}
      </div>
      <div className="mt-3 font-display font-black text-3xl tracking-tighter mono">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      {clickable && (
        <ArrowUpRight
          size={14}
          weight="bold"
          className="absolute top-2 right-2 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
        />
      )}
    </div>
  );
}

function Section({ title, children, right }) {
  return (
    <div className="border border-border bg-card rounded-sm">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{title}</div>
        {right}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export default function DashboardPage() {
  const nav = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [mediaJenis, setMediaJenis] = useState("");
  const [jenisOrder, setJenisOrder] = useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (mediaJenis) params.media_jenis = mediaJenis;
      if (jenisOrder) params.jenis_order = jenisOrder;
      const { data } = await api.get("/dashboard/stats", { params });
      setStats(data);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, mediaJenis, jenisOrder]);

  useEffect(() => {
    load();
  }, [load]);

  const fmtIDR = (n) =>
    new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n || 0);

  // Build query string that also carries current dashboard filters so drill-down keeps context.
  const goToList = (extra = {}) => {
    const sp = new URLSearchParams();
    if (mediaJenis) sp.set("media_jenis", mediaJenis);
    if (jenisOrder) sp.set("jenis_order", jenisOrder);
    Object.entries(extra).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") sp.set(k, v);
    });
    nav(`/workorders?${sp.toString()}`);
  };

  return (
    <div data-testid={DASHBOARD.root} className="p-6 lg:p-8 space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Overview</div>
          <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tighter">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time overview of provisioning workflow, SLA compliance, dan revenue.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
          <select
            data-testid="dashboard-media-filter"
            value={mediaJenis}
            onChange={(e) => setMediaJenis(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-2 py-1.5 text-xs"
          >
            <option value="">All Media</option>
            <option>WIRELINE</option>
            <option>WIRELESS</option>
            <option>FIBER</option>
            <option>SATELLITE</option>
          </select>
          <select
            data-testid="dashboard-jenis-filter"
            value={jenisOrder}
            onChange={(e) => setJenisOrder(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-2 py-1.5 text-xs"
          >
            <option value="">All Jenis</option>
            <option>PSB</option>
            <option>MUTASI</option>
            <option>MIGRASI</option>
            <option>DISMANTLE</option>
            <option>MAINTENANCE</option>
          </select>
          <input
            data-testid={DASHBOARD.dateFrom}
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-2 py-1.5 text-xs mono"
          />
          <span className="text-muted-foreground">→</span>
          <input
            data-testid={DASHBOARD.dateTo}
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="bg-secondary border border-border rounded-sm px-2 py-1.5 text-xs mono"
          />
          <button
            data-testid={DASHBOARD.resetFilter}
            onClick={() => {
              setDateFrom("");
              setDateTo("");
              setMediaJenis("");
              setJenisOrder("");
            }}
            className="px-2 py-1.5 text-xs border border-border rounded-sm hover:bg-slate-100"
          >
            Reset
          </button>
          <span className="ml-4 pulse-dot" />
          <span className="mono">LIVE</span>
        </div>
      </div>

      {loading || !stats ? (
        <div className="text-sm text-muted-foreground mono">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Kpi
              label="Total Orders"
              value={stats.total}
              hint="Semua work order · klik untuk buka daftar"
              testid={DASHBOARD.totalKpi}
              icon={Waveform}
              tone="blue"
              onClick={() => goToList()}
            />
            <Kpi
              label="In Progress"
              value={stats.by_status?.in_progress || 0}
              hint="Sedang berjalan · klik untuk filter"
              testid={DASHBOARD.inProgressKpi}
              icon={ClockClockwise}
              tone="amber"
              onClick={() => goToList({ status: "in_progress" })}
            />
            <Kpi
              label="Completed"
              value={stats.by_status?.completed || 0}
              hint="Aktivasi selesai · klik untuk filter"
              testid={DASHBOARD.completedKpi}
              icon={CheckCircle}
              tone="green"
              onClick={() => goToList({ status: "completed" })}
            />
            <Kpi
              label="Revenue Paid"
              value={fmtIDR(stats.revenue_paid)}
              hint={`Open ${fmtIDR(stats.revenue_open)} · klik untuk PAID`}
              testid={DASHBOARD.revenueKpi}
              icon={Money}
              tone="green"
              onClick={() => goToList({ inv_status: "PAID" })}
            />
            <Kpi
              label="SLA Compliance"
              value={`${stats.sla_pct}%`}
              hint={`${stats.sla_hit} hit / ${stats.sla_miss} miss · klik ke Reports`}
              testid={DASHBOARD.slaKpi}
              icon={stats.sla_pct >= 90 ? TrendUp : TrendDown}
              tone={stats.sla_pct >= 90 ? "green" : stats.sla_pct >= 70 ? "amber" : "red"}
              onClick={() => nav("/reports")}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Section title="Orders by Jenis Pekerjaan" right={<span className="text-[10px] text-muted-foreground mono">klik bar untuk filter</span>}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats.by_jenis_order}>
                  <CartesianGrid vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11, fontFamily: "IBM Plex Mono" }} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11, fontFamily: "IBM Plex Mono" }} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#0f172a", borderRadius: 2 }} />
                  <Bar
                    dataKey="value"
                    fill="#3B82F6"
                    radius={[2, 2, 0, 0]}
                    cursor="pointer"
                    onClick={(d) => d?.name && goToList({ jenis_order: d.name })}
                  />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {(stats.by_jenis_order || []).map((j) => (
                  <button
                    key={j.name}
                    data-testid={`dashboard-jenis-chip-${j.name}`}
                    onClick={() => goToList({ jenis_order: j.name })}
                    className="text-[10px] mono uppercase tracking-widest px-2 py-0.5 border border-border rounded-sm bg-secondary hover:bg-blue-50 hover:border-blue-400 hover:text-blue-700"
                  >
                    {j.name} · {j.value}
                  </button>
                ))}
              </div>
            </Section>

            <Section title="Media Akses" right={<span className="text-[10px] text-muted-foreground mono">klik untuk filter</span>}>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={stats.by_media}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={55}
                    outerRadius={90}
                    strokeWidth={0}
                    cursor="pointer"
                    onClick={(d) => d?.name && goToList({ media_jenis: d.name })}
                  >
                    {stats.by_media.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#0f172a", borderRadius: 2 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 gap-2 mt-2">
                {stats.by_media.map((m, i) => (
                  <button
                    key={m.name}
                    data-testid={`dashboard-media-chip-${m.name}`}
                    onClick={() => goToList({ media_jenis: m.name })}
                    className="flex items-center gap-2 text-xs px-2 py-1 rounded-sm hover:bg-blue-50 hover:text-blue-700 border border-transparent hover:border-blue-200 text-left"
                  >
                    <span className="inline-block w-2 h-2 rounded-full" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                    <span className="text-muted-foreground uppercase tracking-wider">{m.name}</span>
                    <span className="ml-auto mono">{m.value}</span>
                  </button>
                ))}
              </div>
            </Section>

            <Section title="Invoice Status" right={<span className="text-[10px] text-muted-foreground mono">klik untuk filter</span>}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={stats.by_inv_status} layout="vertical">
                  <CartesianGrid horizontal={false} stroke="#e2e8f0" />
                  <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11, fontFamily: "IBM Plex Mono" }} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                  <YAxis dataKey="name" type="category" width={80} tick={{ fill: "#64748b", fontSize: 11, fontFamily: "IBM Plex Mono" }} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#0f172a", borderRadius: 2 }} />
                  <Bar
                    dataKey="value"
                    fill="#10B981"
                    radius={[0, 2, 2, 0]}
                    cursor="pointer"
                    onClick={(d) => d?.name && goToList({ inv_status: d.name })}
                  />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {(stats.by_inv_status || []).map((s) => (
                  <button
                    key={s.name}
                    data-testid={`dashboard-invstatus-chip-${s.name}`}
                    onClick={() => goToList({ inv_status: s.name })}
                    className="text-[10px] mono uppercase tracking-widest px-2 py-0.5 border border-border rounded-sm bg-secondary hover:bg-emerald-50 hover:border-emerald-400 hover:text-emerald-700"
                  >
                    {s.name} · {s.value}
                  </button>
                ))}
              </div>
            </Section>
          </div>
        </>
      )}
    </div>
  );
}
