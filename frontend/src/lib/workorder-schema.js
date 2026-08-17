// Schema definitions for the LA workorder form.
// Sections drive the multi-step form and reuse identical field metadata for
// dashboard, table, and report views.

// Dependent "Perangkat" options per Jenis Media Akses. "PIHAK KE 3" has none.
export const MEDIA_PERANGKAT_OPTIONS = {
  WIRELINE: ["M2M", "Open Port", "AIR Fiber", "GPON", "Standalone", "Back to Back", "SDWAN", "Router"],
  WIRELESS: ["BWA", "Radio Link"],
  SATELLITE: ["Idirect", "Hughes", "Starlink"],
  "PIHAK KE 3": [],
};

export const SECTIONS = [
  {
    id: "customer",
    label: "Pelanggan",
    fields: [
      { name: "pelanggan", label: "Nama Pelanggan *", type: "text" },
      { name: "si_id", label: "SI ID *", type: "text" },
      {
        name: "jenis_order",
        label: "Jenis Order",
        type: "select",
        options: ["PSB", "MUTASI", "MIGRASI", "DISMANTLE", "MAINTENANCE"],
      },
      { name: "alamat", label: "Alamat", type: "textarea", wide: true, rows: 3 },
      { name: "sa_id", label: "SA ID *", type: "text" },
      { name: "lat", label: "Latitude", type: "text", mono: true, dms: true, placeholder: `6°12'31.68"S` },
      { name: "lng", label: "Longitude", type: "text", mono: true, dms: true, placeholder: `106°49'01.20"E` },
      { name: "rfs_la", label: "RFS LA", type: "date" },
      { name: "rfs_pelanggan", label: "RFS Pelanggan", type: "date" },
      { name: "bw", label: "Bandwidth", type: "bandwidth", placeholder: "e.g. 50" },
    ],
  },
  {
    id: "spk",
    label: "SPK",
    fields: [
      { name: "case_no", label: "No. Case", type: "text", mono: true, maintenanceOnly: true },
      { name: "task_no", label: "No. Task", type: "text", mono: true, maintenanceOnly: true },
      { name: "spk_survey_nomor", label: "SPK Survey Nomor", type: "text" },
      { name: "spk_survey_tgl_doc", label: "SPK Survey Tgl Doc", type: "date" },
      { name: "spk_survey_tgl_terima", label: "SPK Survey Tgl Terima", type: "date" },
      { name: "spk_instalasi_nomor", label: "SPK Instalasi Nomor", type: "text" },
      { name: "spk_instalasi_tgl_doc", label: "SPK Instalasi Tgl Doc", type: "date" },
      { name: "spk_instalasi_tgl_terima", label: "SPK Instalasi Tgl Terima", type: "date" },
      { name: "spk_aktivasi_nomor", label: "SPK Aktivasi Nomor", type: "text" },
      { name: "spk_aktivasi_tgl_doc", label: "SPK Aktivasi Tgl Doc", type: "date" },
      { name: "spk_aktivasi_tgl_terima", label: "SPK Aktivasi Tgl Terima", type: "date" },
    ],
  },
  {
    id: "timeline",
    label: "Timeline & SLA",
    fields: [
      { name: "activity_survey_start", label: "Activity Survey Start", type: "date" },
      { name: "activity_survey_end", label: "Activity Survey End", type: "date" },
      { name: "activity_instalasi_start", label: "Activity Instalasi Start", type: "date" },
      { name: "activity_instalasi_end", label: "Activity Instalasi End", type: "date" },
      { name: "activity_aktivasi_start", label: "Activity Aktivasi Start", type: "date" },
      { name: "activity_aktivasi_end", label: "Activity Aktivasi End", type: "date" },
      { name: "stop_survey_start", label: "Stop Clock Survey Start", type: "date" },
      { name: "stop_survey_end", label: "Stop Clock Survey End", type: "date" },
      { name: "stop_instalasi_start", label: "Stop Clock Instalasi Start", type: "date" },
      { name: "stop_instalasi_end", label: "Stop Clock Instalasi End", type: "date" },
      { name: "stop_aktivasi_start", label: "Stop Clock Aktivasi Start", type: "date" },
      { name: "stop_aktivasi_end", label: "Stop Clock Aktivasi End", type: "date" },
      { name: "sdt_survey_durasi", label: "SDT Survey Durasi", type: "text", mono: true, placeholder: "e.g. 3 HARI" },
      { name: "sdt_survey_target", label: "SDT Survey Target", type: "text", mono: true, placeholder: "e.g. 5 HARI" },
      { name: "sdt_instalasi_durasi", label: "SDT Instalasi Durasi", type: "text", mono: true },
      { name: "sdt_instalasi_target", label: "SDT Instalasi Target", type: "text", mono: true },
      { name: "sdt_aktivasi_durasi", label: "SDT Aktivasi Durasi", type: "text", mono: true },
      { name: "sdt_aktivasi_target", label: "SDT Aktivasi Target", type: "text", mono: true },
    ],
  },
  {
    id: "media",
    label: "Media & Kontak",
    fields: [
      {
        name: "media_jenis",
        label: "Jenis Media Akses",
        type: "select",
        options: ["WIRELINE", "WIRELESS", "SATELLITE", "PIHAK KE 3"],
      },
      { name: "media_perangkat", label: "Perangkat", type: "text" },
      { name: "cp_la", label: "CP LA", type: "text" },
      { name: "cp_pelanggan", label: "CP Pelanggan", type: "text" },
      { name: "cp_mitra", label: "CP Pelaksana", type: "text" },
      {
        name: "tim_pelaksana",
        label: "Tim Pelaksana",
        type: "select",
        options: ["", "INTERNAL", "MITRA"],
      },
      { name: "teknisi_pelaksana", label: "Nama Teknisi", type: "teknisi-list" },
    ],
  },
  {
    id: "hasil",
    label: "Hasil Pekerjaan",
    fields: [
      {
        name: "hasil_survey_status",
        label: "Survey Status",
        type: "select",
        options: ["", "OK", "PENDING", "BATAL"],
      },
      { name: "hasil_survey_datek", label: "Survey Datek", type: "textarea", wide: true, rows: 5 },
      { name: "hasil_survey_npae", label: "Survey NPAE", type: "text" },
      {
        name: "hasil_instalasi_status",
        label: "Instalasi Status",
        type: "select",
        options: ["", "OK", "PENDING", "BATAL"],
      },
      { name: "hasil_instalasi_datek", label: "Instalasi Datek", type: "textarea", wide: true, rows: 5 },
      { name: "hasil_instalasi_npae", label: "Instalasi NPAE", type: "text" },
      {
        name: "hasil_aktivasi_status",
        label: "Aktivasi Status",
        type: "select",
        options: ["", "OK", "PENDING", "BATAL"],
      },
      { name: "hasil_aktivasi_datek", label: "Aktivasi Datek", type: "textarea", wide: true, rows: 5 },
      { name: "hasil_aktivasi_npae", label: "Aktivasi NPAE", type: "text" },
      { name: "perangkat_items", label: "Perangkat Terpasang", type: "perangkat-items" },
    ],
  },
  {
    id: "info",
    label: "Info Pelanggan",
    fields: [
      { name: "info_kondisi", label: "Kondisi Pelanggan", type: "textarea" },
      { name: "info_masalah", label: "Info Masalah", type: "textarea" },
      { name: "info_perizinan", label: "Perizinan", type: "text" },
      { name: "info_biaya", label: "Biaya", type: "text" },
      { name: "info_tindak_lanjut", label: "Tindak Lanjut", type: "textarea" },
    ],
  },
  {
    id: "boq",
    label: "BoQ & Paket",
    fields: [
      { name: "boq_items", label: "Paket / BoQ Items", type: "boq-items" },
    ],
  },
  {
    id: "invoice",
    label: "Invoice",
    fields: [
      { name: "invoice_summary", label: "Ringkasan dari BoQ", type: "invoice-summary" },
      {
        name: "inv_jenis_pekerjaan",
        label: "Jenis Pekerjaan Invoice",
        type: "invoice-activity-type",
      },
      { name: "inv_no", label: "No Invoice", type: "text", mono: true },
      { name: "inv_tgl", label: "Tanggal Invoice", type: "date" },
      { name: "inv_tgl_kirim", label: "Tanggal Kirim", type: "date" },
      { name: "inv_tgl_bayar", label: "Tanggal Bayar", type: "date" },
      {
        name: "inv_status",
        label: "Status Invoice",
        type: "select",
        options: ["", "OPEN", "SENT", "PAID", "OVERDUE"],
      },
      { name: "keterangan", label: "Keterangan", type: "textarea" },
    ],
  },
];

