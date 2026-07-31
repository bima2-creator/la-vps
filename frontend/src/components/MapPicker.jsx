import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapPin, X, ArrowRight } from "@phosphor-icons/react";

// Fix Leaflet's default icon path breakage under Webpack/CRA.
const defaultIcon = L.icon({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = defaultIcon;

// Default center: Jakarta.
const DEFAULT_CENTER = [-6.2088, 106.8456];

// -------- DMS helpers --------
function pad(n, w = 2) {
  return String(n).padStart(w, "0");
}

export function toDMS(deg, isLat) {
  if (deg === null || deg === undefined || isNaN(deg)) return "";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = ((mFloat - m) * 60).toFixed(2);
  const hemi = isLat ? (deg >= 0 ? "N" : "S") : (deg >= 0 ? "E" : "W");
  return `${d}°${pad(m)}'${pad(s, 5)}"${hemi}`;
}

/** Parse a lat/lng string (decimal OR DMS "6°12'31.68\"S") back to a decimal number.
 *  Returns null if unparseable. */
export function parseCoord(str) {
  if (str === null || str === undefined) return null;
  const s = String(str).trim();
  if (!s) return null;
  // Plain decimal?
  const dec = Number(s);
  if (!isNaN(dec) && /^-?\d+(\.\d+)?$/.test(s)) return dec;
  const m = s.match(
    /(-?\d+(?:\.\d+)?)\s*[°º]\s*(\d+(?:\.\d+)?)\s*['′]\s*(\d+(?:\.\d+)?)\s*["″]?\s*([NSEW]?)/i
  );
  if (!m) return null;
  const d = parseFloat(m[1]);
  const mm = parseFloat(m[2]);
  const ss = parseFloat(m[3]);
  const h = (m[4] || "").toUpperCase();
  const val = Math.abs(d) + mm / 60 + ss / 3600;
  return h === "S" || h === "W" || d < 0 ? -val : val;
}

function ClickHandler({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function Recenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

export default function MapPicker({ open, initialLat, initialLng, onClose, onApply }) {
  // Parse whatever the form currently holds (may already be DMS from a previous save).
  const parsedLat = parseCoord(initialLat);
  const parsedLng = parseCoord(initialLng);
  const startCenter = useMemo(() => {
    if (parsedLat !== null && parsedLng !== null && !isNaN(parsedLat) && !isNaN(parsedLng)) {
      return [parsedLat, parsedLng];
    }
    return DEFAULT_CENTER;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const [pos, setPos] = useState(startCenter);

  // Reset marker + center whenever the modal opens.
  useEffect(() => {
    if (open) setPos(startCenter);
  }, [open, startCenter]);

  if (!open) return null;

  const dmsLat = toDMS(pos[0], true);
  const dmsLng = toDMS(pos[1], false);

  const handleSearch = async (query) => {
    if (!query.trim()) return;
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
        query
      )}&format=json&limit=1`;
      const resp = await fetch(url);
      const data = await resp.json();
      if (data && data.length > 0) {
        setPos([parseFloat(data[0].lat), parseFloat(data[0].lon)]);
      }
    } catch (e) {
      // Silent – Nominatim rate limits sometimes.
    }
  };

  return (
    <div
      data-testid="map-picker-overlay"
      className="fixed inset-0 z-[70] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl bg-white rounded-sm border border-border shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        data-testid="map-picker-modal"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-slate-50">
          <div className="flex items-center gap-2">
            <MapPin size={18} weight="duotone" className="text-blue-600" />
            <div>
              <div className="font-display font-bold tracking-tight text-lg leading-none">
                Pilih Titik Lokasi
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Klik pada peta atau geser pin biru untuk menetapkan koordinat.
              </div>
            </div>
          </div>
          <button
            data-testid="map-picker-close"
            onClick={onClose}
            className="p-2 hover:bg-slate-200 rounded-sm"
          >
            <X size={16} />
          </button>
        </div>

        {/* Search bar */}
        <div className="px-5 py-2 border-b border-border bg-white">
          <input
            data-testid="map-picker-search"
            type="text"
            placeholder="Cari alamat / kota (mis. Menara BCA Jakarta) lalu tekan Enter"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSearch(e.target.value);
              }
            }}
            className="w-full bg-secondary border border-border rounded-sm px-3 py-2 text-sm"
          />
        </div>

        {/* Map */}
        <div className="h-[480px] w-full">
          <MapContainer
            center={pos}
            zoom={13}
            style={{ height: "100%", width: "100%" }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Recenter center={pos} />
            <ClickHandler onPick={(la, ln) => setPos([la, ln])} />
            <Marker
              position={pos}
              draggable
              eventHandlers={{
                dragend: (e) => {
                  const ll = e.target.getLatLng();
                  setPos([ll.lat, ll.lng]);
                },
              }}
            />
          </MapContainer>
        </div>

        {/* Footer with coordinates */}
        <div className="px-5 py-3 border-t border-border bg-slate-50 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex gap-4 flex-wrap">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mono">
                Lat (DMS)
              </div>
              <div data-testid="map-picker-lat" className="mono text-sm font-semibold">
                {dmsLat}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mono">
                Lng (DMS)
              </div>
              <div data-testid="map-picker-lng" className="mono text-sm font-semibold">
                {dmsLng}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground mono">
                Decimal
              </div>
              <div className="mono text-[11px] text-muted-foreground">
                {pos[0].toFixed(6)}, {pos[1].toFixed(6)}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
            >
              Batal
            </button>
            <button
              data-testid="map-picker-apply"
              onClick={() => onApply(dmsLat, dmsLng)}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-sm"
            >
              Terapkan <ArrowRight size={14} weight="bold" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
