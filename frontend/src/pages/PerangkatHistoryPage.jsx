import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { MagnifyingGlass, HardDrives, CheckCircle, Wrench, ArrowsCounterClockwise } from "@phosphor-icons/react";
import { Pagination, PAGE_SIZE } from "@/components/Pagination";

const STATUS_META = {
  retired: {
    label: "Dicabut / Rusak — tidak dapat dipakai di WO manapun",
    cls: "bg-red-50 text-red-700 border-red-300",
    Icon: Wrench,
  },
  in_use: {
    label: "Sedang dipakai (terpasang aktif)",
    cls: "bg-amber-50 text-amber-800 border-amber-300",
    Icon: CheckCircle,
  },
  available: {
    label: "Tersedia (eks-dismantle) — boleh dipakai kembali",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-300",
    Icon: ArrowsCounterClockwise,
  },
  new: {
    label: "Belum pernah tercatat di work order manapun",
    cls: "bg-slate-100 text-slate-600 border-slate-300",
    Icon: HardDrives,
  },
};

const ROLE_LABEL = {
  existing: "Eksisting",
  dicabut: "Dicabut / Rusak",
  pengganti: "Pengganti",
};

export default function PerangkatHistoryPage() {
  const nav = useNavigate();
  const [nomor, setNomor] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null); // { nomor_registrasi, status, occurrences }
  const [page, setPage] = useState(1);

  const search = async (e) => {
    e?.preventDefault();
    const q = nomor.trim();
    if (!q) {
      toast.error("Masukkan nomor registrasi perangkat");
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get("/perangkat/history", { params: { nomor: q } });
      setResult(data);
      setPage(1);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal memuat riwayat");
    } finally {
      setLoading(false);
    }
  };

  const meta = result ? STATUS_META[result.status] || STATUS_META.new : null;
  const occ = result?.occurrences || [];
  const pageCount = Math.max(1, Math.ceil(occ.length / PAGE_SIZE));
  const pagedOcc = occ.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div data-testid="perangkat-history-root" className="p-6 lg:p-8 space-y-5">
      <div>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">Data</div>
        <h1 className="font-display text-4xl font-black tracking-tighter">Riwayat Perangkat</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Lacak sebuah nomor registrasi perangkat di seluruh work order beserta statusnya.
        </p>
      </div>

      <form onSubmit={search} className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[280px] max-w-lg">
          <MagnifyingGlass
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            data-testid="perangkat-history-input"
            value={nomor}
            onChange={(e) => setNomor(e.target.value.toUpperCase())}
            placeholder="Ketik nomor registrasi, mis. B2WS0200023MA0580"
            className="w-full bg-secondary border border-border rounded-sm pl-9 pr-3 py-2 text-sm mono focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          />
        </div>
        <button
          data-testid="perangkat-history-search"
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60"
        >
          <MagnifyingGlass size={16} weight="bold" /> {loading ? "Mencari…" : "Lacak"}
        </button>
      </form>

      {result && (
        <div className="space-y-4">
          <div
            data-testid="perangkat-history-status"
            className={`flex items-center gap-3 border rounded-sm px-4 py-3 ${meta.cls}`}
          >
            <meta.Icon size={22} weight="fill" className="shrink-0" />
            <div>
              <div className="mono font-semibold">{result.nomor_registrasi}</div>
              <div className="text-sm">{meta.label}</div>
            </div>
          </div>

          <div className="border border-border rounded-sm overflow-hidden bg-card">
            <div className="px-4 py-2.5 border-b border-border text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
              Ditemukan di <span className="mono">{result.occurrences.length}</span> work order
            </div>
            <div className="overflow-x-auto">
              <table className="w-full data-table text-sm">
                <thead className="bg-slate-50 border-b border-border">
                  <tr className="text-left text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                    <th className="font-medium">Pelanggan</th>
                    <th className="font-medium">SA ID</th>
                    <th className="font-medium">SI ID</th>
                    <th className="font-medium">Jenis Order</th>
                    <th className="font-medium">Kategori</th>
                    <th className="font-medium">Nama Perangkat</th>
                    <th className="w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {result.occurrences.length === 0 && (
                    <tr>
                      <td colSpan={7} className="text-center py-10 text-muted-foreground">
                        Nomor registrasi ini belum pernah dipakai. Aman untuk digunakan.
                      </td>
                    </tr>
                  )}
                  {pagedOcc.map((o, i) => (
                    <tr key={i} className="border-b border-border/60 hover:bg-slate-100">
                      <td className="font-medium">{o.pelanggan || "—"}</td>
                      <td className="mono text-[13px]">{o.sa_id || "—"}</td>
                      <td className="mono text-[13px]">{o.si_id || "—"}</td>
                      <td>
                        <span className="inline-flex px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono bg-slate-100 text-slate-700 border-slate-300">
                          {o.jenis_order || "—"}
                        </span>
                      </td>
                      <td>
                        {o.role ? (
                          <span
                            className={`inline-flex px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono ${
                              o.role === "dicabut"
                                ? "bg-red-50 text-red-700 border-red-200"
                                : o.role === "pengganti"
                                ? "bg-blue-50 text-blue-700 border-blue-200"
                                : "bg-emerald-50 text-emerald-700 border-emerald-200"
                            }`}
                          >
                            {ROLE_LABEL[o.role] || o.role}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="mono text-[13px]">{o.nama_perangkat || "—"}</td>
                      <td className="text-right pr-3">
                        <button
                          type="button"
                          onClick={() => nav(`/workorders/${o.workorder_id}`)}
                          className="text-xs text-blue-600 hover:text-blue-800 hover:underline underline-offset-2"
                        >
                          Buka WO
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-4 border-t border-border">
              <Pagination
                page={page}
                pageCount={pageCount}
                total={occ.length}
                onPrev={() => setPage((p) => Math.max(1, p - 1))}
                onNext={() => setPage((p) => Math.min(pageCount, p + 1))}
                testId="perangkat-history-pagination"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
