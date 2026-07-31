import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AUDIT } from "@/constants/testIds";
import { MagnifyingGlass } from "@phosphor-icons/react";

const ACTION_COLORS = {
  "workorder.create": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  "workorder.update": "bg-blue-500/10 text-blue-400 border-blue-500/30",
  "workorder.delete": "bg-red-500/10 text-red-400 border-red-500/30",
  "attachment.upload": "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  "attachment.delete": "bg-red-500/10 text-red-400 border-red-500/30",
  "workorder.export.pdf": "bg-amber-500/10 text-amber-400 border-amber-500/30",
  "workorder.export.pdf_detail": "bg-amber-500/10 text-amber-400 border-amber-500/30",
};

export default function AuditLogPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");
  const [userEmail, setUserEmail] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const params = { limit: 200 };
      if (action) params.action = action;
      if (userEmail) params.user_email = userEmail;
      const { data } = await api.get("/audit-logs", { params });
      setItems(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div data-testid={AUDIT.root} className="p-6 lg:p-8 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Security</div>
        <h1 className="font-display text-4xl font-black tracking-tighter">Audit Log</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Chronological trail of who did what, and when.
        </p>
      </div>

      <div className="border border-border bg-card rounded-sm p-4 flex flex-wrap gap-3 items-center">
        <div className="relative">
          <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            data-testid={AUDIT.actionFilter}
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="action…"
            className="bg-secondary border border-border rounded-sm pl-8 pr-3 py-2 text-sm mono w-56"
          />
        </div>
        <input
          data-testid={AUDIT.userFilter}
          value={userEmail}
          onChange={(e) => setUserEmail(e.target.value)}
          placeholder="user email…"
          className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm mono w-64"
        />
        <button
          data-testid={AUDIT.applyButton}
          onClick={load}
          className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm"
        >
          Apply
        </button>
      </div>

      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <table className="w-full data-table text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th>Time</th>
              <th>User</th>
              <th>Role</th>
              <th>Action</th>
              <th>Target</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="text-center py-6 text-muted-foreground mono">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-6 text-muted-foreground">
                  No audit events match your filters.
                </td>
              </tr>
            )}
            {items.map((it, i) => (
              <tr key={it.id} className={`border-b border-border/60 ${i % 2 ? "bg-slate-50/60" : ""}`}>
                <td className="mono text-[12px] text-muted-foreground">
                  {new Date(it.created_at).toLocaleString("id-ID")}
                </td>
                <td>{it.user_email || "—"}</td>
                <td>
                  <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
                    {it.user_role || "—"}
                  </span>
                </td>
                <td>
                  <span
                    className={`text-[10px] uppercase tracking-widest border px-2 py-0.5 rounded-sm mono ${
                      ACTION_COLORS[it.action] || "bg-slate-100 text-muted-foreground border-border"
                    }`}
                  >
                    {it.action}
                  </span>
                </td>
                <td className="mono text-[11px] text-muted-foreground">
                  {it.workorder_id ? it.workorder_id.slice(-8) : "—"}
                </td>
                <td className="mono text-[11px] text-muted-foreground">
                  {it.meta ? JSON.stringify(it.meta) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
