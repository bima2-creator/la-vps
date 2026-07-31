import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

// Idle timeout: kalau user tidak ada aktivitas selama IDLE_TIMEOUT_MS,
// tampilkan modal peringatan dengan hitung mundur WARN_COUNTDOWN_SEC.
// Kalau tidak diklik "Lanjut", auto-logout + redirect ke /login.
const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 menit
const WARN_COUNTDOWN_SEC = 60; // 60 detik peringatan sebelum keluar
const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "wheel",
  "touchstart",
  "scroll",
];

export default function IdleTimeoutManager() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const lastActivityRef = useRef(Date.now());
  const [warning, setWarning] = useState(false);
  const [countdown, setCountdown] = useState(WARN_COUNTDOWN_SEC);

  const doLogout = useCallback(async () => {
    setWarning(false);
    try {
      await logout();
    } catch {
      /* ignore */
    }
    toast.info("Sesi berakhir karena tidak ada aktivitas. Silakan login kembali.");
    navigate("/login", { replace: true });
  }, [logout, navigate]);

  const continueSession = useCallback(() => {
    lastActivityRef.current = Date.now();
    setWarning(false);
    setCountdown(WARN_COUNTDOWN_SEC);
  }, []);

  // Only run when authenticated
  const active = !!(user && user.email);

  useEffect(() => {
    if (!active) return undefined;
    let throttleTimer = null;
    const bump = () => {
      // Throttle to once per 500 ms
      if (throttleTimer) return;
      throttleTimer = setTimeout(() => {
        throttleTimer = null;
      }, 500);
      // Only bump when warning is NOT showing — during warning the user
      // must explicitly click "Lanjut".
      setWarning((w) => {
        if (!w) lastActivityRef.current = Date.now();
        return w;
      });
    };
    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, bump, { passive: true }));
    return () => {
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, bump));
      if (throttleTimer) clearTimeout(throttleTimer);
    };
  }, [active]);

  useEffect(() => {
    if (!active) return undefined;
    const tick = setInterval(() => {
      const idleMs = Date.now() - lastActivityRef.current;
      if (!warning && idleMs >= IDLE_TIMEOUT_MS) {
        setWarning(true);
        setCountdown(WARN_COUNTDOWN_SEC);
      } else if (warning) {
        setCountdown((c) => {
          if (c <= 1) {
            doLogout();
            return 0;
          }
          return c - 1;
        });
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [active, warning, doLogout]);

  if (!active || !warning) return null;

  return (
    <div
      data-testid="idle-warning-modal"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
    >
      <div className="bg-white border border-border rounded-md shadow-xl max-w-sm w-full p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-lg font-semibold">
            !
          </div>
          <div>
            <div className="font-semibold text-slate-900">Sesi akan berakhir</div>
            <div className="text-[12px] text-muted-foreground">
              Tidak ada aktivitas selama 30 menit
            </div>
          </div>
        </div>
        <div className="text-sm text-slate-700 mb-4">
          Sesi kamu akan otomatis keluar dalam{" "}
          <span className="font-bold text-red-600" data-testid="idle-warning-countdown">
            {countdown}
          </span>{" "}
          detik. Klik <b>Lanjut</b> untuk tetap login.
        </div>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={doLogout}
            className="px-3 py-1.5 text-sm border border-border rounded-sm hover:bg-slate-100"
            data-testid="idle-warning-logout"
          >
            Logout
          </button>
          <button
            type="button"
            onClick={continueSession}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-sm hover:bg-blue-700 font-medium"
            data-testid="idle-warning-continue"
          >
            Lanjut
          </button>
        </div>
      </div>
    </div>
  );
}
