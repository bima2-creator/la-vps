import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import {
  SECTIONS,
  emptyWorkOrder,
  JENIS_ORDER_META,
  JENIS_ORDER_LIST,
  getHiddenFields,
  getMaintenanceOnlyHidden,
  invoiceActivityOptionsFor,
  requiresFasePicker,
  getFaseHiddenFields,
  WO_FASE_OPTIONS,
  getFieldLabel,
  requiresMaintenanceTypePicker,
  MAINTENANCE_TYPE_OPTIONS,
  MAINTENANCE_TYPE_META,
} from "@/lib/workorder-schema";
import { WOFORM } from "@/constants/testIds";
import { toast } from "sonner";
import { CaretLeft, FloppyDisk, FilePdf, Lightning, ArrowsClockwise, ShareNetwork, Wrench, HardDrives, LockKey, MapPin } from "@phosphor-icons/react";
import Attachments from "@/components/Attachments";
import BoqItemsEditor, { computeBoqTotals } from "@/components/BoqItemsEditor";
import PerangkatEditor from "@/components/PerangkatEditor";
import MapPicker from "@/components/MapPicker";

// Migrate a legacy record (single boq_*) into boq_items[] if present.
function ensureBoqItems(record) {
  if (Array.isArray(record.boq_items) && record.boq_items.length > 0) return record;
  const legacy = {
    code: record.boq_paket_code || "LEGACY",
    name: record.boq_paket || "Paket (data lama)",
    keterangan: "",
    satuan: "",
    qty: 1,
    mode: record.boq_mode || "both",
    jasa: Number(record.boq_jasa) || 0,
    material: Number(record.boq_material) || 0,
  };
  // Only create item if there's any meaningful legacy data
  if (legacy.jasa > 0 || legacy.material > 0 || record.boq_paket) {
    return { ...record, boq_items: [legacy] };
  }
  return { ...record, boq_items: [] };
}

const JENIS_ICONS = {
  PSB: Lightning,
  MUTASI: ArrowsClockwise,
  MIGRASI: ShareNetwork,
  DISMANTLE: HardDrives,
  MAINTENANCE: Wrench,
};

function Field({ f, value, onChange }) {
  const base =
    "w-full bg-secondary border border-border rounded-sm px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors";
  const monoClass = f.mono ? "mono" : "";
  // All text/textarea data entry auto-uppercases, matching the operational
  // convention (SA/SI/SPK IDs, addresses, notes are stored uppercase).
  // Individual fields can opt-out with `noUppercase: true`.
  const upper = (v) =>
    typeof v === "string" && !f.noUppercase ? v.toUpperCase() : v;
  return (
    <label className={`block ${f.wide ? "md:col-span-2" : ""}`}>
      <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
        {f.label}
      </span>
      {f.type === "textarea" ? (
        <textarea
          data-testid={`${WOFORM.input}-${f.name}`}
          value={value ?? ""}
          onChange={(e) => onChange(f.name, upper(e.target.value))}
          rows={f.rows || 3}
          wrap="soft"
          className={`${base} ${monoClass} whitespace-pre-wrap break-words leading-relaxed`}
          placeholder={f.placeholder}
        />
      ) : f.type === "select" ? (
        <select
          data-testid={`${WOFORM.input}-${f.name}`}
          value={value ?? ""}
          onChange={(e) => onChange(f.name, e.target.value)}
          className={base}
        >
          {(f.options || []).map((o) => (
            <option key={o} value={o}>
              {o || "— select —"}
            </option>
          ))}
        </select>
      ) : (
        <input
          data-testid={`${WOFORM.input}-${f.name}`}
          type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
          value={value ?? ""}
          onChange={(e) =>
            onChange(
              f.name,
              f.type === "number"
                ? Number(e.target.value || 0)
                : f.type === "date"
                ? e.target.value
                : upper(e.target.value)
            )
          }
          className={`${base} ${monoClass}`}
          placeholder={f.placeholder}
        />
      )}
    </label>
  );
}

