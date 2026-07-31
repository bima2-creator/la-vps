import React, { useMemo, useState, useEffect, useRef } from "react";
import PERANGKAT_MASTER from "@/lib/perangkat-master.json";
import { api } from "@/lib/api";
import {
  Plus,
  Trash,
  HardDrives,
  Wrench,
  ArrowsCounterClockwise,
  CheckCircle,
  MagnifyingGlass,
} from "@phosphor-icons/react";

// Roles are used for MAINTENANCE work orders. For non-maintenance jenis,
// role stays undefined and the editor behaves like before (single "Tambah
// Perangkat" button).
export const PERANGKAT_ROLES = {
  existing: {
    label: "Eksisting",
    hint: "Perangkat yang sudah terpasang sebelumnya (tidak berubah).",
    icon: CheckCircle,
    accent: "bg-emerald-50 text-emerald-700 border-emerald-200",
    button: "bg-emerald-600 hover:bg-emerald-700",
  },
  dicabut: {
    label: "Dicabut / Rusak",
    hint: "Perangkat lama yang diangkat karena rusak / diganti.",
    icon: Wrench,
    accent: "bg-red-50 text-red-700 border-red-200",
    button: "bg-red-600 hover:bg-red-700",
  },
  pengganti: {
    label: "Pengganti",
    hint: "Perangkat baru sebagai pengganti unit yang rusak.",
    icon: ArrowsCounterClockwise,
    accent: "bg-blue-50 text-blue-700 border-blue-200",
    button: "bg-blue-600 hover:bg-blue-700",
  },
};

