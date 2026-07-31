// Formatting helpers used across pages, forms, exports.
export function formatIDR(n) {
  const v = Number(n) || 0;
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(v);
}

// Compact "Rp 12,3 jt" style — used for tight KPI cards
export function formatIDRCompact(n) {
  const v = Number(n) || 0;
  if (v >= 1_000_000_000) return `Rp ${(v / 1_000_000_000).toFixed(1)} M`;
  if (v >= 1_000_000) return `Rp ${(v / 1_000_000).toFixed(1)} jt`;
  if (v >= 1_000) return `Rp ${(v / 1_000).toFixed(0)} rb`;
  return formatIDR(v);
}

// Number-only formatter (no currency prefix) for table cells
export function formatNumber(n) {
  const v = Number(n) || 0;
  return new Intl.NumberFormat("id-ID").format(v);
}
