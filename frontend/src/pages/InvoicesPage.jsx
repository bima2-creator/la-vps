import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { formatIDR } from "@/lib/format";
import { toast } from "sonner";
import {
  Receipt,
  Plus,
  X,
  ArrowClockwise,
  Trash,
  PencilSimple,
  MagnifyingGlass,
  Warning,
  FilePdf,
} from "@phosphor-icons/react";
import { useAuth } from "@/context/AuthContext";

// Each invoice covers exactly ONE phase/jenis pekerjaan. Customers can be one
// or more, but all their WOs must share the same phase.
const INVOICE_CATEGORIES = [
  {
    value: "SURVEY",
    title: "SURVEY",
    hint: "Untuk WO fase Survey (PSB / Mutasi / Migrasi).",
  },
  {
    value: "INSTALASI",
    title: "INSTALASI",
    hint: "Untuk WO fase Instalasi (PSB / Mutasi / Migrasi).",
  },
  {
    value: "AKTIVASI",
    title: "AKTIVASI",
    hint: "Untuk WO fase Aktivasi (PSB / Mutasi / Migrasi).",
  },
  {
    value: "DISMANTLE",
    title: "DISMANTLE",
    hint: "Hanya work order jenis Dismantle.",
  },
  {
    value: "MAINTENANCE",
    title: "MAINTENANCE",
    hint: "Hanya work order Maintenance (CM / PM).",
  },
];
// For the list-page filter dropdown, include all values including legacy NON_MAINTENANCE.
const ACTIVITY_TYPES = ["SURVEY", "INSTALASI", "AKTIVASI", "DISMANTLE", "MAINTENANCE", "NON_MAINTENANCE"];
const STATUS_OPTIONS = ["OPEN", "SENT", "PAID", "LUNAS", "OVERDUE"];

const STATUS_BADGE = {
  OPEN: "bg-blue-100 text-blue-700 border-blue-200",
  SENT: "bg-amber-100 text-amber-800 border-amber-200",
  PAID: "bg-emerald-100 text-emerald-800 border-emerald-200",
  LUNAS: "bg-emerald-100 text-emerald-800 border-emerald-200",
  OVERDUE: "bg-red-100 text-red-700 border-red-200",
};

function makeInvoiceNo() {
  // Deprecated. Backend now auto-generates INV/NN/RomanMonth/YYYY on POST /invoices.
  return "";
}

