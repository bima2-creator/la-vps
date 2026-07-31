import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { USERS } from "@/constants/testIds";
import { toast } from "sonner";
import { UserPlus, Trash } from "@phosphor-icons/react";

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", username: "", email: "", password: "", role: "operator" });
  const [creating, setCreating] = useState(false);

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

  const create = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post("/users", form);
      toast.success("User created");
      setForm({ name: "", username: "", email: "", password: "", role: "operator" });
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Create failed");
    } finally {
      setCreating(false);
    }
  };

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
      </div>

      <form onSubmit={create} className="border border-border bg-card rounded-sm p-5 space-y-3">
        <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">New User</div>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <input
            data-testid={USERS.nameInput}
            required
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          />
          <input
            data-testid={USERS.emailInput}
            required
            type="text"
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm mono"
          />
          <input
            data-testid="users-email-input"
            type="email"
            placeholder="Email (optional)"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm mono"
          />
          <input
            data-testid={USERS.passwordInput}
            required
            type="password"
            placeholder="Password (min 4)"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
            minLength={4}
          />
          <select
            data-testid={USERS.roleSelect}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          >
            <option value="admin">Admin</option>
            <option value="operator">Operator</option>
            <option value="viewer">Viewer</option>
          </select>
          <button
            data-testid={USERS.createButton}
            disabled={creating}
            className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60"
          >
            <UserPlus size={16} /> Create
          </button>
        </div>
      </form>

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
