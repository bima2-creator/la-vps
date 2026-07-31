import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { USERS } from "@/constants/testIds";
import { toast } from "sonner";
import { Trash } from "@phosphor-icons/react";

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Failed to load");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const del = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try {
      await api.delete(`/users/${id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Delete failed");
    }
  };

  const roleColors = {
    admin: "bg-red-500/10 text-red-400 border-red-500/30",
    operator: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    viewer: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  };

  return (
    <div data-testid={USERS.root} className="p-6 lg:p-8 space-y-4">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Administration</div>
        <h1 className="font-display text-4xl font-black tracking-tighter">Users &amp; Roles</h1>
        <p className="text-sm text-muted-foreground mt-1">Akun sistem tetap: admin, operator, dan guest.</p>
      </div>

      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <table className="w-full data-table text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th>Name</th>
              <th>Username</th>
              <th>Email</th>
              <th>Role</th>
              <th>Created</th>
              <th></th>
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
            {users.map((u, i) => (
              <tr key={u.id} className={`border-b border-border/60 ${i % 2 ? "bg-slate-50/60" : ""}`}>
                <td>{u.name}</td>
                <td className="mono">{u.username}</td>
                <td className="mono text-xs text-muted-foreground">{u.email || "—"}</td>
                <td>
                  <span className={`text-[10px] uppercase tracking-widest border px-2 py-0.5 rounded-sm ${roleColors[u.role] || ""}`}>
                    {u.role}
                  </span>
                </td>
                <td className="mono text-xs text-muted-foreground">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString("id-ID") : "—"}
                </td>
                <td className="text-right pr-3">
                  <button
                    data-testid={USERS.deleteButton}
                    onClick={() => del(u.id)}
                    className="p-1.5 rounded-sm hover:bg-red-500/10 hover:text-red-400"
                    title="Delete"
                  >
                    <Trash size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