export default function InvoicesPage() {
  const { user } = useAuth();
  const canEdit = user && (user.role === "admin" || user.role === "operator");
  const canDelete = user && user.role === "admin";

  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [jenisFilter, setJenisFilter] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editingInv, setEditingInv] = useState(null); // full invoice for editing

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/invoices");
      setInvoices(data);
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    return invoices.filter((iv) => {
      if (statusFilter && (iv.status || "").toUpperCase() !== statusFilter) return false;
      if (jenisFilter && iv.jenis_pekerjaan !== jenisFilter) return false;
      if (q) {
        const s = q.toLowerCase();
        const custStr = (iv.pelanggans || [iv.pelanggan])
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!custStr.includes(s) && !(iv.invoice_no || "").toLowerCase().includes(s))
          return false;
      }
      return true;
    });
  }, [invoices, q, statusFilter, jenisFilter]);

  const onCreate = () => {
    setEditingInv(null);
    setFormOpen(true);
  };

  const onEdit = (iv) => {
    setEditingInv(iv);
    setFormOpen(true);
  };

  const onDelete = async (iv) => {
    if (!window.confirm(`Hapus invoice ${iv.invoice_no || iv.id}?`)) return;
    try {
      await api.delete(`/invoices/${iv.id}`);
      toast.success("Invoice dihapus");
      load();
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  return (
    <div className="p-6 lg:p-8" data-testid="invoices-page">
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Modul
          </div>
          <h1 className="font-display text-4xl font-black tracking-tighter mt-1 flex items-center gap-3">
            <Receipt size={32} weight="duotone" className="text-blue-500" />
            Invoices
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Buat invoice per pelanggan berdasarkan jenis pekerjaan (Survey /
            Instalasi / Aktivasi / Dismantle / Maintenance). Satu invoice bisa
            berisi beberapa work order.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            data-testid="invoices-refresh"
            onClick={load}
            className="border border-border bg-white hover:bg-slate-100 rounded-sm px-3 py-2 text-sm transition-colors"
          >
            <ArrowClockwise size={14} className="inline mr-1.5" /> Refresh
          </button>
          {canEdit && (
            <button
              data-testid="invoices-create"
              onClick={onCreate}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-sm inline-flex items-center gap-2 transition-colors"
            >
              <Plus size={14} weight="bold" /> Buat Invoice
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="border border-border bg-card rounded-sm p-3 mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <MagnifyingGlass size={14} className="text-muted-foreground" />
          <input
            data-testid="invoices-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cari nomor invoice / pelanggan…"
            className="flex-1 bg-transparent outline-none text-sm"
          />
        </div>
        <select
          data-testid="invoices-filter-jenis"
          value={jenisFilter}
          onChange={(e) => setJenisFilter(e.target.value)}
          className="border border-border bg-white rounded-sm px-2 py-1.5 text-sm"
        >
          <option value="">All Jenis</option>
          {ACTIVITY_TYPES.map((a) => (
            <option key={a}>{a}</option>
          ))}
        </select>
        <select
          data-testid="invoices-filter-status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-border bg-white rounded-sm px-2 py-1.5 text-sm"
        >
          <option value="">All Status</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="border border-border bg-card rounded-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-border">
            <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              <th className="text-left px-3 py-2">No Invoice</th>
              <th className="text-left px-3 py-2">Pelanggan</th>
              <th className="text-left px-3 py-2">Jenis Pekerjaan</th>
              <th className="text-left px-3 py-2">Tanggal</th>
              <th className="text-right px-3 py-2">Jumlah WO</th>
              <th className="text-right px-3 py-2">Grand Total</th>
              <th className="text-left px-3 py-2">Status</th>
              <th className="w-24"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="8" className="text-center p-6 text-muted-foreground">
                  Loading…
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan="8" className="text-center p-8 text-muted-foreground">
                  <Receipt size={28} weight="duotone" className="mx-auto mb-2 opacity-50" />
                  Belum ada invoice.{" "}
                  {canEdit ? (
                    <>
                      Klik{" "}
                      <button
                        type="button"
                        data-testid="invoice-empty-open-create"
                        onClick={onCreate}
                        className="text-blue-600 underline underline-offset-2 hover:text-blue-700 font-medium"
                      >
                        Buat Invoice
                      </button>{" "}
                      untuk mulai.
                    </>
                  ) : (
                    "Belum ada data untuk ditampilkan."
                  )}
                </td>
              </tr>
            ) : (
              filtered.map((iv) => (
                <tr
                  key={iv.id}
                  data-testid="invoice-row"
                  className="border-b border-border last:border-0 hover:bg-blue-50/40"
                >
                  <td className="px-3 py-2 mono text-blue-600">
                    {iv.invoice_no ? (
                      <button
                        type="button"
                        data-testid={`invoice-row-open-${iv.id}`}
                        onClick={() => onEdit(iv)}
                        className="text-blue-600 hover:text-blue-800 hover:underline underline-offset-2 font-medium text-left"
                        title="Buka detail invoice"
                      >
                        {iv.invoice_no}
                      </button>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                    {iv.inv_no_eproc && (
                      <div
                        data-testid="invoice-row-eproc"
                        className="text-[10px] mono text-slate-500 mt-0.5"
                        title="No Invoice EPROC"
                      >
                        EPROC: {iv.inv_no_eproc}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {(iv.pelanggans && iv.pelanggans.length > 1) ? (
                      <div>
                        <div className="font-medium">
                          {iv.pelanggans.length} Pelanggan
                        </div>
                        <div className="text-[11px] text-muted-foreground truncate max-w-xs">
                          {iv.pelanggans.join(", ")}
                        </div>
                      </div>
                    ) : (
                      (iv.pelanggans && iv.pelanggans[0]) || iv.pelanggan
                    )}
                  </td>
                  <td className="px-3 py-2 mono text-xs">
                    <span className="px-2 py-0.5 rounded-sm border border-border bg-slate-50 uppercase tracking-wide">
                      {iv.jenis_pekerjaan}
                    </span>
                  </td>
                  <td className="px-3 py-2 mono text-xs">{iv.tanggal || "-"}</td>
                  <td className="px-3 py-2 text-right mono">
                    {(iv.work_order_ids || []).length}
                  </td>
                  <td className="px-3 py-2 text-right mono font-semibold text-foreground">
                    {formatIDR(iv.grand_total)}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-wider mono ${
                        STATUS_BADGE[iv.status] || "bg-slate-100 text-slate-700 border-slate-200"
                      }`}
                    >
                      {iv.status || "-"}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button
                      data-testid={`invoice-pdf-${iv.id}`}
                      onClick={async () => {
                        if (!iv.inv_no_eproc) {
                          toast.error("Isi No Invoice EPROC dulu untuk mengaktifkan PDF");
                          return;
                        }
                        try {
                          const resp = await api.get(`/invoices/${iv.id}/pdf`, {
                            responseType: "blob",
                          });
                          const blob = new Blob([resp.data], { type: "application/pdf" });
                          const url = window.URL.createObjectURL(blob);
                          window.open(url, "_blank");
                          setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
                        } catch (e) {
                          toast.error(formatApiError(e) || "Gagal generate PDF");
                        }
                      }}
                      disabled={!iv.inv_no_eproc}
                      className={`p-1 mr-1 ${
                        iv.inv_no_eproc
                          ? "text-red-600 hover:text-red-700"
                          : "text-muted-foreground/40 cursor-not-allowed"
                      }`}
                      title={
                        iv.inv_no_eproc
                          ? "Print / Download PDF"
                          : "Isi No Invoice EPROC dulu untuk mengaktifkan PDF"
                      }
                    >
                      <FilePdf size={14} weight="fill" />
                    </button>
                    {canEdit && (
                      <button
                        data-testid={`invoice-edit-${iv.id}`}
                        onClick={() => onEdit(iv)}
                        className="p-1 text-muted-foreground hover:text-blue-600"
                        title="Edit"
                      >
                        <PencilSimple size={14} />
                      </button>
                    )}
                    {canDelete && (
                      <button
                        data-testid={`invoice-delete-${iv.id}`}
                        onClick={() => onDelete(iv)}
                        className="p-1 text-muted-foreground hover:text-red-600 ml-1"
                        title="Hapus"
                      >
                        <Trash size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Modal */}
      {formOpen && (
        <InvoiceForm
          initial={editingInv}
          onClose={() => setFormOpen(false)}
          onSaved={() => {
            setFormOpen(false);
            load();
          }}
        />
      )}
    </div>
  );
}

// ---------------- InvoiceForm ----------------
function InvoiceForm({ initial, onClose, onSaved }) {
  const isEdit = Boolean(initial);
  const [allCustomers, setAllCustomers] = useState([]);
  const [customerDiag, setCustomerDiag] = useState(null);
  const [jenisPekerjaan, setJenisPekerjaan] = useState(initial?.jenis_pekerjaan || "");
  const [selectedPelanggans, setSelectedPelanggans] = useState(
    initial?.pelanggans && initial.pelanggans.length > 0
      ? initial.pelanggans
      : initial?.pelanggan
      ? [initial.pelanggan]
      : []
  );
  const [addingPelanggan, setAddingPelanggan] = useState(false);
  const [customerSearch, setCustomerSearch] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState(new Set(initial?.work_order_ids || []));
  const [loadingCand, setLoadingCand] = useState(false);
  const [meta, setMeta] = useState({
    invoice_no: initial?.invoice_no || "",
    inv_no_eproc: initial?.inv_no_eproc || "",
    tanggal: initial?.tanggal || new Date().toISOString().slice(0, 10),
    tgl_kirim: initial?.tgl_kirim || "",
    tgl_bayar: initial?.tgl_bayar || "",
    status: initial?.status || "OPEN",
    keterangan: initial?.keterangan || "",
  });
  const [saving, setSaving] = useState(false);
  const [fpAttachment, setFpAttachment] = useState(
    initial?.faktur_pajak_attachment || null,
  );
  const [uploadingFp, setUploadingFp] = useState(false);
  const [bpAttachment, setBpAttachment] = useState(
    initial?.bukti_potong_attachment || null,
  );
  const [uploadingBp, setUploadingBp] = useState(false);

  // Load customers whenever the jenis pekerjaan changes.
  // If no jenis is picked yet, we clear the customer list to force the user
  // to pick jenis first (Step 1 → Step 2 flow). When a jenis is picked, only
  // pelanggan with at least one billable WO for that jenis are returned.
  useEffect(() => {
    if (!jenisPekerjaan) {
      setAllCustomers([]);
      setCustomerDiag(null);
      return;
    }
    (async () => {
      try {
        const { data } = await api.get("/invoices/customers", {
          params: {
            jenis_pekerjaan: jenisPekerjaan,
            ...(isEdit && initial?.id ? { exclude_invoice_id: initial.id } : {}),
          },
        });
        // The filtered endpoint returns { items, diagnostic }. Legacy plain array
        // is still supported as a fallback.
        const items = Array.isArray(data) ? data : data.items || [];
        const diag = Array.isArray(data) ? null : data.diagnostic || null;
        setAllCustomers(items);
        setCustomerDiag(diag);
        const validNames = new Set(items.map((c) => c.pelanggan));
        setSelectedPelanggans((prev) => prev.filter((p) => validNames.has(p)));
      } catch (e) {
        toast.error(formatApiError(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jenisPekerjaan]);

  // Load candidates whenever jenis + selected pelanggans change
  useEffect(() => {
    if (!jenisPekerjaan || selectedPelanggans.length === 0) {
      setCandidates([]);
      setSelected(new Set());
      return;
    }
    (async () => {
      setLoadingCand(true);
      try {
        const { data } = await api.get("/invoices/candidates", {
          params: {
            jenis_pekerjaan: jenisPekerjaan,
            pelanggans: selectedPelanggans.join(","),
            ...(isEdit && initial?.id ? { exclude_invoice_id: initial.id } : {}),
          },
        });
        setCandidates(data);
        // Auto-include ALL matching WOs — no manual picking
        setSelected(new Set(data.map((c) => c.id)));
      } catch (e) {
        toast.error(formatApiError(e));
      } finally {
        setLoadingCand(false);
      }
    })();
  }, [jenisPekerjaan, selectedPelanggans]);

  // Group candidates by pelanggan for the summary card
  const grouped = useMemo(() => {
    const map = new Map();
    selectedPelanggans.forEach((p) => map.set(p, []));
    candidates.forEach((c) => {
      const key = c.pelanggan || "-";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(c);
    });
    return Array.from(map.entries()); // [ [pelanggan, wos[]], ...]
  }, [candidates, selectedPelanggans]);

  const perPelangganTotals = useMemo(() => {
    return grouped.map(([pel, wos]) => {
      let jasa = 0;
      let material = 0;
      wos.forEach((c) => {
        jasa += Number(c.boq_jasa) || 0;
        material += Number(c.boq_material) || 0;
      });
      return { pelanggan: pel, wo_count: wos.length, jasa, material, subtotal: jasa + material };
    });
  }, [grouped]);

  const totals = perPelangganTotals.reduce(
    (acc, t) => {
      acc.jasa += t.jasa;
      acc.material += t.material;
      acc.grand += t.subtotal;
      return acc;
    },
    { jasa: 0, material: 0, grand: 0 }
  );

  const addPelanggan = (p) => {
    if (selectedPelanggans.includes(p)) {
      toast.info("Pelanggan sudah dipilih");
      return;
    }
    setSelectedPelanggans([...selectedPelanggans, p]);
    setAddingPelanggan(false);
    setCustomerSearch("");
  };

  const removePelanggan = (p) => {
    setSelectedPelanggans(selectedPelanggans.filter((x) => x !== p));
  };

  const availableCustomers = useMemo(() => {
    const s = customerSearch.toLowerCase();
    return allCustomers
      .filter((c) => !selectedPelanggans.includes(c.pelanggan))
      .filter((c) => !s || c.pelanggan.toLowerCase().includes(s));
  }, [allCustomers, selectedPelanggans, customerSearch]);

  const autoInvNo = null; // deprecated: backend auto-generates INV/NN/RomanMonth/YYYY on create.

  const uploadFakturPajak = async (file) => {
    if (!isEdit || !initial?.id) {
      toast.error("Simpan invoice terlebih dahulu sebelum upload faktur pajak");
      return;
    }
    if (!file) return;
    const isPdf = file.type === "application/pdf" || (file.name || "").toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      toast.error("Hanya file PDF yang diperbolehkan");
      return;
    }
    setUploadingFp(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(
        `/invoices/${initial.id}/faktur-pajak`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setFpAttachment(data.faktur_pajak_attachment || null);
      toast.success("Faktur pajak berhasil diupload — akan otomatis jadi lampiran invoice");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setUploadingFp(false);
    }
  };

  const deleteFakturPajak = async () => {
    if (!isEdit || !initial?.id) return;
    if (!window.confirm("Hapus file faktur pajak yang tersimpan?")) return;
    try {
      await api.delete(`/invoices/${initial.id}/faktur-pajak`);
      setFpAttachment(null);
      toast.success("Faktur pajak dihapus");
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const previewFakturPajak = () => {
    if (!isEdit || !initial?.id) return;
    const token = localStorage.getItem("la_token") || "";
    const base = (api.defaults && api.defaults.baseURL) || "";
    const url = `${base}/invoices/${initial.id}/faktur-pajak/download?auth=${encodeURIComponent(token)}`;
    window.open(url, "_blank");
  };

  const uploadBuktiPotong = async (file) => {
    if (!isEdit || !initial?.id) {
      toast.error("Simpan invoice terlebih dahulu sebelum upload bukti potong");
      return;
    }
    if (!file) return;
    const isPdf = file.type === "application/pdf" || (file.name || "").toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      toast.error("Hanya file PDF yang diperbolehkan");
      return;
    }
    setUploadingBp(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(
        `/invoices/${initial.id}/bukti-potong`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setBpAttachment(data.bukti_potong_attachment || null);
      toast.success("Bukti potong berhasil diupload — akan otomatis jadi lampiran invoice");
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setUploadingBp(false);
    }
  };

  const deleteBuktiPotong = async () => {
    if (!isEdit || !initial?.id) return;
    if (!window.confirm("Hapus file bukti potong yang tersimpan?")) return;
    try {
      await api.delete(`/invoices/${initial.id}/bukti-potong`);
      setBpAttachment(null);
      toast.success("Bukti potong dihapus");
    } catch (e) {
      toast.error(formatApiError(e));
    }
  };

  const previewBuktiPotong = () => {
    if (!isEdit || !initial?.id) return;
    const token = localStorage.getItem("la_token") || "";
    const base = (api.defaults && api.defaults.baseURL) || "";
    const url = `${base}/invoices/${initial.id}/bukti-potong/download?auth=${encodeURIComponent(token)}`;
    window.open(url, "_blank");
  };

  const submit = async () => {
    if (!jenisPekerjaan) return toast.error("Pilih jenis pekerjaan");
    if (selectedPelanggans.length === 0) return toast.error("Tambah minimal 1 pelanggan");
    if (selected.size === 0)
      return toast.error("Pilih minimal 1 work order untuk ditagihkan");
    if (!String(meta.invoice_no || "").trim())
      return toast.error("No Invoice wajib diisi");
    if (!totals.grand || totals.grand <= 0)
      return toast.error(
        "Nilai invoice tidak boleh 0 — pastikan WO yang dipilih memiliki nilai BoQ"
      );
    setSaving(true);
    try {
      const payload = {
        pelanggans: selectedPelanggans,
        jenis_pekerjaan: jenisPekerjaan,
        invoice_no: meta.invoice_no,
        inv_no_eproc: meta.inv_no_eproc,
        tanggal: meta.tanggal,
        tgl_kirim: meta.tgl_kirim,
        tgl_bayar: meta.tgl_bayar,
        status: meta.status,
        keterangan: meta.keterangan,
        work_order_ids: Array.from(selected),
      };
      if (isEdit) {
        await api.put(`/invoices/${initial.id}`, payload);
        toast.success("Invoice diperbarui");
      } else {
        await api.post("/invoices", payload);
        toast.success("Invoice dibuat");
      }
      onSaved();
    } catch (e) {
      toast.error(formatApiError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      data-testid="invoice-form-modal"
      className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto"
    >
      <div className="bg-white border border-border rounded-sm shadow-xl max-w-5xl w-full my-8">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
              {isEdit ? "Edit Invoice" : "Buat Invoice"}
            </div>
            <div className="font-display text-2xl font-bold tracking-tight mt-0.5">
              Invoice
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-muted-foreground hover:text-foreground"
            data-testid="invoice-form-close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Step 1: Jenis Pekerjaan (FIRST) */}
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
              1 &middot; Jenis Pekerjaan
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
              {INVOICE_CATEGORIES.map((cat) => {
                const on = jenisPekerjaan === cat.value;
                return (
                  <button
                    key={cat.value}
                    type="button"
                    data-testid={`invoice-jenis-${cat.value}`}
                    onClick={() => {
                      setJenisPekerjaan(cat.value);
                      setSelected(new Set());
                    }}
                    className={`text-left px-3 py-3 rounded-sm border transition-colors ${
                      on
                        ? "bg-blue-50 border-blue-500 ring-1 ring-blue-500"
                        : "bg-white border-border hover:border-blue-400"
                    }`}
                  >
                    <div
                      className={`mono text-xs uppercase tracking-[0.15em] font-semibold ${
                        on ? "text-blue-700" : "text-foreground"
                      }`}
                    >
                      {cat.title}
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-1 leading-relaxed">
                      {cat.hint}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 2: Pelanggan (multi, after jenis is picked) */}
          {jenisPekerjaan && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  2 &middot; Pelanggan ({selectedPelanggans.length} dipilih)
                </div>
                {!addingPelanggan && (
                  <button
                    type="button"
                    data-testid="invoice-add-pelanggan-btn"
                    onClick={() => {
                      if (!jenisPekerjaan) {
                        toast.error("Pilih jenis pekerjaan terlebih dahulu");
                        return;
                      }
                      setAddingPelanggan(true);
                    }}
                    disabled={!jenisPekerjaan}
                    className={`inline-flex items-center gap-1.5 text-white text-xs font-medium px-3 py-1.5 rounded-sm transition-colors ${
                      jenisPekerjaan
                        ? "bg-blue-600 hover:bg-blue-700"
                        : "bg-slate-300 cursor-not-allowed"
                    }`}
                    title={
                      jenisPekerjaan
                        ? "Tambah pelanggan"
                        : "Pilih jenis pekerjaan dulu"
                    }
                  >
                    <Plus size={12} weight="bold" /> Tambah Pelanggan
                  </button>
                )}
              </div>

              {/* Selected chips */}
              {selectedPelanggans.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {selectedPelanggans.map((p) => (
                    <span
                      key={p}
                      data-testid={`invoice-pelanggan-chip-${p}`}
                      className="inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-700 rounded-sm pl-3 pr-1 py-1 text-xs"
                    >
                      <span className="truncate max-w-xs">{p}</span>
                      <button
                        type="button"
                        onClick={() => removePelanggan(p)}
                        className="p-0.5 hover:bg-blue-200 rounded-sm"
                        title="Hapus pelanggan"
                      >
                        <X size={10} weight="bold" />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Picker (when adding) */}
              {addingPelanggan && (
                <div className="border border-blue-200 bg-blue-50/60 rounded-sm p-3 mt-1">
                  <div className="flex items-center gap-2 mb-2">
                    <MagnifyingGlass size={14} className="text-muted-foreground" />
                    <input
                      data-testid="invoice-pelanggan-search"
                      autoFocus
                      value={customerSearch}
                      onChange={(e) => setCustomerSearch(e.target.value)}
                      placeholder="Cari pelanggan…"
                      className="flex-1 bg-white border border-border rounded-sm px-2 py-1 text-sm outline-none"
                    />
                    <button
                      onClick={() => {
                        setAddingPelanggan(false);
                        setCustomerSearch("");
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground px-2"
                    >
                      Batal
                    </button>
                  </div>
                  <div className="max-h-60 overflow-y-auto border border-border rounded-sm bg-white">
                    {availableCustomers.length === 0 ? (
                      <div className="p-3 text-sm text-muted-foreground text-center space-y-1.5">
                        <div>
                          Tidak ada pelanggan yang memiliki WO {jenisPekerjaan} berstatus{" "}
                          <b>OK / BATAL</b>.
                        </div>
                        {customerDiag &&
                          (customerDiag.missing_pelanggan > 0 ||
                            customerDiag.not_ready_status > 0 ||
                            customerDiag.already_billed > 0) && (
                            <div
                              data-testid="invoice-customer-diagnostic"
                              className="text-[11px] mono text-amber-700 bg-amber-50 border border-amber-200 rounded-sm p-2 mx-4 mt-2 text-left"
                            >
                              <div className="mb-1 uppercase tracking-widest text-[10px]">
                                Diagnostik
                              </div>
                              {customerDiag.missing_pelanggan > 0 && (
                                <div>
                                  &bull; {customerDiag.missing_pelanggan} WO cocok jenis
                                  ini tapi <b>Nama Pelanggan kosong</b> — buka WO-nya
                                  &amp; isi nama pelanggan.
                                </div>
                              )}
                              {customerDiag.not_ready_status > 0 && (
                                <div>
                                  &bull; {customerDiag.not_ready_status} WO cocok jenis
                                  ini tapi <b>status hasil pekerjaan belum OK/BATAL</b>{" "}
                                  — buka WO-nya &amp; set status di section Hasil
                                  Pekerjaan.
                                </div>
                              )}
                              {customerDiag.already_billed > 0 && (
                                <div>
                                  &bull; {customerDiag.already_billed} WO sudah{" "}
                                  <b>dibuatkan invoice sebelumnya</b> — tidak bisa
                                  ditagih ulang. Cek di daftar invoice.
                                </div>
                              )}
                            </div>
                          )}
                      </div>
                    ) : (
                      availableCustomers.map((c) => (
                        <button
                          key={c.pelanggan}
                          type="button"
                          data-testid={`invoice-add-pelanggan-opt-${c.pelanggan}`}
                          onClick={() => addPelanggan(c.pelanggan)}
                          className="w-full text-left px-3 py-2 border-b border-border/60 last:border-0 hover:bg-blue-50 transition-colors flex items-center justify-between"
                        >
                          <span className="text-sm truncate">{c.pelanggan}</span>
                          <span className="text-[10px] mono text-muted-foreground shrink-0 ml-2">
                            {c.wo_count} WO
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Summary per pelanggan */}
          {jenisPekerjaan && selectedPelanggans.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
                3 &middot; Ringkasan per Pelanggan
              </div>
              {loadingCand ? (
                <div className="p-3 text-sm text-muted-foreground">Loading…</div>
              ) : (
                <div className="border border-border rounded-sm overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-border">
                      <tr className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                        <th className="text-left px-3 py-2">Pelanggan</th>
                        <th className="text-right px-3 py-2 w-24">Jumlah WO</th>
                        <th className="text-right px-3 py-2 w-36">Total Jasa</th>
                        <th className="text-right px-3 py-2 w-36">Total Material</th>
                        <th className="text-right px-3 py-2 w-40">Subtotal</th>
                        <th className="w-10 px-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {perPelangganTotals.map((t) => (
                        <tr
                          key={t.pelanggan}
                          data-testid={`invoice-summary-row-${t.pelanggan}`}
                          className="border-b border-border last:border-0"
                        >
                          <td className="px-3 py-2">
                            <div className="text-sm font-medium truncate max-w-md">
                              {t.pelanggan}
                            </div>
                            {t.wo_count === 0 && (
                              <div className="text-[10px] text-amber-600 mt-0.5">
                                Tidak ada WO {jenisPekerjaan} untuk pelanggan ini
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right mono">{t.wo_count}</td>
                          <td className="px-3 py-2 text-right mono text-xs">
                            {formatIDR(t.jasa)}
                          </td>
                          <td className="px-3 py-2 text-right mono text-xs">
                            {formatIDR(t.material)}
                          </td>
                          <td className="px-3 py-2 text-right mono font-semibold">
                            {formatIDR(t.subtotal)}
                          </td>
                          <td className="px-2 py-2 text-center">
                            <button
                              type="button"
                              onClick={() => removePelanggan(t.pelanggan)}
                              className="p-1 rounded-sm text-red-500 hover:text-red-600 hover:bg-red-50"
                              title="Hapus pelanggan dari invoice"
                            >
                              <Trash size={14} weight="bold" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {/* Grand total footer */}
                  {selected.size > 0 && (
                    <div className="bg-slate-50 border-t border-border px-3 py-3">
                      <div className="max-w-md ml-auto space-y-1.5 text-sm mono">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground uppercase text-[11px] tracking-[0.15em]">
                            Total Jasa
                          </span>
                          <span>{formatIDR(totals.jasa)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground uppercase text-[11px] tracking-[0.15em]">
                            Total Material
                          </span>
                          <span>{formatIDR(totals.material)}</span>
                        </div>
                        <div className="flex items-center justify-between pt-1.5 border-t border-border">
                          <span className="text-foreground uppercase text-xs tracking-[0.15em] font-semibold">
                            Grand Total ({selected.size} WO &middot;{" "}
                            {perPelangganTotals.filter((t) => t.wo_count > 0).length} pelanggan)
                          </span>
                          <span
                            data-testid="invoice-form-grand-total"
                            className="text-blue-600 text-lg font-bold"
                          >
                            {formatIDR(totals.grand)}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 4: Metadata */}
          {jenisPekerjaan && selectedPelanggans.length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1.5">
                4 &middot; Detail Invoice
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    No Invoice <span className="text-red-600">*</span>
                  </label>
                  <input
                    data-testid="invoice-form-no"
                    value={meta.invoice_no}
                    onChange={(e) => setMeta({ ...meta, invoice_no: e.target.value.toUpperCase() })}
                    placeholder="ISI MANUAL, MIS. INV/01/I/2026"
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    No Invoice EPROC
                  </label>
                  <input
                    data-testid="invoice-form-no-eproc"
                    value={meta.inv_no_eproc}
                    onChange={(e) =>
                      setMeta({ ...meta, inv_no_eproc: e.target.value.toUpperCase() })
                    }
                    placeholder="NO. INVOICE DI SISTEM EPROC (OPSIONAL)"
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm mono"
                  />
                </div>
                <div className="md:col-span-2 border border-dashed border-border rounded-sm p-3 bg-slate-50">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                    Faktur Pajak (lampiran invoice)
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                      File Faktur Pajak (PDF)
                    </label>
                    {!isEdit && (
                      <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-2 py-1.5">
                        Simpan invoice dulu, kemudian buka Edit untuk upload file.
                      </div>
                    )}
                    {isEdit && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <label className="inline-flex items-center gap-1.5 border border-border bg-white hover:bg-slate-100 rounded-sm px-3 py-1.5 text-sm cursor-pointer">
                          {uploadingFp ? "Mengupload…" : (fpAttachment ? "Ganti file" : "Pilih file")}
                          <input
                            type="file"
                            accept="application/pdf,.pdf"
                            className="hidden"
                            disabled={uploadingFp}
                            data-testid="invoice-form-faktur-pajak-file"
                            onChange={(e) => {
                              const f = e.target.files && e.target.files[0];
                              if (f) uploadFakturPajak(f);
                              e.target.value = "";
                            }}
                          />
                        </label>
                        {fpAttachment ? (
                          <>
                            <button
                              type="button"
                              onClick={previewFakturPajak}
                              className="text-sm text-blue-600 hover:underline"
                            >
                              Lihat: {fpAttachment.original_filename || "faktur_pajak"}
                            </button>
                            <button
                              type="button"
                              onClick={deleteFakturPajak}
                              className="text-sm text-red-600 hover:underline"
                            >
                              Hapus
                            </button>
                          </>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">
                            Belum ada file. Setelah upload, otomatis jadi lampiran PDF invoice.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="md:col-span-2 border border-dashed border-border rounded-sm p-3 bg-slate-50">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-2">
                    Bukti Potong (lampiran invoice)
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                      File Bukti Potong (PDF)
                    </label>
                    {!isEdit && (
                      <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-sm px-2 py-1.5">
                        Simpan invoice dulu, kemudian buka Edit untuk upload file.
                      </div>
                    )}
                    {isEdit && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <label className="inline-flex items-center gap-1.5 border border-border bg-white hover:bg-slate-100 rounded-sm px-3 py-1.5 text-sm cursor-pointer">
                          {uploadingBp ? "Mengupload…" : (bpAttachment ? "Ganti file" : "Pilih file")}
                          <input
                            type="file"
                            accept="application/pdf,.pdf"
                            className="hidden"
                            disabled={uploadingBp}
                            data-testid="invoice-form-bukti-potong-file"
                            onChange={(e) => {
                              const f = e.target.files && e.target.files[0];
                              if (f) uploadBuktiPotong(f);
                              e.target.value = "";
                            }}
                          />
                        </label>
                        {bpAttachment ? (
                          <>
                            <button
                              type="button"
                              onClick={previewBuktiPotong}
                              className="text-sm text-blue-600 hover:underline"
                            >
                              Lihat: {bpAttachment.original_filename || "bukti_potong"}
                            </button>
                            <button
                              type="button"
                              onClick={deleteBuktiPotong}
                              className="text-sm text-red-600 hover:underline"
                            >
                              Hapus
                            </button>
                          </>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">
                            Belum ada file. Setelah upload, otomatis jadi lampiran PDF invoice.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Status
                  </label>
                  <select
                    data-testid="invoice-form-status"
                    value={meta.status}
                    onChange={(e) => setMeta({ ...meta, status: e.target.value })}
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Tanggal Invoice
                  </label>
                  <input
                    type="date"
                    data-testid="invoice-form-tanggal"
                    value={meta.tanggal}
                    onChange={(e) => setMeta({ ...meta, tanggal: e.target.value })}
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Tanggal Kirim
                  </label>
                  <input
                    type="date"
                    value={meta.tgl_kirim}
                    onChange={(e) => setMeta({ ...meta, tgl_kirim: e.target.value })}
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Tanggal Bayar
                  </label>
                  <input
                    type="date"
                    value={meta.tgl_bayar}
                    onChange={(e) => setMeta({ ...meta, tgl_bayar: e.target.value })}
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-[10px] uppercase tracking-[0.2em] text-muted-foreground mb-1">
                    Keterangan
                  </label>
                  <textarea
                    rows="2"
                    value={meta.keterangan}
                    onChange={(e) => setMeta({ ...meta, keterangan: e.target.value.toUpperCase() })}
                    className="w-full border border-border bg-white rounded-sm px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border flex items-center justify-end gap-2 bg-slate-50">
          <button
            onClick={onClose}
            className="border border-border bg-white hover:bg-slate-100 rounded-sm px-4 py-2 text-sm"
          >
            Batal
          </button>
          <button
            data-testid="invoice-form-save"
            onClick={submit}
            disabled={
              saving ||
              !jenisPekerjaan ||
              selectedPelanggans.length === 0 ||
              selected.size === 0
            }
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 disabled:cursor-not-allowed text-white text-sm font-medium px-4 py-2 rounded-sm transition-colors"
          >
            {saving ? "Menyimpan…" : isEdit ? "Perbarui Invoice" : "Simpan Invoice"}
          </button>
        </div>
      </div>
    </div>
  );
}