export const ALL_FIELDS = SECTIONS.flatMap((s) => s.fields);

// Jenis Order metadata: label, description, and which fields are hidden for that jenis.
// DISMANTLE and MAINTENANCE tidak butuh section/step Aktivasi, tapi tetap butuh BoQ.
const AKTIVASI_FIELDS = [
  "spk_aktivasi_nomor",
  "spk_aktivasi_tgl_doc",
  "spk_aktivasi_tgl_terima",
  "activity_aktivasi_start",
  "activity_aktivasi_end",
  "stop_aktivasi_start",
  "stop_aktivasi_end",
  "sdt_aktivasi_durasi",
  "sdt_aktivasi_target",
  "hasil_aktivasi_status",
  "hasil_aktivasi_datek",
  "hasil_aktivasi_npae",
];

// DISMANTLE work order minimal fields:
// hide customer geo/bw/rfs, hide entire Timeline&SLA + Aktivasi,
// keep only spk_survey_nomor + spk_survey_tgl_doc as "SPK Dismantle",
// keep only hasil_survey_status + perangkat_items as "Hasil Dismantle".
const DISMANTLE_EXTRA_HIDDEN = [
  "sa_id",
  "bw",
  "lat",
  "lng",
  "rfs_la",
  "rfs_pelanggan",
  // SPK: keep survey nomor + tgl_doc + tgl_terima (relabeled as SPK Dismantle)
  "spk_instalasi_nomor",
  "spk_instalasi_tgl_doc",
  "spk_instalasi_tgl_terima",
  // Timeline & SLA — hide all remaining (aktivasi already hidden)
  "activity_survey_start",
  "activity_survey_end",
  "activity_instalasi_start",
  "activity_instalasi_end",
  "stop_survey_start",
  "stop_survey_end",
  "stop_instalasi_start",
  "stop_instalasi_end",
  "sdt_survey_durasi",
  "sdt_survey_target",
  "sdt_instalasi_durasi",
  "sdt_instalasi_target",
  // Hasil — keep hasil_survey_status only (Status Dismantle)
  "hasil_survey_datek",
  "hasil_survey_npae",
  "hasil_instalasi_status",
  "hasil_instalasi_datek",
  "hasil_instalasi_npae",
];

