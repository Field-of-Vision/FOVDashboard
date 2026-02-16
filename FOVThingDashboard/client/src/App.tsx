// src/App.tsx
import React, { useState } from "react";
import LoginPage from "./Pages/Login";
import Dashboard from "./Pages/Dashboard";

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));

  const handleLogin = (t: string) => {
    localStorage.setItem("token", t);
    setToken(t);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("stadium");
    setToken(null);
  };

  if (!token) return <LoginPage onLogin={handleLogin} />;

  return (
    <>
      <Dashboard token={token} onUnauthorized={handleLogout} />
      {/* Floating Logout button (Tailwind) */}
      <button
        onClick={handleLogout}
        aria-label="Logout"
        title="Logout"
        className="fixed bottom-4 left-4 z-[999] px-4 py-2 rounded-xl border border-blue-200 shadow-md bg-white text-blue-700 font-semibold hover:bg-blue-50 transition-colors"
      >
        Logout
      </button>
    </>
  );
}
