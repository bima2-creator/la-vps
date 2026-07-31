import React, { useEffect, useState, useCallback } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import {
  Database,
  MagnifyingGlass,
  DownloadSimple,
  Plus,
  Trash,
  PencilSimple,
  Check,
  X,
} from "@phosphor-icons/react";

function KpiCard({ label, value, testid }) {
  return (
    <div data-testid={testid} className="border border-border bg-card p-5 rounded-sm">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-2 font-display font-black text-3xl mono">{value}</div>
    </div>
  );
}

export default function BankDataPage() {
  const [data, setData] = useState({ items: [], total: 0, kpi: {} });
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null); // { id, prefix, nama }
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ prefix: "", nama: "" });

  const load = useCallback(async (search) => {
    setLoading(true);
    try {
      const { data } = await api.get("/perangkat/bank", {
        params: { q: search || undefined, page: 1, page_size: 500 },
      });
      setData(data);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Gagal memuat bank data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load("");
  }, [load]);

  useEffect(() => {
    const t = setTimeout(() => load(q), 300);
    return () => clearTimeout(t);
  }, [q, load]);

  const startEdit = (row) => setEditing({ id: row.id, prefix: row.prefix, nama: row.nama });
  const cancelEdit = () => setEditing(null);

  const saveEdit = async () => {
    try {
      await api.put(`/perangkat/bank/${editing.id}`, {
        prefix: editing.prefix.trim().toUpperCase(),
        nama: editing.nama.trim(),
      });
      toast.success("Entri diperbarui");
      setEditing(null);
      load(q);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Gagal menyimpan");
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Hapus entri "${row.prefix}" → ${row.nama}?`)) return;
    try {
      await api.delete(`/perangkat/bank/${row.id}`);
      toast.success("Entri dihapus");
      load(q);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Gagal menghapus");
    }
  };

  const addEntry = async () => {
    try {
      await api.post("/perangkat/bank", {
        prefix: draft.prefix.trim().toUpperCase(),
        nama: draft.nama.trim(),
      });
      toast.success("Entri ditambahkan");
      setAdding(false);
      setDraft({ prefix: "", nama: "" });
      load(q);
    } catch (e) {
      toast.error(formatApiError(e?.response?.data?.detail) || "Gagal menambah entri");
    }
  };

  const exportXlsx = async () => {
    try {
      const resp = await api.get("/perangkat/bank/export/xlsx", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "bank-data-perangkat.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Excel diunduh");
    } catch (e) {
      toast.error("Gagal ekspor Excel");
    }
  };

  const items = data.items || [];

  return (
    <div data-testid="bank-data-page" className="p-6 lg:p-8 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Asset Intelligence
          </div>
          <h1 className="font-display text-4xl font-black tracking-tighter">Kelola Bank Data</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Daftar prefix nomor registrasi (11-13 karakter) yang dikenali sistem untuk auto-isi nama
            perangkat. Perbaiki atau hapus entri yang salah di sini.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="bank-add-btn"
            onClick={() => {
              setAdding((v) => !v);
              setDraft({ prefix: "", nama: "" });
            }}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-2 rounded-sm"
          >
            <Plus size={16} weight="bold" /> Tambah Entri
          </button>
          <button
            data-testid="bank-export-xlsx"
            onClick={exportXlsx}
            className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
          >
            <DownloadSimple size={16} /> Export Excel
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <KpiCard testid="bank-kpi-entries" label="Total Entri" value={data.kpi?.total_entries ?? 0} />
        <KpiCard testid="bank-kpi-prefixes" label="Prefix Unik" value={data.kpi?.total_prefixes ?? 0} />
        <KpiCard testid="bank-kpi-namas" label="Nama Perangkat Unik" value={data.kpi?.total_namas ?? 0} />
      </div>

      {adding && (
        <div className="border border-blue-200 bg-blue-50/60 rounded-sm p-3">
          <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
            Tambah entri manual
          </div>
          <div className="grid grid-cols-1 md:grid-cols-[220px_1fr_auto] gap-2 items-start">
            <input
              data-testid="bank-add-prefix"
              placeholder="Prefix (11-13 char)"
              value={draft.prefix}
              onChange={(e) => setDraft({ ...draft, prefix: e.target.value.toUpperCase() })}
              className="border border-border bg-white rounded-sm px-3 py-2 text-sm mono"
            />
            <input
              data-testid="bank-add-nama"
              placeholder="Nama perangkat"
              value={draft.nama}
              onChange={(e) => setDraft({ ...draft, nama: e.target.value })}
              className="border border-border bg-white rounded-sm px-3 py-2 text-sm"
            />
            <div className="flex gap-2">
              <button
                data-testid="bank-add-confirm"
                onClick={addEntry}
                disabled={draft.prefix.trim().length < 11 || !draft.nama.trim()}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-sm px-3 py-2 rounded-sm"
              >
                Simpan
              </button>
              <button
                onClick={() => setAdding(false)}
                className="text-sm text-muted-foreground hover:text-foreground px-2"
              >
                Batal
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="relative max-w-md">
        <MagnifyingGlass
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <input
          data-testid="bank-search"
          placeholder="Cari prefix atau nama perangkat…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-full border border-border bg-white rounded-sm pl-9 pr-3 py-2 text-sm"
        />
      </div>

      <div className="border border-border rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              <th className="text-left px-3 py-2 w-56">Prefix</th>
              <th className="text-left px-3 py-2 w-20">Panjang</th>
              <th className="text-left px-3 py-2">Nama Perangkat</th>
              <th className="text-left px-3 py-2 w-24">Jumlah</th>
              <th className="w-28 px-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-muted-foreground">
                  {loading ? "Memuat…" : "Belum ada bank data."}
                </td>
              </tr>
            ) : (
              items.map((row) => {
                const isEdit = editing && editing.id === row.id;
                return (
                  <tr
                    key={row.id}
                    data-testid={`bank-row-${row.id}`}
                    className="border-b border-border last:border-0 hover:bg-slate-50/60"
                  >
                    <td className="px-3 py-2 mono">
                      {isEdit ? (
                        <input
                          data-testid="bank-edit-prefix"
                          value={editing.prefix}
                          onChange={(e) =>
                            setEditing({ ...editing, prefix: e.target.value.toUpperCase() })
                          }
                          className="w-full border border-border rounded-sm px-2 py-1 text-sm mono"
                        />
                      ) : (
                        row.prefix
                      )}
                    </td>
                    <td className="px-3 py-2 mono text-muted-foreground">{row.plen}</td>
                    <td className="px-3 py-2">
                      {isEdit ? (
                        <input
                          data-testid="bank-edit-nama"
                          value={editing.nama}
                          onChange={(e) => setEditing({ ...editing, nama: e.target.value })}
                          className="w-full border border-border rounded-sm px-2 py-1 text-sm"
                        />
                      ) : (
                        row.nama
                      )}
                    </td>
                    <td className="px-3 py-2 mono text-muted-foreground">{row.count}</td>
                    <td className="px-2 py-2">
                      {isEdit ? (
                        <div className="flex items-center justify-center gap-1">
                          <button
                            data-testid="bank-edit-save"
                            onClick={saveEdit}
                            className="p-1.5 rounded-sm text-emerald-600 hover:bg-emerald-50"
                            title="Simpan"
                          >
                            <Check size={15} weight="bold" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="p-1.5 rounded-sm text-slate-500 hover:bg-slate-100"
                            title="Batal"
                          >
                            <X size={15} weight="bold" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-1">
                          <button
                            data-testid={`bank-edit-${row.id}`}
                            onClick={() => startEdit(row)}
                            className="p-1.5 rounded-sm text-blue-600 hover:bg-blue-50"
                            title="Edit"
                          >
                            <PencilSimple size={15} weight="bold" />
                          </button>
                          <button
                            data-testid={`bank-delete-${row.id}`}
                            onClick={() => remove(row)}
                            className="p-1.5 rounded-sm text-red-500 hover:bg-red-50"
                            title="Hapus"
                          >
                            <Trash size={15} weight="bold" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="text-xs text-muted-foreground">
        Menampilkan {items.length} dari {data.total} entri.
      </div>
    </div>
  );
}
