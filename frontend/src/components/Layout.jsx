import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { NAV } from "@/constants/testIds";
import {
  ChartBar,
  Table,
  FileText,
  Users,
  SignOut,
  Broadcast,
  Receipt,
  HardDrives,
  CaretLeft,
  CaretRight,
} from "@phosphor-icons/react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: ChartBar, testid: NAV.dashboard, roles: ["admin", "operator", "viewer"] },
  { to: "/workorders", label: "Work Orders", icon: Table, testid: NAV.workorders, roles: ["admin", "operator", "viewer"] },
  { to: "/invoices", label: "Invoices", icon: Receipt, testid: "nav-invoices", roles: ["admin", "operator", "viewer"] },
  { to: "/perangkat", label: "Master Perangkat", icon: HardDrives, testid: "nav-perangkat", roles: ["admin", "operator", "viewer"] },
  { to: "/reports", label: "Reports", icon: FileText, testid: NAV.reports, roles: ["admin", "operator", "viewer"] },
  { to: "/audit", label: "Audit Log", icon: FileText, testid: NAV.audit, roles: ["admin"] },
  { to: "/users", label: "Users", icon: Users, testid: NAV.users, roles: ["admin"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <aside
        className={`${collapsed ? "w-16" : "w-60"} shrink-0 border-r border-border bg-slate-50 transition-[width] duration-200 flex flex-col`}
      >
        <div className="h-16 border-b border-border flex items-center gap-3 px-4">
          <Broadcast size={24} weight="duotone" className="text-blue-500 shrink-0" />
          {!collapsed && (
            <div className="leading-none">
              <div className="font-display font-black tracking-tighter text-lg">LA TRACKER</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Portal Management</div>
            </div>
          )}
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {navItems
            .filter((i) => !user?.role || i.roles.includes(user.role))
            .map(({ to, label, icon: Icon, testid }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/workorders"}
                data-testid={testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                    isActive
                      ? "bg-blue-500/10 text-blue-400 border-l-2 border-blue-500 pl-[10px]"
                      : "text-muted-foreground hover:bg-slate-100 hover:text-foreground"
                  }`
                }
              >
                <Icon size={18} weight="regular" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            ))}
        </nav>

        <div className="border-t border-border p-2 space-y-1">
          <button
            data-testid={NAV.collapse}
            onClick={() => setCollapsed((v) => !v)}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-sm text-sm text-muted-foreground hover:bg-slate-100 hover:text-foreground"
          >
            {collapsed ? <CaretRight size={18} /> : <CaretLeft size={18} />}
            {!collapsed && <span>Collapse</span>}
          </button>
          <button
            data-testid={NAV.logout}
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-sm text-sm text-red-400 hover:bg-red-500/10"
          >
            <SignOut size={18} />
            {!collapsed && <span>Logout</span>}
          </button>
          {!collapsed && user && (
            <div className="px-3 pt-3 pb-1 border-t border-border/50 mt-2">
              <div className="text-xs font-medium truncate">{user.name}</div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mono">
                {user.role}
              </div>
            </div>
          )}
        </div>
      </aside>

      <main className="flex-1 min-w-0 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
