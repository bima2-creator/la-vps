import React, { useState } from "react";
import PaketPicker from "./PaketPicker";
import DEFAULT_PAKETS from "@/lib/paket-data.json";
import MAINTENANCE_PAKETS from "@/lib/paket-maintenance-data.json";
import { formatIDR } from "@/lib/format";
import { Plus, Trash, Package } from "@phosphor-icons/react";

const MODE_LABEL = {
  jasa: "Jasa",
  material: "Material",
  both: "Jasa + Material",
};

function subtotalOf(item) {
  const qty = Number(item.qty) || 0;
  const j = Number(item.jasa) || 0;
  const m = Number(item.material) || 0;
  if (item.mode === "jasa") return qty * j;
  if (item.mode === "material") return qty * m;
  return qty * (j + m);
}

export function computeBoqTotals(items) {
  let totalJasa = 0;
  let totalMaterial = 0;
  (items || []).forEach((it) => {
    const qty = Number(it.qty) || 0;
    const j = Number(it.jasa) || 0;
    const m = Number(it.material) || 0;
    if (it.mode !== "material") totalJasa += qty * j;
    if (it.mode !== "jasa") totalMaterial += qty * m;
  });
  return {
    totalJasa,
    totalMaterial,
    grandTotal: totalJasa + totalMaterial,
  };
}

function ManualPaketForm({ value, onChange, onSubmit }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  const jasa = Number(value.jasa) || 0;
  const material = Number(value.material) || 0;
  const qty = Number(value.qty) || 0;
  const preview = qty * (jasa + material);
  const canSubmit = String(value.name || "").trim() && qty > 0 && (jasa > 0 || material > 0);
  return (
    <div data-testid="boq-manual-form">
      <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
        Tambah paket manual &middot; isi detail paket kustom
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-6 gap-3">
        <label className="sm:col-span-4">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
            Nama / Deskripsi Paket <span className="text-red-600">*</span>
          </span>
          <input
            data-testid="boq-manual-name"
            type="text"
            value={value.name}
            onChange={(e) => set("name", e.target.value.toUpperCase())}
            placeholder="mis. PERPANJANGAN KABEL OUTDOOR 50M"
            className="w-full bg-white border border-border rounded-sm px-3 py-2 text-sm"
          />
        </label>
        <label>
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
            Satuan
          </span>
          <input
            data-testid="boq-manual-satuan"
            type="text"
            value={value.satuan}
            onChange={(e) => set("satuan", e.target.value.toUpperCase())}
            placeholder="UNIT / M / JAM"
            className="w-full bg-white border border-border rounded-sm px-3 py-2 text-sm mono"
          />
        </label>
        <label>
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
            Quantity <span className="text-red-600">*</span>
          </span>
          <input
            data-testid="boq-manual-qty"
            type="number"
            min="0"
            step="0.01"
            value={value.qty}
            onChange={(e) => set("qty", Number(e.target.value) || 0)}
            className="w-full bg-white border border-border rounded-sm px-3 py-2 text-sm mono text-right"
          />
        </label>
        <label className="sm:col-span-3">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
            Harga Jasa (per satuan)
          </span>
          <input
            data-testid="boq-manual-jasa"
            type="number"
            min="0"
            value={value.jasa}
            onChange={(e) => set("jasa", Number(e.target.value) || 0)}
            className="w-full bg-white border border-border rounded-sm px-3 py-2 text-sm mono text-right"
          />
        </label>
        <label className="sm:col-span-3">
          <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
            Harga Material (per satuan)
          </span>
          <input
            data-testid="boq-manual-material"
            type="number"
            min="0"
            value={value.material}
            onChange={(e) => set("material", Number(e.target.value) || 0)}
            className="w-full bg-white border border-border rounded-sm px-3 py-2 text-sm mono text-right"
          />
        </label>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3 flex-wrap border-t border-blue-200 pt-3">
        <div className="text-xs text-muted-foreground">
          Preview subtotal:{" "}
          <span
            data-testid="boq-manual-preview-total"
            className="mono text-blue-700 font-bold text-sm"
          >
            {formatIDR(preview)}
          </span>{" "}
          <span className="text-[10px] mono uppercase tracking-widest ml-2">
            (Jasa {formatIDR(qty * jasa)} + Material {formatIDR(qty * material)})
          </span>
        </div>
        <button
          type="button"
          data-testid="boq-manual-submit"
          disabled={!canSubmit}
          onClick={onSubmit}
          className={`inline-flex items-center gap-2 text-white text-sm font-medium px-4 py-2 rounded-sm transition-colors ${
            canSubmit
              ? "bg-blue-600 hover:bg-blue-700"
              : "bg-slate-300 cursor-not-allowed"
          }`}
        >
          <Plus size={14} weight="bold" /> Tambah ke BoQ
        </button>
      </div>
      {!canSubmit && (
        <div className="mt-2 text-[11px] text-amber-700 mono">
          Wajib isi nama, quantity &gt; 0, dan minimal salah satu antara Jasa
          atau Material &gt; 0.
        </div>
      )}
    </div>
  );
}

