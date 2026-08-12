import React, { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { NAV } from "@/constants/testIds";
import IdleTimeoutManager from "@/components/IdleTimeoutManager";
import {
  ChartBar,
  ChartLineUp,
  Table,
  FileText,
  Users,
  SignOut,
  Broadcast,
  Receipt,
  HardDrives,
  Database,
  MagnifyingGlass,
  Faders,
  FloppyDisk,
  CaretLeft,
  CaretRight,
} from "@phosphor-icons/react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: ChartBar, testid: NAV.dashboard, roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/workorders", label: "Work Orders", icon: Table, testid: NAV.workorders, roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/invoices", label: "Invoices", icon: Receipt, testid: "nav-invoices", roles: ["admin", "operator"], group: "main" },
  { to: "/perangkat", label: "Flow Perangkat", icon: HardDrives, testid: "nav-perangkat", roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/perangkat-history", label: "Riwayat Perangkat", icon: MagnifyingGlass, testid: "nav-perangkat-history", roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/reports", label: "Reports", icon: FileText, testid: NAV.reports, roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/kpi-teknisi", label: "KPI Teknisi", icon: ChartLineUp, testid: "nav-kpi-teknisi", roles: ["admin", "operator", "viewer"], group: "main" },
  { to: "/audit", label: "Audit Log", icon: FileText, testid: NAV.audit, roles: ["admin"], group: "admin" },
  { to: "/bank-data", label: "Kelola Bank Data", icon: Database, testid: "nav-bank-data", roles: ["admin"], group: "admin" },
  { to: "/perangkat-names", label: "Kelola Nama Perangkat", icon: Faders, testid: "nav-perangkat-names", roles: ["admin"], group: "admin" },
  { to: "/users", label: "Users", icon: Users, testid: NAV.users, roles: ["admin"], group: "admin" },
  { to: "/backup", label: "Backup Data", icon: FloppyDisk, testid: "nav-backup", roles: ["admin"], group: "admin" },
];

function initialsOf(name = "") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [belumInvoice, setBelumInvoice] = useState(null);

  // Badge count of Work Orders yang belum dibuatkan invoice.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get("/workorders/pending-invoice-count");
        if (alive) setBelumInvoice(data.belum);
      } catch {
        /* non-blocking */
      }
    })();
    return () => {
      alive = false;
    };
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const visibleItems = navItems.filter((i) => !user?.role || i.roles.includes(user.role));
  const mainItems = visibleItems.filter((i) => i.group === "main");
  const adminItems = visibleItems.filter((i) => i.group === "admin");

  const renderLink = ({ to, label, icon: Icon, testid }) => {
    const badge = to === "/workorders" && belumInvoice ? belumInvoice : null;
    return (
    <NavLink
      key={to}
      to={to}
      end={to === "/workorders"}
      data-testid={testid}
      title={collapsed ? `${label}${badge ? ` (${badge} belum invoice)` : ""}` : undefined}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 rounded-lg text-sm font-medium transition-all ${
          collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2.5"
        } ${
          isActive
            ? "bg-blue-600 text-white shadow-sm shadow-blue-600/20"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        }`
      }
    >
      <Icon size={19} weight={collapsed ? "regular" : "duotone"} className="shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
      {badge != null && (
        <span
          data-testid="nav-workorders-belum-badge"
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            navigate("/workorders?invoiced=belum");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              navigate("/workorders?invoiced=belum");
            }
          }}
          className={`ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-[10px] font-bold mono bg-amber-500 text-white cursor-pointer hover:bg-amber-600 transition-colors ${
            collapsed ? "absolute -top-0.5 -right-0.5 ml-0" : ""
          }`}
          title={`${badge} WO belum dibuatkan invoice — klik untuk lihat`}
        >
          {badge > 99 ? "99+" : badge}
        </span>
      )}
    </NavLink>
    );
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside
        className={`${collapsed ? "w-[68px]" : "w-64"} shrink-0 border-r border-border bg-white transition-[width] duration-200 flex flex-col`}
      >
        <div className={`h-16 flex items-center gap-3 ${collapsed ? "justify-center px-0" : "px-4"} border-b border-border`}>
          <div className="grid place-items-center h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm shadow-blue-600/30 shrink-0">
            <Broadcast size={20} weight="fill" />
          </div>
          {!collapsed && (
            <div className="leading-none">
              <div className="font-display font-black tracking-tighter text-lg">LA TRACKER</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">Portal Management</div>
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-4 space-y-1">
          {!collapsed && (
            <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Menu</div>
          )}
          {mainItems.map(renderLink)}

          {adminItems.length > 0 && (
            <>
              <div className={`mt-4 mb-1 ${collapsed ? "mx-2 border-t border-border" : "px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400 pb-1.5"}`}>
                {!collapsed && "Admin"}
              </div>
              {adminItems.map(renderLink)}
            </>
          )}
        </nav>

        <div className="border-t border-border p-2.5 space-y-1">
          {!collapsed && user && (
            <div className="flex items-center gap-2.5 rounded-lg bg-slate-50 border border-border px-2.5 py-2 mb-1">
              <div className="grid place-items-center h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white text-xs font-bold shrink-0">
                {initialsOf(user.name)}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold truncate">{user.name}</div>
                <div className="text-[9px] uppercase tracking-widest text-muted-foreground mono">{user.role}</div>
              </div>
            </div>
          )}
          <button
            data-testid={NAV.collapse}
            onClick={() => setCollapsed((v) => !v)}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-100 hover:text-slate-900 transition-colors ${collapsed ? "justify-center" : ""}`}
          >
            {collapsed ? <CaretRight size={18} /> : <CaretLeft size={18} />}
            {!collapsed && <span>Collapse</span>}
          </button>
          <button
            data-testid={NAV.logout}
            onClick={handleLogout}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-500 hover:bg-red-50 transition-colors ${collapsed ? "justify-center" : ""}`}
          >
            <SignOut size={18} />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        <Outlet />
      </main>
      <IdleTimeoutManager />
    </div>
  );
}
