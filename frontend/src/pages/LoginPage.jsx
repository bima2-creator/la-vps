import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { LOGIN } from "@/constants/testIds";
import { formatApiError } from "@/lib/api";
import { Broadcast } from "@phosphor-icons/react";

const USER_OPTIONS = [
  { value: "admin", label: "Admin" },
  { value: "operator", label: "Operator" },
  { value: "guest", label: "Guest" },
];

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const pw = username === "guest" ? "guest" : password;
      await login(username, pw);
      const to = loc.state?.from?.pathname || "/dashboard";
      nav(to, { replace: true });
    } catch (e) {
      setErr(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative grid lg:grid-cols-[1.1fr_1fr] bg-background text-foreground">
      {/* left decorative panel */}
      <div className="hidden lg:flex relative overflow-hidden border-r border-border">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1644088379091-d574269d422f?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600')",
          }}
        />
        <div className="absolute inset-0 bg-black/75" />
        <div className="absolute inset-0 grid-bg opacity-40" />
        <div className="relative z-10 p-12 flex flex-col justify-between w-full">
          <div className="flex items-center gap-3">
            <Broadcast size={28} weight="duotone" className="text-blue-400" />
            <div className="font-display font-black text-2xl tracking-tighter text-white">LA TRACKER</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.25em] text-blue-300/80 mb-3">
              Portal Project Management and Delivery
            </div>
            <h1 className="font-display text-5xl font-black tracking-tighter leading-[1]">
              Every Delivery Work Order
              <br />
              <span className="text-blue-400">One command center.</span>
            </h1>
            <p className="mt-6 text-sm text-slate-300 max-w-md">
              Entry, pengolahan, dan penyajian data telekomunikasi dalam satu dashboard
              yang cepat &amp; tepat.
            </p>
          </div>
          <div className="mono text-[11px] text-slate-500">
            v1.0 · secured with JWT · {new Date().getFullYear()}
          </div>
        </div>
      </div>

      {/* right form */}
      <div className="flex items-center justify-center px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="text-[11px] uppercase tracking-[0.25em] text-muted-foreground">
            Sign in
          </div>
          <h2 className="mt-2 font-display text-3xl font-black tracking-tighter">
            Welcome back.
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Use your operator credentials to continue.
          </p>

          <div className="mt-8 space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                Role
              </label>
              <div
                data-testid={LOGIN.emailInput}
                role="radiogroup"
                aria-label="Role"
                className="mt-2 grid grid-cols-3 gap-2"
              >
                {USER_OPTIONS.map((opt) => {
                  const active = username === opt.value;
                  return (
                    <label
                      key={opt.value}
                      data-testid={`login-user-${opt.value}`}
                      className={`cursor-pointer select-none rounded-lg border px-3 py-3 text-center transition-all ${
                        active
                          ? "border-blue-500 bg-blue-500/10 ring-1 ring-blue-500"
                          : "border-border bg-secondary hover:border-blue-400/60"
                      }`}
                    >
                      <input
                        type="radio"
                        name="username"
                        value={opt.value}
                        checked={active}
                        onChange={(e) => setUsername(e.target.value)}
                        className="sr-only"
                      />
                      <div className="text-sm font-semibold">{opt.label}</div>
                    </label>
                  );
                })}
              </div>
            </div>
            {username !== "guest" && (
              <div>
                <label className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
                  Password
                </label>
                <input
                  data-testid={LOGIN.passwordInput}
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full bg-secondary border border-border rounded-sm px-3 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 mono transition-colors"
                  placeholder="••••••••"
                />
              </div>
            )}
            {username === "guest" && (
              <p className="text-xs text-muted-foreground">
                Guest tidak memerlukan password — klik Sign in untuk masuk sebagai Viewer.
              </p>
            )}
          </div>

          {err && (
            <div className="mt-4 text-sm text-red-400 border border-red-500/30 bg-red-500/10 px-3 py-2 rounded-sm">
              {err}
            </div>
          )}

          <button
            data-testid={LOGIN.submitButton}
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-sm bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium py-2.5 transition-colors disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in →"}
          </button>
        </form>
      </div>
    </div>
  );
}