// MAINTENANCE work order fields:
// Hide sa_id (only si_id used), lat/lng/bw, rfs_la, rfs_pelanggan,
// Hide SPK Instalasi block (only survey-level SPK used, relabeled to "No. SPK").
// Hide activity/stop/sdt for all phases (aktivasi already hidden).
// case_no & task_no shown in SPK section (added conditionally).
const MAINTENANCE_EXTRA_HIDDEN = [
  "sa_id",
  "bw",
  "rfs_la",
  "rfs_pelanggan",
  // SPK: keep survey nomor + tgl_doc only, relabeled to "No. SPK" / "Tanggal SPK"
  "spk_survey_tgl_terima",
  "spk_instalasi_nomor",
  "spk_instalasi_tgl_doc",
  "spk_instalasi_tgl_terima",
  // Timeline & SLA — hide all (aktivasi already hidden)
  "activity_survey_start",
  "activity_survey_end",
  "activity_instalasi_start",
  "activity_instalasi_end",
  "stop_survey_start",
  "stop_survey_end",
  "stop_instalasi_start",
  "stop_instalasi_end",
  "sdt_survey_durasi",
  "sdt_survey_target",
  "sdt_instalasi_durasi",
  "sdt_instalasi_target",
  // Hasil — keep hasil_survey_status (Status Maintenance) + hasil_survey_datek
  // (Datek Maintenance) + perangkat_items. Hide the rest.
  "hasil_survey_npae",
  "hasil_instalasi_status",
  "hasil_instalasi_datek",
  "hasil_instalasi_npae",
];

export const JENIS_ORDER_META = {
  PSB: {
    label: "PSB",
    title: "Pasang Sambungan Baru",
    desc: "Instalasi pelanggan baru dari 0 (Survey → Instalasi → Aktivasi).",
    hidden: [],
  },
  MUTASI: {
    label: "MUTASI",
    title: "Mutasi Pelanggan",
    desc: "Perpindahan layanan / paket / lokasi pelanggan existing.",
    hidden: [],
  },
  MIGRASI: {
    label: "MIGRASI",
    title: "Migrasi Layanan",
    desc: "Migrasi platform / bandwidth / media akses.",
    hidden: [],
  },
  DISMANTLE: {
    label: "DISMANTLE",
    title: "Dismantle / Cabut",
    desc: "Pencabutan perangkat & layanan. Hanya butuh SPK, status & daftar perangkat tercabut.",
    hidden: [...AKTIVASI_FIELDS, ...DISMANTLE_EXTRA_HIDDEN],
  },
  MAINTENANCE: {
    label: "MAINTENANCE",
    title: "Maintenance / Perbaikan",
    desc: "Kunjungan pemeliharaan/perbaikan (Corrective atau Preventive). Butuh No. Case & No. Task.",
    hidden: [...AKTIVASI_FIELDS, ...MAINTENANCE_EXTRA_HIDDEN],
  },
};

