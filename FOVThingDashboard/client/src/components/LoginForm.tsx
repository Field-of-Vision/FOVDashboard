// src/components/LoginForm.tsx
import React, { useState } from "react";
import { API_BASE } from "../config";

type LoginResponse = { token: string; role: "admin" | "stadium"; stadium?: string };
type Props = { onLogin: (token: string) => void };

export default function LoginForm({ onLogin }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || "Login failed");
      }
      const data = (await res.json()) as LoginResponse;
      localStorage.setItem("token", data.token);
      localStorage.setItem("role", data.role);
      if (data.stadium) localStorage.setItem("stadium", data.stadium);
      onLogin(data.token);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md bg-white border border-blue-100 rounded-2xl shadow-xl p-6 sm:p-8"
      >
        <h1 className="text-2xl font-semibold text-slate-900 mb-1">Login</h1>
        <p className="text-sm text-slate-500 mb-6">Sign in to your stadium dashboard</p>

        <label className="block text-sm font-medium text-slate-700">
          Stadium ID or “admin”
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. aviva, marvel, or admin"
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            autoFocus
          />
        </label>

        <label className="block text-sm font-medium text-slate-700 mt-4">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </label>

        {error && (
          <div className="mt-4 rounded-lg bg-red-50 text-red-700 text-sm px-3 py-2">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-blue-600 px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {loading ? "Signing in…" : "Login"}
        </button>
      </form>
  );
}
