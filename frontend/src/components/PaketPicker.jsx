import React, { useMemo, useState, useEffect, useRef } from "react";
import DEFAULT_PAKETS from "@/lib/paket-data.json";
import { MagnifyingGlass, X, Package } from "@phosphor-icons/react";

const fmtIDR = (n) =>
  new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n || 0);

/**
 * Searchable paket picker. Emits onPick({code, name, jasa, material, keterangan, satuan}).
 * value: currently selected code (string).
 */
export default function PaketPicker({ value, valueName, onPick, onClear, disabled, source }) {
  const PAKETS = source && source.length > 0 ? source : DEFAULT_PAKETS;
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const rootRef = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return PAKETS.slice(0, 200);
    return PAKETS.filter(
      (p) =>
        p.code.toLowerCase().includes(s) ||
        p.name.toLowerCase().includes(s) ||
        (p.keterangan || "").toLowerCase().includes(s)
    ).slice(0, 200);
  }, [q]);

  return (
    <div ref={rootRef} className="relative">
      <div className="flex items-stretch gap-2">
        <button
          type="button"
          data-testid="paket-picker-open"
          disabled={disabled}
          onClick={() => setOpen((v) => !v)}
          className="flex-1 flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 rounded-sm px-3 py-2 text-sm text-left transition-colors disabled:opacity-60"
        >
          <Package size={16} weight="duotone" className="text-blue-500 shrink-0" />
          {value ? (
            <span className="mono text-foreground truncate">
              <span className="text-blue-600">{value}</span> · {valueName}
            </span>
          ) : (
            <span className="text-muted-foreground">Pilih paket dari master PKS…</span>
          )}
        </button>
        {value && !disabled && (
          <button
            type="button"
            data-testid="paket-picker-clear"
            onClick={onClear}
            className="border border-border bg-secondary hover:bg-slate-100 rounded-sm px-2 text-muted-foreground"
            title="Hapus paket"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {open && (
        <div
          data-testid="paket-picker-panel"
          className="absolute z-30 mt-1 left-0 right-0 border border-border bg-card rounded-sm shadow-lg max-h-96 overflow-hidden flex flex-col"
        >
          <div className="p-2 border-b border-border flex items-center gap-2 bg-slate-50">
            <MagnifyingGlass size={14} className="text-muted-foreground" />
            <input
              data-testid="paket-picker-search"
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Cari kode paket, nama, atau keterangan…"
              className="flex-1 bg-transparent outline-none text-sm"
            />
            <span className="mono text-[10px] uppercase tracking-widest text-muted-foreground">
              {filtered.length} / {PAKETS.length}
            </span>
          </div>
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground text-center">
                Tidak ada paket yang cocok.
              </div>
            ) : (
              filtered.map((p) => (
                <button
                  key={p.code}
                  type="button"
                  data-testid={`paket-option-${p.code}`}
                  onClick={() => {
                    onPick(p);
                    setOpen(false);
                    setQ("");
                  }}
                  className="w-full text-left px-3 py-2 border-b border-border/60 hover:bg-blue-50 transition-colors block"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">
                        <span className="mono text-blue-600">{p.code}</span> · {p.name}
                      </div>
                      {p.keterangan && (
                        <div className="text-xs text-muted-foreground truncate mt-0.5">
                          {p.keterangan}
                        </div>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm mono font-semibold text-foreground">
                        {fmtIDR(p.total)}
                      </div>
                      <div className="text-[10px] text-muted-foreground mono">
                        J {fmtIDR(p.jasa).replace("Rp", "").trim()} · M{" "}
                        {fmtIDR(p.material).replace("Rp", "").trim()}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