// Label overrides per jenis_order — some fields keep their DB name but the
// UI label reads differently in certain contexts (e.g. DISMANTLE re-uses the
// spk_survey_* fields as "SPK Dismantle").
export const JENIS_ORDER_LIST = Object.keys(JENIS_ORDER_META);

// Label overrides per jenis_order — some fields keep their DB name but the
// UI label reads differently in certain contexts (e.g. DISMANTLE re-uses the
// spk_survey_* fields as "SPK Dismantle").
export const JENIS_FIELD_LABEL_OVERRIDES = {
  DISMANTLE: {
    spk_survey_nomor: "SPK Dismantle",
    spk_survey_tgl_doc: "SPK Dismantle Tanggal Doc",
    spk_survey_tgl_terima: "SPK Dismantle Diterima",
    hasil_survey_status: "Dismantle Status",
  },
  MAINTENANCE: {
    spk_survey_nomor: "No. SPK",
    spk_survey_tgl_doc: "Tanggal SPK",
    hasil_survey_status: "Status Maintenance",
    hasil_survey_datek: "Datek Maintenance",
    perangkat_items: "flow perangkat",
  },
};

export function getFieldLabel(jenis, fieldName, defaultLabel) {
  return JENIS_FIELD_LABEL_OVERRIDES[jenis]?.[fieldName] || defaultLabel;
}

export function getHiddenFields(jenis) {
  return new Set((JENIS_ORDER_META[jenis]?.hidden) || []);
}

// Fields marked maintenanceOnly must be hidden for non-MAINTENANCE orders.
export function getMaintenanceOnlyHidden(jenis) {
  if (jenis === "MAINTENANCE") return new Set();
  const hidden = new Set();
  ALL_FIELDS.forEach((f) => {
    if (f.maintenanceOnly) hidden.add(f.name);
  });
  return hidden;
}

export function emptyWorkOrder() {
  const obj = {};
  ALL_FIELDS.forEach((f) => {
    if (
      f.type === "invoice-summary" ||
      f.type === "invoice-activity-type" ||
      f.type === "boq-items" ||
      f.type === "perangkat-items" ||
      f.type === "teknisi-list"
    ) {
      if (f.type === "boq-items" || f.type === "perangkat-items" || f.type === "teknisi-list")
        obj[f.name] = [];
      return;
    }
    obj[f.name] = f.type === "number" ? 0 : "";
  });
  obj.boq_mode = "both";
  obj.boq_paket_code = "";
  obj.boq_paket = "";
  obj.boq_jasa = 0;
  obj.boq_material = 0;
  obj.boq_jumlah = 0;
  obj.inv_jenis_pekerjaan = "";
  obj.wo_jenis_pekerjaan = "";
  obj.maintenance_type = "";
  obj.case_no = "";
  obj.task_no = "";
  return obj;
}

// Which activity type(s) are valid for the WO's jenis_order.
// User request: tampilkan semua 5 opsi selalu, tidak lagi dibatasi per jenis WO.
export const INVOICE_ACTIVITY_OPTIONS_ALL = ["SURVEY", "INSTALASI", "AKTIVASI", "DISMANTLE", "MAINTENANCE"];

export function invoiceActivityOptionsFor(_jenis) {
  return INVOICE_ACTIVITY_OPTIONS_ALL;
}

// -----------------------------------------------------------------------
// Fase pekerjaan (per WO) — for PSB/MUTASI/MIGRASI, user picks 1 fase only.
// -----------------------------------------------------------------------
export const WO_FASE_OPTIONS = ["SURVEY", "INSTALASI", "AKTIVASI"];

export function requiresFasePicker(jenis) {
  return jenis === "PSB" || jenis === "MUTASI" || jenis === "MIGRASI";
}

// MAINTENANCE-specific: after picking MAINTENANCE the user must pick CM vs PM.
export const MAINTENANCE_TYPE_OPTIONS = ["CM", "PM"];

export const MAINTENANCE_TYPE_META = {
  CM: {
    label: "CM",
    title: "Corrective Maintenance",
    desc: "Perbaikan gangguan / kerusakan yang sudah terjadi (reactive).",
  },
  PM: {
    label: "PM",
    title: "Preventive Maintenance",
    desc: "Pemeliharaan berkala terjadwal untuk mencegah gangguan (proactive).",
  },
};

