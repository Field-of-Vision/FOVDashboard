// src/config.ts
export const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE ??
  (process.env.REACT_APP_API_BASE as string | undefined) ??
  "http://localhost:8000";

export const WS_BASE =
  (import.meta as any)?.env?.VITE_WS_BASE ??
  (process.env.REACT_APP_WS_BASE as string | undefined) ??
  (window.location.protocol === "https:" ? "wss://localhost:8000" : "ws://localhost:8000");