export default function WorkOrderFormPage() {
  const nav = useNavigate();
  const { id } = useParams();
  const { user } = useAuth();
  const canEdit = user && (user.role === "admin" || user.role === "operator");
  const isEdit = Boolean(id);
  const [form, setForm] = useState(emptyWorkOrder());
  const [active, setActive] = useState(SECTIONS[0].id);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(isEdit);
  // Jenis picker gating: when creating new, user MUST choose Jenis Order first.
  const [jenisPicked, setJenisPicked] = useState(isEdit);
  // Map picker modal
  const [mapPickerOpen, setMapPickerOpen] = useState(false);

  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      try {
        const { data } = await api.get(`/workorders/${id}`);
        setForm(ensureBoqItems({ ...emptyWorkOrder(), ...data }));
      } catch (e) {
        toast.error("Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, [id, isEdit]);

  const onChange = (k, v) => {
    setForm((f) => {
      const next = { ...f, [k]: v };
      // If boq_items changed, re-derive legacy aggregates so exports/reports stay in sync
      if (k === "boq_items") {
        const t = computeBoqTotals(v);
        next.boq_jasa = t.totalJasa;
        next.boq_material = t.totalMaterial;
        next.boq_jumlah = t.grandTotal;
        // boq_paket as comma-separated codes for the old single-value field
        next.boq_paket = (v || []).map((it) => it.code).join(", ");
        next.boq_paket_code = (v || [])[0]?.code || "";
        // If mixed modes across items, default the legacy mode to "both"
        const modes = new Set((v || []).map((it) => it.mode));
        next.boq_mode = modes.size === 1 ? [...modes][0] : "both";
      }
      return next;
    });
  };

  const pickJenis = (jenis) => {
    setForm((f) => ({
      ...f,
      jenis_order: jenis,
      wo_jenis_pekerjaan: "",
      maintenance_type: "",
    }));
    // For jenis that require fase picker OR maintenance sub-picker, stay in picker
    if (requiresFasePicker(jenis)) return;
    if (requiresMaintenanceTypePicker(jenis)) return;
    setJenisPicked(true);
  };

  const pickFase = (fase) => {
    setForm((f) => ({ ...f, wo_jenis_pekerjaan: fase, inv_jenis_pekerjaan: fase }));
    setJenisPicked(true);
  };

  const pickMaintenanceType = (mt) => {
    setForm((f) => ({
      ...f,
      maintenance_type: mt,
      wo_jenis_pekerjaan: "MAINTENANCE",
      inv_jenis_pekerjaan: "MAINTENANCE",
    }));
    setJenisPicked(true);
  };

  const backToJenisStep = () => {
    setForm((f) => ({ ...f, jenis_order: "", wo_jenis_pekerjaan: "", maintenance_type: "" }));
  };

  const save = async () => {
    // Nama Pelanggan wajib
    if (!String(form.pelanggan || "").trim()) {
      toast.error("Nama Pelanggan wajib diisi");
      setActive("customer");
      return;
    }
    // Global: SA ID atau SI ID wajib diisi minimal salah satu
    const hasSa = String(form.sa_id || "").trim();
    const hasSi = String(form.si_id || "").trim();
    if (!hasSa && !hasSi) {
      toast.error("SA ID atau SI ID wajib diisi minimal salah satu");
      setActive("customer");
      return;
    }
    // Client-side validation for MAINTENANCE: case_no & task_no wajib
    if (form.jenis_order === "MAINTENANCE") {
      if (!String(form.case_no || "").trim()) {
        toast.error("No. Case wajib diisi untuk Work Order Maintenance");
        setActive("spk");
        return;
      }
      if (!String(form.task_no || "").trim()) {
        toast.error("No. Task wajib diisi untuk Work Order Maintenance");
        setActive("spk");
        return;
      }
    }
    setSaving(true);
    try {
      const payload = { ...form };
      // strip meta fields
      delete payload.id;
      delete payload.created_at;
      delete payload.updated_at;
      delete payload.created_by;
      if (isEdit) {
        await api.put(`/workorders/${id}`, payload);
        toast.success("Updated");
      } else {
        await api.post("/workorders", payload);
        toast.success("Created");
      }
      nav("/workorders");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const jenisChosen = form.jenis_order || "";
  const faseChosen = form.wo_jenis_pekerjaan || "";
  const maintenanceType = form.maintenance_type || "";

  // A WO can only edit BoQ (and be invoiced) once its "hasil" status is OK or BATAL.
  // The relevant status field depends on jenis_order + fase pekerjaan.
  const BILLABLE_STATUSES = new Set(["OK", "BATAL", "DONE", "SELESAI", "COMPLETED"]);
  const billableStatusField = (() => {
    if (jenisChosen === "DISMANTLE" || jenisChosen === "MAINTENANCE")
      return "hasil_survey_status";
    if (faseChosen === "SURVEY") return "hasil_survey_status";
    if (faseChosen === "INSTALASI") return "hasil_instalasi_status";
    if (faseChosen === "AKTIVASI") return "hasil_aktivasi_status";
    return "";
  })();
  const currentBillableStatus = billableStatusField
    ? String(form[billableStatusField] || "").trim().toUpperCase()
    : "";
  const billingReady =
    !billableStatusField ||
    BILLABLE_STATUSES.has(currentBillableStatus);
  const needsFase = requiresFasePicker(jenisChosen);
  const needsMaintenanceType = requiresMaintenanceTypePicker(jenisChosen);
  // Merge hidden fields from jenis_order, fase pekerjaan, and maintenance-only tag.
  const jenisHidden = getHiddenFields(jenisChosen);
  const faseHidden = getFaseHiddenFields(jenisChosen, faseChosen);
  const maintOnlyHidden = getMaintenanceOnlyHidden(jenisChosen);
  const hiddenFields = new Set([...jenisHidden, ...faseHidden, ...maintOnlyHidden]);
  // Sections filtered to remove hidden fields; if a section becomes empty it's dropped.
  const visibleSections = SECTIONS.map((s) => ({
    ...s,
    fields: s.fields.filter((f) => !hiddenFields.has(f.name)),
  })).filter((s) => s.fields.length > 0);
  const visibleActiveSection =
    visibleSections.find((s) => s.id === active) || visibleSections[0];

  if (loading) return <div className="p-8 text-muted-foreground mono">Loading…</div>;

  // ---------------- Jenis Order picker (step 0, mandatory for new) ----------------
  if (!isEdit && !jenisPicked) {
    // Sub-step: for MAINTENANCE, ask CM vs PM
    if (jenisChosen && needsMaintenanceType && !maintenanceType) {
      return (
        <div data-testid="workorder-maintenance-type-picker" className="p-6 lg:p-8 max-w-5xl mx-auto">
          <button
            onClick={backToJenisStep}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mb-4"
          >
            <CaretLeft size={12} /> Ganti Jenis Order
          </button>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Step 2 of 2 &middot; Wajib
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tighter mt-2">
            Jenis Maintenance
          </h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
            Pilih tipe maintenance: <span className="mono text-blue-600">Corrective</span>{" "}
            (reaktif atas gangguan) atau{" "}
            <span className="mono text-blue-600">Preventive</span> (pemeliharaan berkala).
            Tipe akan dicatat di badge WO dan mempengaruhi pelaporan.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
            {MAINTENANCE_TYPE_OPTIONS.map((mt) => {
              const info = MAINTENANCE_TYPE_META[mt];
              const Icon = mt === "CM" ? Wrench : ArrowsClockwise;
              return (
                <button
                  key={mt}
                  type="button"
                  data-testid={`maintenance-type-pick-${mt}`}
                  onClick={() => pickMaintenanceType(mt)}
                  className="group text-left border border-border bg-card hover:border-blue-500/60 hover:bg-blue-500/5 transition-all rounded-sm p-5"
                >
                  <div className="flex items-start justify-between">
                    <Icon
                      size={28}
                      weight="duotone"
                      className="text-blue-500 group-hover:text-blue-600"
                    />
                    <span className="mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      {info.label}
                    </span>
                  </div>
                  <div className="font-display text-xl font-bold tracking-tight mt-5">
                    {info.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2 leading-relaxed">
                    {info.desc}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    // Sub-step: for PSB/MUTASI/MIGRASI, ask fase pekerjaan
    if (jenisChosen && needsFase && !faseChosen) {
      return (
        <div data-testid="workorder-fase-picker" className="p-6 lg:p-8 max-w-5xl mx-auto">
          <button
            onClick={backToJenisStep}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mb-4"
          >
            <CaretLeft size={12} /> Ganti Jenis Order
          </button>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Step 2 of 2 &middot; Wajib
          </div>
          <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tighter mt-2">
            Pilih Fase Pekerjaan
          </h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
            Untuk jenis order <span className="mono text-blue-600">{jenisChosen}</span>,
            satu work order hanya mencakup satu fase pekerjaan. Field SPK, Timeline &amp; SLA,
            serta Hasil Pekerjaan akan otomatis disesuaikan.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
            {WO_FASE_OPTIONS.map((f) => {
              const info = {
                SURVEY: {
                  title: "Survey",
                  desc: "Kunjungan awal untuk asesmen lokasi & kebutuhan.",
                  Icon: Lightning,
                },
                INSTALASI: {
                  title: "Instalasi",
                  desc: "Pemasangan fisik perangkat & jaringan di lokasi.",
                  Icon: HardDrives,
                },
                AKTIVASI: {
                  title: "Aktivasi",
                  desc: "Konfigurasi & pengaktifan layanan pelanggan.",
                  Icon: Wrench,
                },
              }[f];
              const Icon = info.Icon;
              return (
                <button
                  key={f}
                  type="button"
                  data-testid={`fase-pick-${f}`}
                  onClick={() => pickFase(f)}
                  className="group text-left border border-border bg-card hover:border-blue-500/60 hover:bg-blue-500/5 transition-all rounded-sm p-5"
                >
                  <div className="flex items-start justify-between">
                    <Icon
                      size={26}
                      weight="duotone"
                      className="text-blue-500 group-hover:text-blue-600"
                    />
                    <span className="mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                      {f}
                    </span>
                  </div>
                  <div className="font-display text-xl font-bold tracking-tight mt-5">
                    {info.title}
                  </div>
                  <div className="text-xs text-muted-foreground mt-2 leading-relaxed">
                    {info.desc}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      );
    }

    return (
      <div data-testid="workorder-jenis-picker" className="p-6 lg:p-8 max-w-5xl mx-auto">
        <button
          onClick={() => nav("/workorders")}
          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mb-4"
        >
          <CaretLeft size={12} /> Batal &amp; kembali
        </button>
        <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
          Step 1 of 2 &middot; Wajib
        </div>
        <h1 className="font-display text-4xl sm:text-5xl font-black tracking-tighter mt-2">
          Pilih Jenis Order
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-2xl">
          Jenis order menentukan field yang perlu diisi. <span className="text-amber-500">
          Pilihan ini akan dikunci</span> setelah Anda melanjutkan &mdash; untuk ganti,
          batalkan dan mulai ulang.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
          {JENIS_ORDER_LIST.map((jenis) => {
            const meta = JENIS_ORDER_META[jenis];
            const Icon = JENIS_ICONS[jenis] || Lightning;
            return (
              <button
                key={jenis}
                data-testid={`jenis-pick-${jenis}`}
                onClick={() => pickJenis(jenis)}
                className="group text-left border border-border bg-card hover:border-blue-500/60 hover:bg-blue-500/5 transition-all rounded-sm p-5 relative overflow-hidden"
              >
                <div className="flex items-start justify-between">
                  <Icon
                    size={26}
                    weight="duotone"
                    className="text-blue-500 group-hover:text-blue-600"
                  />
                  <span className="mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                    {meta.label}
                  </span>
                </div>
                <div className="font-display text-xl font-bold tracking-tight mt-5">
                  {meta.title}
                </div>
                <div className="text-xs text-muted-foreground mt-2 leading-relaxed">
                  {meta.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div data-testid={WOFORM.root} className="p-6 lg:p-8 space-y-4">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <button
            onClick={() => nav("/workorders")}
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <CaretLeft size={12} /> Back to list
          </button>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-1">
            {isEdit ? "Edit" : "New"} Work Order
          </h1>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {jenisChosen && (
              <span
                data-testid="workorder-jenis-badge"
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border border-blue-500/40 bg-blue-500/10 text-blue-700 text-[10px] uppercase tracking-[0.2em] mono"
              >
                <LockKey size={10} weight="bold" /> {jenisChosen}
              </span>
            )}
            {faseChosen && jenisChosen !== "MAINTENANCE" && (
              <span
                data-testid="workorder-fase-badge"
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border border-emerald-500/40 bg-emerald-500/10 text-emerald-700 text-[10px] uppercase tracking-[0.2em] mono"
              >
                <LockKey size={10} weight="bold" /> Fase: {faseChosen}
              </span>
            )}
            {maintenanceType && (
              <span
                data-testid="workorder-maintenance-type-badge"
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border border-amber-500/40 bg-amber-500/10 text-amber-700 text-[10px] uppercase tracking-[0.2em] mono"
              >
                <LockKey size={10} weight="bold" /> {maintenanceType === "CM" ? "Corrective" : "Preventive"}
              </span>
            )}
            {isEdit && (
              <p className="text-xs text-muted-foreground mono">ID: {id}</p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {isEdit && (
            <a
              href={`${process.env.REACT_APP_BACKEND_URL}/api/workorders/${id}/pdf?auth=${encodeURIComponent(localStorage.getItem("la_token") || "")}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 border border-border bg-secondary hover:bg-slate-100 text-sm px-4 py-2 rounded-sm"
            >
              <FilePdf size={16} /> PDF
            </a>
          )}
          <button
            data-testid={WOFORM.cancelButton}
            onClick={() => nav("/workorders")}
            className="border border-border bg-secondary hover:bg-slate-100 text-sm px-4 py-2 rounded-sm"
          >
            Cancel
          </button>
          <button
            data-testid={WOFORM.saveButton}
            onClick={save}
            disabled={saving}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-sm disabled:opacity-60"
          >
            <FloppyDisk size={16} weight="bold" /> {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-4">
        <aside className="border border-border bg-card rounded-sm p-2 h-max">
          {(() => {
            const hasSa = String(form.sa_id || "").trim();
            const hasSi = String(form.si_id || "").trim();
            const sectionsLocked = !hasSa && !hasSi;
            return visibleSections.map((s, i) => {
              const isCustomer = s.id === "customer";
              const isLocked = sectionsLocked && !isCustomer;
              return (
                <button
                  key={s.id}
                  data-testid={`${WOFORM.sectionTab}-${s.id}`}
                  disabled={isLocked}
                  onClick={() => {
                    if (isLocked) {
                      toast.error(
                        "Isi SA ID atau SI ID di section Customer terlebih dahulu"
                      );
                      setActive("customer");
                      return;
                    }
                    setActive(s.id);
                  }}
                  className={`w-full text-left px-3 py-2 rounded-sm text-sm transition-colors flex items-center gap-3 ${
                    active === s.id
                      ? "bg-blue-500/10 text-blue-400 border-l-2 border-blue-500 pl-[10px]"
                      : isLocked
                      ? "text-muted-foreground/40 cursor-not-allowed"
                      : "text-muted-foreground hover:bg-slate-100 hover:text-foreground"
                  }`}
                  title={
                    isLocked
                      ? "Isi SA ID atau SI ID untuk membuka section ini"
                      : ""
                  }
                >
                  <span className="mono text-[10px] text-muted-foreground/70">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="flex-1">{s.label}</span>
                  {isLocked && (
                    <LockKey size={10} weight="fill" className="text-amber-500" />
                  )}
                </button>
              );
            });
          })()}
        </aside>

        <section className="border border-border bg-card rounded-sm p-5">
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground mb-1">
            Section
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight mb-6">
            {visibleActiveSection?.label}
          </h2>
          {visibleActiveSection?.id === "customer" && (
            <>
              <div
                data-testid="workorder-form-sa-si-hint"
                className="mb-4 px-3 py-2 border border-amber-300 bg-amber-50 text-amber-800 text-xs rounded-sm mono"
              >
                <b>*</b> Nama Pelanggan wajib diisi &middot; SA ID atau SI ID wajib
                diisi minimal salah satu untuk setiap Work Order.
              </div>
              <div className="mb-4 flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  data-testid="workorder-form-map-picker-btn"
                  onClick={() => setMapPickerOpen(true)}
                  disabled={!canEdit}
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-sm font-medium px-3 py-2 rounded-sm transition-colors"
                >
                  <MapPin size={14} weight="fill" /> Pilih Titik Lokasi di Peta
                </button>
                <span className="text-[11px] text-muted-foreground">
                  Otomatis mengisi Latitude &amp; Longitude dalam format DMS
                  (mis. <span className="mono">{`6°12'31.68"S`}</span>).
                </span>
              </div>
            </>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(visibleActiveSection?.fields || []).map((f) => {
              // Lock jenis_order — user harus batal untuk ganti
              if (f.name === "jenis_order") {
                return (
                  <label key={f.name} className="block">
                    <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                      {f.label} <span className="text-amber-500">(terkunci)</span>
                    </span>
                    <div className="w-full bg-secondary/50 border border-border rounded-sm px-3 py-2 text-sm flex items-center justify-between">
                      <span className="mono">{form.jenis_order || "-"}</span>
                      <LockKey size={14} className="text-muted-foreground" />
                    </div>
                  </label>
                );
              }
              // Multi-paket BoQ editor — locked until hasil_*_status is OK/BATAL
              if (f.type === "boq-items") {
                return (
                  <div key={f.name} className="md:col-span-2">
                    <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                      {f.label}
                    </span>
                    {billingReady ? (
                      <BoqItemsEditor
                        items={form.boq_items || []}
                        onChange={(items) => onChange("boq_items", items)}
                        disabled={!canEdit}
                        jenis={jenisChosen}
                      />
                    ) : (
                      <div
                        data-testid="workorder-form-boq-locked"
                        className="border border-amber-300 bg-amber-50 rounded-sm p-5 text-amber-800"
                      >
                        <div className="flex items-start gap-3">
                          <LockKey size={22} weight="duotone" className="text-amber-600 shrink-0 mt-0.5" />
                          <div className="text-sm leading-relaxed">
                            <div className="font-semibold text-amber-900 mb-1">
                              BoQ & Paket terkunci
                            </div>
                            Isi <b>hasil pekerjaan</b> dengan status <b>OK</b> atau{" "}
                            <b>BATAL</b> terlebih dahulu pada section{" "}
                            <button
                              type="button"
                              onClick={() => setActive("hasil")}
                              className="underline text-blue-700 hover:text-blue-900"
                            >
                              Hasil Pekerjaan
                            </button>{" "}
                            untuk membuka BoQ & Paket.
                            {currentBillableStatus && (
                              <div className="mt-2 text-xs mono">
                                Status sekarang:{" "}
                                <span className="px-1.5 py-0.5 rounded-sm bg-white border border-amber-300">
                                  {currentBillableStatus || "(kosong)"}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              }
              // Perangkat editor (nama + nomor registrasi, multi row)
              if (f.type === "perangkat-items") {
                return (
                  <div key={f.name} className="md:col-span-2">
                    <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                      {getFieldLabel(jenisChosen, f.name, f.label)}
                    </span>
                    <PerangkatEditor
                      items={form.perangkat_items || []}
                      onChange={(items) => onChange("perangkat_items", items)}
                      disabled={!canEdit}
                      jenis={jenisChosen}
                    />
                    <div className="mt-2 text-[11px] text-muted-foreground">
                      1 nomor registrasi hanya boleh dimiliki 1 SA ID / SI ID (WO).
                    </div>
                  </div>
                );
              }
              // Invoice summary card (read-only ringkasan dari BoQ). Auto-fill removed
              // per user request; new invoices are managed via /invoices module.
              if (f.type === "invoice-summary") {
                const t = computeBoqTotals(form.boq_items || []);
                const itemCount = (form.boq_items || []).length;
                const fmt = (n) =>
                  new Intl.NumberFormat("id-ID", {
                    style: "currency",
                    currency: "IDR",
                    maximumFractionDigits: 0,
                  }).format(Number(n) || 0);
                return (
                  <div
                    key={f.name}
                    data-testid="invoice-summary-card"
                    className="md:col-span-2 border border-blue-200 bg-blue-50/50 rounded-sm p-4"
                  >
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
                        {f.label}
                      </div>
                      <a
                        href="/invoices"
                        className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-sm font-medium transition-colors"
                      >
                        Buka Modul Invoice &rarr;
                      </a>
                    </div>
                    {itemCount === 0 ? (
                      <div className="mt-3 text-sm text-muted-foreground">
                        Belum ada paket di section BoQ. Isi terlebih dahulu untuk melihat
                        ringkasan invoice.
                      </div>
                    ) : (
                      <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                            Pelanggan
                          </div>
                          <div className="text-sm font-medium mt-0.5 truncate">
                            {form.pelanggan || "-"}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                            Jumlah Item
                          </div>
                          <div className="text-sm mono mt-0.5">{itemCount} paket</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                            Total Jasa
                          </div>
                          <div className="text-sm mono mt-0.5">{fmt(t.totalJasa)}</div>
                        </div>
                        <div>
                          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                            Total Material
                          </div>
                          <div className="text-sm mono mt-0.5">{fmt(t.totalMaterial)}</div>
                        </div>
                        <div className="col-span-2 md:col-span-4 pt-2 border-t border-blue-200 flex items-center justify-between">
                          <div className="text-xs uppercase tracking-[0.15em] font-semibold text-foreground">
                            Grand Total (siap ditagihkan)
                          </div>
                          <div
                            data-testid="invoice-summary-grand-total"
                            className="text-lg font-bold text-blue-700 mono"
                          >
                            {fmt(t.grandTotal)}
                          </div>
                        </div>
                      </div>
                    )}
                    <div className="mt-3 text-[11px] text-muted-foreground">
                      Untuk membuat invoice per pelanggan berdasarkan jenis pekerjaan
                      (multi-WO), gunakan menu <b>Invoices</b> di sidebar.
                    </div>
                  </div>
                );
              }
              // Invoice activity type picker: sekarang semua 5 opsi selalu ditampilkan.
              if (f.type === "invoice-activity-type") {
                const options = invoiceActivityOptionsFor(form.jenis_order);
                return (
                  <div key={f.name} className="md:col-span-2">
                    <span className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                      {f.label}
                    </span>
                    <div className="flex flex-wrap gap-2" data-testid="invoice-activity-type-picker">
                      {options.map((opt) => {
                        const on = form.inv_jenis_pekerjaan === opt;
                        return (
                          <button
                            key={opt}
                            type="button"
                            data-testid={`inv-activity-${opt}`}
                            disabled={!canEdit}
                            onClick={() => onChange("inv_jenis_pekerjaan", opt)}
                            className={`px-4 py-2 text-xs uppercase tracking-[0.15em] rounded-sm border transition-colors ${
                              on
                                ? "bg-blue-600 border-blue-600 text-white"
                                : "bg-white border-border text-muted-foreground hover:border-blue-500 hover:text-blue-700"
                            }`}
                          >
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                    <div className="mt-1.5 text-[11px] text-muted-foreground">
                      Field ini legacy / referensi. Untuk invoice sebenarnya, gunakan modul
                      Invoices.
                    </div>
                  </div>
                );
              }
              return (
                <Field
                  key={f.name}
                  f={{
                    ...f,
                    label:
                      getFieldLabel(jenisChosen, f.name, f.label) +
                      (f.maintenanceOnly && jenisChosen === "MAINTENANCE" ? " *" : ""),
                  }}
                  value={form[f.name]}
                  onChange={onChange}
                />
              );
            })}
          </div>
        </section>
      </div>

      {isEdit && <Attachments workorderId={id} canEdit={canEdit} />}

      <MapPicker
        open={mapPickerOpen}
        initialLat={form.lat}
        initialLng={form.lng}
        onClose={() => setMapPickerOpen(false)}
        onApply={(latDms, lngDms) => {
          setForm((f) => ({ ...f, lat: latDms, lng: lngDms }));
          setMapPickerOpen(false);
          toast.success("Koordinat DMS diterapkan ke form");
        }}
      />
    </div>
  );
}