export function requiresMaintenanceTypePicker(jenis) {
  return jenis === "MAINTENANCE";
}

// Return set of field names that must be HIDDEN for the picked fase.
// Only relevant for PSB/MUTASI/MIGRASI. Returns empty set otherwise.
export function getFaseHiddenFields(jenis, fase) {
  if (!requiresFasePicker(jenis) || !fase) return new Set();
  const allPhases = ["survey", "instalasi", "aktivasi"];
  const keepPhase = fase.toLowerCase();
  const hidePhases = allPhases.filter((p) => p !== keepPhase);
  const hidden = new Set();
  hidePhases.forEach((p) => {
    hidden.add(`spk_${p}_nomor`);
    hidden.add(`spk_${p}_tgl_doc`);
    hidden.add(`spk_${p}_tgl_terima`);
    hidden.add(`activity_${p}_start`);
    hidden.add(`activity_${p}_end`);
    hidden.add(`stop_${p}_start`);
    hidden.add(`stop_${p}_end`);
    hidden.add(`sdt_${p}_durasi`);
    hidden.add(`sdt_${p}_target`);
    hidden.add(`hasil_${p}_status`);
    hidden.add(`hasil_${p}_datek`);
    hidden.add(`hasil_${p}_npae`);
  });
  // Perangkat terpasang tidak relevan pada fase Survey.
  if (keepPhase === "survey") {
    hidden.add("perangkat_items");
  }
  return hidden;
}

export const TABLE_COLUMNS = [
  { key: "pelanggan", label: "Pelanggan" },
  { key: "sa_id", label: "SA ID", mono: true },
  { key: "si_id", label: "SI ID", mono: true },
  { key: "jenis_order", label: "Jenis Order" },
  { key: "jenis_pekerjaan", label: "Jenis Pekerjaan", virtual: true },
  { key: "bw", label: "BW", mono: true },
  { key: "media_jenis", label: "Media" },
  { key: "spk_summary", label: "No SPK", virtual: true },
  { key: "invoice_no_display", label: "No Invoice", virtual: true },
  { key: "current_activity", label: "Activity", virtual: true },
  { key: "boq_jumlah", label: "Total", mono: true, numeric: true },
];

// Human-readable "jenis pekerjaan" per work order:
//   PSB / MUTASI / MIGRASI → wo_jenis_pekerjaan (SURVEY / INSTALASI / AKTIVASI)
//   MAINTENANCE            → CM (Corrective) or PM (Preventive)
//   DISMANTLE              → DISMANTLE
export function deriveJenisPekerjaan(row) {
  const jo = (row.jenis_order || "").toUpperCase();
  if (jo === "MAINTENANCE") {
    const mt = (row.maintenance_type || "").toUpperCase();
    if (mt === "CM") return "CM (Corrective)";
    if (mt === "PM") return "PM (Preventive)";
    return "MAINTENANCE";
  }
  if (jo === "DISMANTLE") return "DISMANTLE";
  return (row.wo_jenis_pekerjaan || "").toUpperCase() || "—";
}

// Ordered phases used to derive current activity per work order.
// For DISMANTLE / MAINTENANCE the aktivasi phase is not applicable.
export function activityPhasesFor(jenis) {
  if (jenis === "DISMANTLE" || jenis === "MAINTENANCE") {
    return ["survey", "instalasi"];
  }
  return ["survey", "instalasi", "aktivasi"];
}

export function deriveSpkSummary(row) {
  const parts = [];
  const map = [
    ["S", row.spk_survey_nomor],
    ["I", row.spk_instalasi_nomor],
    ["A", row.spk_aktivasi_nomor],
  ];
  map.forEach(([tag, v]) => {
    if (v) parts.push(`${tag}: ${v}`);
  });
  return parts;
}

export function deriveCurrentActivity(row) {
  const phases = activityPhasesFor(row.jenis_order);
  let last = { phase: null, state: "idle" };
  for (const p of phases) {
    const start = row[`activity_${p}_start`];
    const end = row[`activity_${p}_end`];
    if (start && !end) return { phase: p, state: "on-going" };
    if (start && end) last = { phase: p, state: "done" };
  }
  if (last.phase) {
    // If last phase done and it's the final phase → all-done
    const finalPhase = phases[phases.length - 1];
    if (last.phase === finalPhase) return { phase: last.phase, state: "complete" };
    return { phase: last.phase, state: "done" };
  }
  return { phase: null, state: "none" };
}