export default function BoqItemsEditor({ items, onChange, disabled, jenis }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTab, setPickerTab] = useState("master"); // "master" | "manual"
  const [pickedPaket, setPickedPaket] = useState(null); // paket master row after Step 1
  const [manualForm, setManualForm] = useState({
    name: "",
    satuan: "",
    qty: 1,
    jasa: 0,
    material: 0,
  });
  const list = items || [];
  const isMaintenance = jenis === "MAINTENANCE";
  const paketSource = isMaintenance ? MAINTENANCE_PAKETS : DEFAULT_PAKETS;

  const nextManualCode = () => {
    const nums = list
      .map((it) => (it.code || "").match(/^MANUAL-(\d+)$/))
      .filter(Boolean)
      .map((m) => parseInt(m[1], 10));
    const next = (nums.length ? Math.max(...nums) : 0) + 1;
    return `MANUAL-${String(next).padStart(2, "0")}`;
  };

  const addManualItem = () => {
    const name = String(manualForm.name || "").trim();
    if (!name) return;
    const j = Number(manualForm.jasa) || 0;
    const m = Number(manualForm.material) || 0;
    const qty = Number(manualForm.qty) || 1;
    // Auto-select mode based on which fields have values.
    let mode = "both";
    if (j > 0 && m === 0) mode = "jasa";
    else if (m > 0 && j === 0) mode = "material";
    const next = [
      ...list,
      {
        code: nextManualCode(),
        name,
        keterangan: "Custom (manual entry)",
        satuan: String(manualForm.satuan || "").trim() || "unit",
        qty,
        mode,
        jasa: j,
        material: m,
      },
    ];
    onChange(next);
    setPickerOpen(false);
    setManualForm({ name: "", satuan: "", qty: 1, jasa: 0, material: 0 });
    setPickerTab("master");
  };

  const addItem = (mode) => {
    if (!pickedPaket) return;
    const p = pickedPaket;
    const next = [
      ...list,
      {
        code: p.code,
        name: p.name,
        keterangan: p.keterangan || "",
        satuan: p.satuan || "",
        qty: 1,
        mode,
        jasa: p.jasa,
        material: p.material,
      },
    ];
    onChange(next);
    setPickerOpen(false);
    setPickedPaket(null);
  };

  const closePicker = () => {
    setPickerOpen(false);
    setPickedPaket(null);
    setManualForm({ name: "", satuan: "", qty: 1, jasa: 0, material: 0 });
    setPickerTab("master");
  };

  const patch = (idx, k, v) => {
    const next = list.map((it, i) => (i === idx ? { ...it, [k]: v } : it));
    onChange(next);
  };

  const removeAt = (idx) => onChange(list.filter((_, i) => i !== idx));

  const totals = computeBoqTotals(list);

  return (
    <div data-testid="boq-items-editor" className="space-y-3">
      {/* Add row */}
      {!disabled && (
        <div>
          {pickerOpen ? (
            <div className="border border-blue-200 bg-blue-50/60 rounded-sm p-4">
              {/* Tab bar */}
              <div className="flex items-center gap-1 border-b border-blue-200 mb-4 -mt-1">
                <button
                  type="button"
                  data-testid="boq-picker-tab-master"
                  onClick={() => {
                    setPickerTab("master");
                    setPickedPaket(null);
                  }}
                  className={`px-3 py-2 text-xs mono uppercase tracking-widest border-b-2 -mb-px transition-colors ${
                    pickerTab === "master"
                      ? "border-blue-600 text-blue-700 font-semibold"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Master {isMaintenance ? "KHS" : "PKS"}
                </button>
                <button
                  type="button"
                  data-testid="boq-picker-tab-manual"
                  onClick={() => {
                    setPickerTab("manual");
                    setPickedPaket(null);
                  }}
                  className={`px-3 py-2 text-xs mono uppercase tracking-widest border-b-2 -mb-px transition-colors ${
                    pickerTab === "manual"
                      ? "border-blue-600 text-blue-700 font-semibold"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Manual / Custom
                </button>
                <button
                  type="button"
                  onClick={closePicker}
                  className="ml-auto text-xs text-muted-foreground hover:text-foreground px-2"
                >
                  Batal
                </button>
              </div>

              {pickerTab === "manual" ? (
                <ManualPaketForm
                  value={manualForm}
                  onChange={setManualForm}
                  onSubmit={addManualItem}
                />
              ) : !pickedPaket ? (
                <>
                  <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                    Step 1 &middot; Pilih paket dari{" "}
                    {isMaintenance ? "KHS Gangguan (Maintenance)" : "master PKS"}
                  </div>
                  <PaketPicker
                    value=""
                    valueName=""
                    source={paketSource}
                    onPick={(p) => setPickedPaket(p)}
                    onClear={() => {}}
                  />
                </>
              ) : (
                <>
                  <div className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mb-3 flex items-center gap-2 flex-wrap">
                    <span>Step 2 &middot; Pilih jenis biaya</span>
                    <span className="mono text-[10px] px-2 py-0.5 rounded-sm bg-blue-600 text-white">
                      {pickedPaket.code}
                    </span>
                    <span className="text-foreground normal-case tracking-normal">
                      {pickedPaket.name}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      {
                        key: "jasa",
                        title: "Jasa saja",
                        desc: "Hanya biaya jasa/tenaga kerja.",
                        val: pickedPaket.jasa,
                      },
                      {
                        key: "material",
                        title: "Material saja",
                        desc: "Hanya biaya material/perangkat.",
                        val: pickedPaket.material,
                      },
                      {
                        key: "both",
                        title: "Jasa + Material",
                        desc: "Total lengkap paket.",
                        val: pickedPaket.jasa + pickedPaket.material,
                      },
                    ].map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        data-testid={`boq-add-mode-${opt.key}`}
                        onClick={() => addItem(opt.key)}
                        className="text-left border border-border bg-white hover:border-blue-500 hover:bg-blue-50 rounded-sm p-3 transition-all group"
                      >
                        <div className="text-sm font-semibold text-foreground group-hover:text-blue-700">
                          {opt.title}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-1">
                          {opt.desc}
                        </div>
                        <div className="mt-2 mono text-sm text-blue-700 font-bold">
                          {formatIDR(opt.val)}
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setPickedPaket(null)}
                      className="text-xs text-blue-600 hover:text-blue-700"
                    >
                      &larr; Ganti paket
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <button
              type="button"
              data-testid="boq-add-paket-btn"
              onClick={() => setPickerOpen(true)}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-sm transition-colors"
            >
              <Plus size={14} weight="bold" /> Tambah Paket
            </button>
          )}
        </div>
      )}

      {/* Items table */}
      {list.length === 0 ? (
        <div className="border border-dashed border-border rounded-sm p-8 text-center">
          <Package size={28} weight="duotone" className="mx-auto text-muted-foreground mb-2" />
          <div className="text-sm text-muted-foreground">
            Belum ada paket. Klik <span className="text-blue-600 font-medium">Tambah Paket</span>{" "}
            untuk mulai.
          </div>
        </div>
      ) : (
        <div className="border border-border rounded-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-border">
              <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                <th className="text-left px-3 py-2 w-24">Kode</th>
                <th className="text-left px-3 py-2">Paket</th>
                <th className="text-left px-3 py-2 w-32">Mode</th>
                <th className="text-right px-3 py-2 w-20">Qty</th>
                <th className="text-right px-3 py-2 w-36">Jasa</th>
                <th className="text-right px-3 py-2 w-36">Material</th>
                <th className="text-right px-3 py-2 w-40">Subtotal</th>
                {!disabled && <th className="w-10 px-2"></th>}
              </tr>
            </thead>
            <tbody className="mono">
              {list.map((it, i) => (
                <tr
                  key={i}
                  data-testid={`boq-item-row-${i}`}
                  className="border-b border-border last:border-0"
                >
                  <td className="px-3 py-2 text-blue-600">{it.code}</td>
                  <td className="px-3 py-2">
                    <div className="font-sans text-foreground">{it.name}</div>
                    {it.keterangan && (
                      <div className="text-[11px] text-muted-foreground font-sans truncate max-w-md">
                        {it.keterangan}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <select
                      data-testid={`boq-item-mode-${i}`}
                      value={it.mode || "both"}
                      disabled={disabled}
                      onChange={(e) => patch(i, "mode", e.target.value)}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-xs"
                    >
                      <option value="both">{MODE_LABEL.both}</option>
                      <option value="jasa">{MODE_LABEL.jasa}</option>
                      <option value="material">{MODE_LABEL.material}</option>
                    </select>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      data-testid={`boq-item-qty-${i}`}
                      type="number"
                      min="0"
                      step="0.01"
                      disabled={disabled}
                      value={it.qty ?? 1}
                      onChange={(e) => patch(i, "qty", Number(e.target.value) || 0)}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-right"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      data-testid={`boq-item-jasa-${i}`}
                      type="number"
                      min="0"
                      disabled={disabled || it.mode === "material"}
                      value={it.jasa ?? 0}
                      onChange={(e) => patch(i, "jasa", Number(e.target.value) || 0)}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-right disabled:bg-slate-100 disabled:text-muted-foreground"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      data-testid={`boq-item-material-${i}`}
                      type="number"
                      min="0"
                      disabled={disabled || it.mode === "jasa"}
                      value={it.material ?? 0}
                      onChange={(e) => patch(i, "material", Number(e.target.value) || 0)}
                      className="w-full bg-white border border-border rounded-sm px-2 py-1 text-right disabled:bg-slate-100 disabled:text-muted-foreground"
                    />
                  </td>
                  <td
                    data-testid={`boq-item-subtotal-${i}`}
                    className="px-3 py-2 text-right font-semibold text-foreground"
                  >
                    {formatIDR(subtotalOf(it))}
                  </td>
                  {!disabled && (
                    <td className="px-2 py-2 text-center">
                      <button
                        type="button"
                        data-testid={`boq-item-delete-${i}`}
                        onClick={() => removeAt(i)}
                        className="p-1 rounded-sm text-red-500 hover:text-red-600 hover:bg-red-50 transition-colors"
                        title="Hapus baris"
                      >
                        <Trash size={14} weight="bold" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>

          {/* Totals footer */}
          <div className="bg-slate-50 border-t border-border px-3 py-3">
            <div className="max-w-md ml-auto space-y-1.5 text-sm mono">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground uppercase text-[11px] tracking-[0.15em]">
                  Total Jasa
                </span>
                <span data-testid="boq-total-jasa" className="text-foreground">
                  {formatIDR(totals.totalJasa)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground uppercase text-[11px] tracking-[0.15em]">
                  Total Material
                </span>
                <span data-testid="boq-total-material" className="text-foreground">
                  {formatIDR(totals.totalMaterial)}
                </span>
              </div>
              <div className="flex items-center justify-between pt-1.5 border-t border-border">
                <span className="text-foreground uppercase text-xs tracking-[0.15em] font-semibold">
                  Grand Total
                </span>
                <span
                  data-testid="boq-grand-total"
                  className="text-blue-600 text-lg font-bold"
                >
                  {formatIDR(totals.grandTotal)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
