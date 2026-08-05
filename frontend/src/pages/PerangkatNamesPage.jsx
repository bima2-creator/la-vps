import React, { useCallback, useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { MagnifyingGlass, ArrowsMerge, Trash, ArrowClockwise } from "@phosphor-icons/react";

export default function PerangkatNamesPage() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState([]);
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      const { data } = await api.get("/perangkat/names/summary", { params });
      setItems(data.items || []);
      setSelected([]);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal memuat");
    } finally {
      setLoading(false);
    }
  }, [q]);

  useEffect(() => {
    load();
  }, []);

  const toggle = (nama) =>
    setSelected((prev) => (prev.includes(nama) ? prev.filter((x) => x !== nama) : [...prev, nama]));

  const allSelected = items.length > 0 && items.every((i) => selected.includes(i.nama));
  const toggleAll = () =>
    setSelected(allSelected ? [] : items.map((i) => i.nama));

  const doMerge = async () => {
    const into = target.trim().toUpperCase();
    if (!into) return toast.error("Isi nama tujuan terlebih dahulu");
    if (selected.length === 0) return toast.error("Pilih minimal satu nama");
    setBusy(true);
    try {
      const { data } = await api.post("/perangkat/names/merge", { from_names: selected, into });
      toast.success(
        `Digabung ke "${into}" · ${data.bank_moved} entri, ${data.workorders_updated} work order diperbarui`
      );
      setTarget("");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal menggabungkan");
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    if (selected.length === 0) return;
    if (!window.confirm(`Hapus ${selected.length} nama perangkat dari registry? Data work order tidak berubah.`))
      return;
    setBusy(true);
    try {
      const { data } = await api.post("/perangkat/names/delete", { names: selected });
      toast.success(`Dihapus ${data.deleted_entries} entri dari registry`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Gagal menghapus");
    } finally {
      setBusy(false);
    }
  };

  const pickTarget = (nama) => setTarget(nama);

  return (
    <div data-testid="perangkat-names-root" className="p-6 lg:p-8 space-y-5">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Data</div>
        <h1 className="font-display text-4xl font-black tracking-tighter">Kelola Nama Perangkat</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Rapikan registry: gabungkan nama duplikat/typo menjadi satu, ganti nama, atau hapus yang salah.
          Penggabungan juga memperbarui nama pada work order terkait.
        </p>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            data-testid="names-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            placeholder="Cari nama perangkat…"
            className="w-full bg-secondary border border-border rounded-sm pl-9 pr-3 py-2 text-sm"
          />
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-3 py-2 rounded-sm"
        >
          <ArrowClockwise size={15} /> Muat ulang
        </button>
      </div>

      {selected.length > 0 && (
        <div
          data-testid="names-action-bar"
          className="flex items-center gap-2 flex-wrap border border-blue-300 bg-blue-50 rounded-sm px-3 py-2"
        >
          <span className="text-sm font-medium text-blue-800">
            <span className="mono">{selected.length}</span> dipilih
          </span>
          <input
            data-testid="names-merge-target"
            value={target}
            onChange={(e) => setTarget(e.target.value.toUpperCase())}
            placeholder="Nama tujuan (gabung / ganti ke…)"
            className="flex-1 min-w-[200px] border border-border bg-white rounded-sm px-3 py-1.5 text-sm mono"
          />
          <button
            data-testid="names-merge-btn"
            onClick={doMerge}
            disabled={busy || !target.trim()}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-60 text-white text-sm px-3 py-1.5 rounded-sm"
          >
            <ArrowsMerge size={15} weight="bold" /> Gabungkan / Ganti
          </button>
          <button
            data-testid="names-delete-btn"
            onClick={doDelete}
            disabled={busy}
            className="inline-flex items-center gap-2 border border-red-300 text-red-700 hover:bg-red-100 disabled:opacity-60 text-sm px-3 py-1.5 rounded-sm"
          >
            <Trash size={15} /> Hapus
          </button>
          <button onClick={() => setSelected([])} className="text-xs text-blue-700/80 hover:text-blue-900 underline">
            batalkan
          </button>
        </div>
      )}

      <div className="border border-border rounded-sm overflow-hidden bg-card">
        <div className="px-4 py-2.5 border-b border-border text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          <span className="mono">{items.length}</span> nama perangkat
        </div>
        <div className="overflow-x-auto">
          <table className="w-full data-table text-sm">
            <thead className="bg-slate-50 border-b border-border">
              <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                <th className="w-10 pl-3">
                  <input
                    type="checkbox"
                    data-testid="names-select-all"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="h-4 w-4 cursor-pointer accent-blue-600"
                  />
                </th>
                <th className="font-medium">Nama Perangkat</th>
                <th className="font-medium w-28">Pemakaian</th>
                <th className="font-medium w-28">Entri Prefix</th>
                <th className="w-24"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="text-center py-10 text-muted-foreground mono">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-10 text-muted-foreground">
                    Tidak ada nama perangkat.
                  </td>
                </tr>
              )}
              {!loading &&
                items.map((it) => (
                  <tr
                    key={it.nama}
                    className={`border-b border-border/60 hover:bg-slate-100 ${
                      selected.includes(it.nama) ? "bg-blue-50/70" : ""
                    }`}
                  >
                    <td className="pl-3">
                      <input
                        type="checkbox"
                        data-testid={`names-select-${it.nama}`}
                        checked={selected.includes(it.nama)}
                        onChange={() => toggle(it.nama)}
                        className="h-4 w-4 cursor-pointer accent-blue-600"
                      />
                    </td>
                    <td className="mono">{it.nama}</td>
                    <td className="mono">{it.count}</td>
                    <td className="mono">{it.entries}</td>
                    <td className="text-right pr-3">
                      <button
                        onClick={() => pickTarget(it.nama)}
                        title="Pakai sebagai nama tujuan penggabungan"
                        className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        jadikan tujuan
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