function RoleBadge({ role }) {
  const meta = PERANGKAT_ROLES[role];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <span
      data-testid={`perangkat-role-badge-${role}`}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-widest mono ${meta.accent}`}
    >
      <Icon size={10} weight="fill" /> {meta.label}
    </span>
  );
}

export default function PerangkatEditor({ items, onChange, disabled, jenis, hideAdd }) {
  const list = items || [];
  const isMaint = jenis === "MAINTENANCE";
  const [addRole, setAddRole] = useState(null); // null | "existing" | "dicabut" | "pengganti" | "any"
  const [draft, setDraft] = useState({ nama_perangkat: "", nomor_registrasi: "" });
  const [bank, setBank] = useState(null); // { matched, ambiguous, suggested, options }
  const autoFilledRef = useRef(""); // last value we auto-filled, so we don't clobber manual edits

  // Bank Data lookup: recognise device name from registration prefix (11-13 chars).
  useEffect(() => {
    const nomor = (draft.nomor_registrasi || "").trim();
    if (nomor.length < 11) {
      setBank(null);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get("/perangkat/bank/lookup", { params: { nomor } });
        if (cancelled) return;
        setBank(data);
        // Auto-fill only for an unambiguous match, and only when the name field is
        // empty or still holds a previously auto-filled value (never override typing).
        if (data.matched && !data.ambiguous) {
          setDraft((d) => {
            const cur = (d.nama_perangkat || "").trim();
            if (!cur || cur === autoFilledRef.current) {
              autoFilledRef.current = data.suggested;
              return { ...d, nama_perangkat: data.suggested };
            }
            return d;
          });
        }
      } catch {
        if (!cancelled) setBank(null);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [draft.nomor_registrasi]);

  const pickBankOption = (nama) => {
    autoFilledRef.current = nama;
    setDraft((d) => ({ ...d, nama_perangkat: nama }));
  };

  const suggestions = useMemo(() => {
    const q = draft.nama_perangkat.trim().toLowerCase();
    if (!q) return [];
    return PERANGKAT_MASTER.filter(
      (n) => n.toLowerCase().includes(q) && n.toLowerCase() !== q
    ).slice(0, 8);
  }, [draft.nama_perangkat]);

  const closeAdd = () => {
    setAddRole(null);
    setDraft({ nama_perangkat: "", nomor_registrasi: "" });
    setBank(null);
    autoFilledRef.current = "";
  };

  const addItem = () => {
    const nama = draft.nama_perangkat.trim();
    const nr = draft.nomor_registrasi.trim();
    if (!nama || !nr) return;
    if (list.some((x) => (x.nomor_registrasi || "").trim() === nr)) {
      alert(`Nomor registrasi "${nr}" sudah ada di WO ini`);
      return;
    }
    const entry = { nama_perangkat: nama, nomor_registrasi: nr };
    if (isMaint && addRole && addRole !== "any") entry.role = addRole;
    onChange([...list, entry]);
    closeAdd();
  };

  const removeAt = (idx) => onChange(list.filter((_, i) => i !== idx));

  const patch = (idx, k, v) => {
    // Uppercase text fields for consistency with data-entry policy.
    const val = typeof v === "string" && k !== "role" ? v.toUpperCase() : v;
    onChange(list.map((it, i) => (i === idx ? { ...it, [k]: val } : it)));
  };

  // --- Row-level Bank Data auto-detect (editing existing rows) ---
  const listRef = useRef(list);
  listRef.current = list;
  const rowTimers = useRef({});
  const rowAutoRef = useRef({});
  const [rowBank, setRowBank] = useState({}); // idx -> lookup result

  const setRowNama = (idx, nama) => {
    rowAutoRef.current[idx] = nama;
    const cur = listRef.current;
    onChange(cur.map((it, i) => (i === idx ? { ...it, nama_perangkat: nama } : it)));
  };

  const scheduleRowLookup = (idx, nomor) => {
    const n = (nomor || "").trim();
    if (rowTimers.current[idx]) clearTimeout(rowTimers.current[idx]);
    if (n.length < 11) {
      setRowBank((m) => ({ ...m, [idx]: null }));
      return;
    }
    rowTimers.current[idx] = setTimeout(async () => {
      try {
        const { data } = await api.get("/perangkat/bank/lookup", { params: { nomor: n } });
        setRowBank((m) => ({ ...m, [idx]: data }));
        if (data.matched && !data.ambiguous) {
          const cur = listRef.current;
          const curNama = (cur[idx]?.nama_perangkat || "").trim();
          if (!curNama || curNama === rowAutoRef.current[idx]) {
            setRowNama(idx, data.suggested);
          }
        }
      } catch {
        /* ignore lookup errors */
      }
    }, 300);
  };

  const activeMeta = isMaint && addRole && addRole !== "any" ? PERANGKAT_ROLES[addRole] : null;

  return (
    <div data-testid="perangkat-editor" className="space-y-3">
      {!disabled && !hideAdd && (
        <div>
          {addRole ? (
            <div
              className={`border rounded-sm p-3 ${
                activeMeta ? "border-blue-200 bg-blue-50/60" : "border-blue-200 bg-blue-50/60"
              }`}
            >
              <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2 flex items-center gap-2 flex-wrap">
                <span>Tambah perangkat</span>
                {activeMeta && <RoleBadge role={addRole} />}
                {activeMeta && (
                  <span className="normal-case tracking-normal text-foreground">
                    &middot; {activeMeta.hint}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 relative">
                <div className="relative">
                  <input
                    data-testid="perangkat-draft-nama"
                    placeholder="Nama perangkat (ketik untuk cari)"
                    value={draft.nama_perangkat}
                    onChange={(e) =>
                      setDraft({ ...draft, nama_perangkat: e.target.value.toUpperCase() })
                    }
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  />
                  {suggestions.length > 0 && (
                    <div className="absolute z-10 left-0 right-0 mt-1 border border-border bg-white rounded-sm shadow-lg max-h-52 overflow-y-auto">
                      {suggestions.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setDraft({ ...draft, nama_perangkat: s })}
                          className="w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50 border-b border-border/60 last:border-0"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <input
                  data-testid="perangkat-draft-nomor"
                  placeholder="Nomor registrasi (unique)"
                  value={draft.nomor_registrasi}
                  onChange={(e) =>
                    setDraft({ ...draft, nomor_registrasi: e.target.value.toUpperCase() })
                  }
                  className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm mono"
                />
              </div>
              {bank && bank.matched && !bank.ambiguous && (
                <div
                  data-testid="perangkat-bank-detected"
                  className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-sm px-2 py-1"
                >
                  <CheckCircle size={12} weight="fill" />
                  Terdeteksi otomatis dari bank data:
                  <span className="font-medium mono">{bank.suggested}</span>
                </div>
              )}
              {bank && bank.matched && bank.ambiguous && (
                <div
                  data-testid="perangkat-bank-options"
                  className="mt-2 border border-amber-200 bg-amber-50 rounded-sm p-2"
                >
                  <div className="text-[11px] text-amber-800 mb-1.5 flex items-center gap-1.5">
                    <MagnifyingGlass size={12} weight="bold" />
                    Beberapa perangkat cocok untuk prefix ini, pilih salah satu:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {bank.options.map((o) => (
                      <button
                        key={o.nama}
                        type="button"
                        data-testid={`perangkat-bank-option-${o.nama}`}
                        onClick={() => pickBankOption(o.nama)}
                        className={`text-[11px] px-2 py-1 rounded-sm border mono transition-colors ${
                          draft.nama_perangkat === o.nama
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-white border-border hover:bg-blue-50"
                        }`}
                      >
                        {o.nama}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-2 flex items-center gap-2">
                <button
                  type="button"
                  data-testid="perangkat-add-confirm"
                  onClick={addItem}
                  disabled={!draft.nama_perangkat || !draft.nomor_registrasi}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white text-xs font-medium px-3 py-1.5 rounded-sm"
                >
                  Tambah
                </button>
                <button
                  type="button"
                  onClick={closeAdd}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Batal
                </button>
              </div>
            </div>
          ) : isMaint ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(PERANGKAT_ROLES).map(([role, meta]) => {
                const Icon = meta.icon;
                return (
                  <button
                    key={role}
                    type="button"
                    data-testid={`perangkat-add-${role}-btn`}
                    onClick={() => setAddRole(role)}
                    className={`inline-flex items-center gap-2 ${meta.button} text-white text-sm font-medium px-4 py-2 rounded-sm transition-colors`}
                    title={meta.hint}
                  >
                    <Icon size={14} weight="bold" /> Tambah perangkat {meta.label.toLowerCase()}
                  </button>
                );
              })}
            </div>
          ) : (
            <button
              type="button"
              data-testid="perangkat-add-btn"
              onClick={() => setAddRole("any")}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-sm transition-colors"
            >
              <Plus size={14} weight="bold" /> Tambah Perangkat
            </button>
          )}
        </div>
      )}

      {list.length === 0 ? (
        <div className="border border-dashed border-border rounded-sm p-8 text-center">
          <HardDrives size={26} weight="duotone" className="mx-auto text-muted-foreground mb-2" />
          <div className="text-sm text-muted-foreground">
            {isMaint
              ? "Belum ada perangkat. Pilih salah satu kategori di atas untuk menambah."
              : "Belum ada perangkat terpasang."}
          </div>
        </div>
      ) : (
        <div className="border border-border rounded-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-border">
              <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                <th className="text-left px-3 py-2">Nama Perangkat</th>
                <th className="text-left px-3 py-2 w-64">Nomor Registrasi</th>
                {isMaint && <th className="text-left px-3 py-2 w-44">Kategori</th>}
                {!disabled && <th className="w-10 px-2"></th>}
              </tr>
            </thead>
            <tbody className="mono">
              {list.map((it, i) => (
                <tr
                  key={i}
                  data-testid={`perangkat-row-${i}`}
                  className="border-b border-border last:border-0"
                >
                  <td className="px-3 py-2">
                    <input
                      data-testid={`perangkat-nama-${i}`}
                      value={it.nama_perangkat || ""}
                      onChange={(e) => patch(i, "nama_perangkat", e.target.value)}
                      disabled={disabled}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-sm"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      data-testid={`perangkat-nomor-${i}`}
                      value={it.nomor_registrasi || ""}
                      onChange={(e) => {
                        patch(i, "nomor_registrasi", e.target.value);
                        scheduleRowLookup(i, e.target.value.toUpperCase());
                      }}
                      disabled={disabled}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-sm mono"
                    />
                    {!disabled && rowBank[i] && rowBank[i].matched && rowBank[i].ambiguous && (
                      <div
                        data-testid={`perangkat-row-bank-options-${i}`}
                        className="mt-1 flex flex-wrap gap-1"
                      >
                        {rowBank[i].options.map((o) => (
                          <button
                            key={o.nama}
                            type="button"
                            onClick={() => setRowNama(i, o.nama)}
                            className={`text-[10px] px-1.5 py-0.5 rounded-sm border transition-colors ${
                              it.nama_perangkat === o.nama
                                ? "bg-blue-600 text-white border-blue-600"
                                : "bg-amber-50 border-amber-200 hover:bg-amber-100"
                            }`}
                          >
                            {o.nama}
                          </button>
                        ))}
                      </div>
                    )}
                  </td>
                  {isMaint && (
                    <td className="px-3 py-2">
                      {disabled ? (
                        <RoleBadge role={it.role} />
                      ) : (
                        <select
                          data-testid={`perangkat-role-${i}`}
                          value={it.role || ""}
                          onChange={(e) => patch(i, "role", e.target.value)}
                          className="w-full bg-white border border-border rounded-sm px-2 py-1 text-xs"
                        >
                          <option value="">(tanpa kategori)</option>
                          {Object.entries(PERANGKAT_ROLES).map(([r, m]) => (
                            <option key={r} value={r}>
                              {m.label}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                  )}
                  {!disabled && (
                    <td className="px-2 py-2 text-center">
                      <button
                        type="button"
                        data-testid={`perangkat-delete-${i}`}
                        onClick={() => removeAt(i)}
                        className="p-1 rounded-sm text-red-500 hover:text-red-600 hover:bg-red-50"
                        title="Hapus perangkat"
                      >
                        <Trash size={14} weight="bold" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
