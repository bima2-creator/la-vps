import React, { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { USERS } from "@/constants/testIds";
import { toast } from "sonner";
import { Trash, Plus, Key, Power } from "@phosphor-icons/react";

function FieldEngineerSection() {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ username: "", name: "", password: "" });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users/field-engineers");
      setList(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal memuat daftar FE");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!form.username || !form.name || !form.password) return;
    setSaving(true);
    try {
      await api.post("/users/field-engineers", form);
      toast.success(`Akun FE "${form.username}" dibuat`);
      setForm({ username: "", name: "", password: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal membuat akun");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (fe) => {
    try {
      await api.patch(`/users/field-engineers/${fe.id}`, { active: !fe.active });
      toast.success(fe.active ? `${fe.username} dinonaktifkan` : `${fe.username} diaktifkan`);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal mengubah status");
    }
  };

  const resetPassword = async (fe) => {
    const pw = window.prompt(`Password baru untuk ${fe.username} (min. 4 karakter):`);
    if (!pw) return;
    try {
      await api.patch(`/users/field-engineers/${fe.id}`, { password: pw });
      toast.success(`Password ${fe.username} direset`);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal reset password");
    }
  };

  const del = async (fe) => {
    if (!window.confirm(`Hapus akun FE "${fe.username}"? WO yang pernah ditugaskan tetap tersimpan.`)) return;
    try {
      await api.delete(`/users/${fe.id}`);
      toast.success("Akun dihapus");
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal menghapus");
    }
  };

  const inputCls =
    "bg-secondary border border-border rounded-sm px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500";

  return (
    <div data-testid="fe-section" className="space-y-3">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight">Field Engineer</h2>
        <p className="text-xs text-muted-foreground">
          Akun untuk teknisi lapangan (login via aplikasi mobile). FE hanya melihat & mengisi WO yang
          ditugaskan padanya.
        </p>
      </div>

      <form onSubmit={create} className="flex flex-wrap items-end gap-2 border border-border rounded-sm bg-card p-3">
        <label className="block">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">Username</span>
          <input
            data-testid="fe-username-input"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase().replace(/\s/g, "") })}
            className={`${inputCls} mono w-40`}
            placeholder="mis. budi"
          />
        </label>
        <label className="block">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">Nama Lengkap</span>
          <input
            data-testid="fe-name-input"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={`${inputCls} w-56`}
            placeholder="Budi Santoso"
          />
        </label>
        <label className="block">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">Password</span>
          <input
            data-testid="fe-password-input"
            type="text"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className={`${inputCls} mono w-40`}
            placeholder="min. 4 karakter"
          />
        </label>
        <button
          data-testid="fe-create-button"
          type="submit"
          disabled={saving || !form.username || !form.name || form.password.length < 4}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-sm"
        >
          <Plus size={15} /> Tambah FE
        </button>
      </form>

      <div className="border border-border rounded-sm bg-card overflow-hidden">
        <table className="w-full data-table text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-left text-[10px] uppercase tracking-widest text-muted-foreground">
              <th>Nama</th>
              <th>Username</th>
              <th>Status</th>
              <th>Dibuat</th>
              <th className="text-right pr-3">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="text-center py-5 text-muted-foreground mono">Loading…</td>
              </tr>
            )}
            {!loading && list.length === 0 && (
              <tr>
                <td colSpan={5} className="text-center py-5 text-muted-foreground">
                  Belum ada akun Field Engineer.
                </td>
              </tr>
            )}
            {list.map((fe, i) => (
              <tr key={fe.id} data-testid={`fe-row-${fe.username}`} className={`border-b border-border/60 ${i % 2 ? "bg-slate-50/60" : ""}`}>
                <td>{fe.name}</td>
                <td className="mono">{fe.username}</td>
                <td>
                  <span
                    className={`text-[10px] uppercase tracking-widest border px-2 py-0.5 rounded-sm ${
                      fe.active
                        ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/30"
                        : "bg-slate-200 text-slate-500 border-slate-300"
                    }`}
                  >
                    {fe.active ? "Aktif" : "Nonaktif"}
                  </span>
                </td>
                <td className="mono text-xs text-muted-foreground">
                  {fe.created_at ? new Date(fe.created_at).toLocaleDateString("id-ID") : "—"}
                </td>
                <td className="text-right pr-3 whitespace-nowrap">
                  <button
                    data-testid={`fe-toggle-${fe.username}`}
                    onClick={() => toggleActive(fe)}
                    className={`p-1.5 rounded-sm ${fe.active ? "hover:bg-amber-500/10 hover:text-amber-500" : "hover:bg-emerald-500/10 hover:text-emerald-500"}`}
                    title={fe.active ? "Nonaktifkan" : "Aktifkan"}
                  >
                    <Power size={14} />
                  </button>
                  <button
                    data-testid={`fe-reset-${fe.username}`}
                    onClick={() => resetPassword(fe)}
                    className="p-1.5 rounded-sm hover:bg-blue-500/10 hover:text-blue-500"
                    title="Reset password"
                  >
                    <Key size={14} />
                  </button>
                  <button
                    data-testid={`fe-delete-${fe.username}`}
                    onClick={() => del(fe)}
                    className="p-1.5 rounded-sm hover:bg-red-500/10 hover:text-red-400"
                    title="Hapus"
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

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data.filter((u) => u.role !== "field_engineer"));
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Failed to load");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  const roleColors = {
    admin: "bg-red-500/10 text-red-400 border-red-500/30",
    operator: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    viewer: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  };

  return (
    <div data-testid={USERS.root} className="p-6 lg:p-8 space-y-8">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Administration</div>
        <h1 className="font-display text-4xl font-black tracking-tighter">Users &amp; Roles</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Akun sistem tetap: admin, operator, dan guest. Akun Field Engineer dikelola di bawah.
        </p>
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
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="text-center py-6 text-muted-foreground mono">
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FieldEngineerSection />
    </div>
  );
}
