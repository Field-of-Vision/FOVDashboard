// src/Dashboard.tsx
import React, { useEffect, useState, useRef } from 'react';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import DeviceComponent from '../components/DeviceComponent';
import ChampionRelay from '../components/ChampionRelay';
import '../index.css';
import { API_BASE, WS_BASE } from "../config";

type ReactText = string | number;

interface Device {
  name: string;
  wifiConnected: boolean;
  batteryCharge: number;
  temperature: number;
  firmwareVersion: string;
  otaUpdateStatus: string;
  lastMessageTime: string;
  firstSeen: string;
  latencyMs?: number;
  stadium?: string;
}

type Filter = "all" | "online" | "offline";

type Props = {
  token: string;
  onUnauthorized?: () => void;
};

// tiny JWT payload decoder
function parseJwt(token: string | null) {
  if (!token) return null;
  try {
    const base = token.split(".")[1];
    if (!base) return null;
    const padded = base.padEnd(base.length + (4 - (base.length % 4)) % 4, "=");
    const b64 = padded.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(b64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

const Dashboard: React.FC<Props> = ({ token, onUnauthorized }) => {
  const [devices, setDevices] = useState<Record<string, Device>>({});
  const [relays, setRelays] = useState<Record<string, any>>({});
  const [stadiumLabels, setStadiumLabels] = useState<Record<string, string>>({});
  const [connectionStatus, setConnectionStatus] = useState<string>('Connecting...');
  const [filter, setFilter] = useState<Filter>("all");

  // minimal state for search + sorting
  const [query, setQuery] = useState<string>("");
  const [sortAsc, setSortAsc] = useState<boolean>(true);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const offlineToastIds = useRef<Record<string, ReactText>>({});

  // header from JWT
  const claims = parseJwt(token);
  const isAdmin = claims?.sub_type === "admin";
  const stadiumSlug: string | null = isAdmin ? null : (claims?.sub ?? null);
  const stadiumName = stadiumSlug ? (stadiumLabels[stadiumSlug] ?? stadiumSlug) : "";

  const connectWebSocket = () => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = `${WS_BASE}/ws?token=${encodeURIComponent(token)}`;
    console.log('Connecting to WebSocket:', wsUrl);
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connection established');
      setConnectionStatus('Connected');
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
      setConnectionStatus('Error connecting');
      ws.current?.close();
    };

    ws.current.onmessage = (event) => {
      if (event.data === "ping") { ws.current?.send("pong"); return; }
      if (event.data === "pong") { return; }

      try {
        const data = JSON.parse(event.data);

        if (data.topic?.startsWith("relay:")) {
          const rid = data.topic.split(":")[1];
          setRelays(prev => ({ ...prev, [rid]: data.message }));
          return;
        }

        setDevices(prevDevices => {
          const prev = prevDevices[data.topic];
          const next = { ...prev, ...data.message };

          if (prev && prev.wifiConnected && !next.wifiConnected) {
            if (!offlineToastIds.current[next.name]) {
              const id = toast.error(`${next.name} went offline`, {
                autoClose: 300_000,
                closeOnClick: true,
                onClose: () => { delete offlineToastIds.current[next.name]; },
              });
              offlineToastIds.current[next.name] = id;
            }
          }

          if (prev && !prev.wifiConnected && next.wifiConnected) {
            const id = offlineToastIds.current[next.name];
            if (id) { toast.dismiss(id); delete offlineToastIds.current[next.name]; }
          }

          return { ...prevDevices, [data.topic]: next };
        });
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.current.onclose = () => {
      setConnectionStatus('Disconnected. Attempting to reconnect...');
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000);
    };
  };

  useEffect(() => {
    const loadInitial = async () => {
      try {
        const commonOpts: RequestInit = {
          headers: { Authorization: `Bearer ${token}` },
        };

        // stadium labels (public endpoint, no auth needed)
        try {
          const labelsRes = await fetch(`${API_BASE}/api/meta/stadiums`);
          if (labelsRes.ok) {
            const data = await labelsRes.json();
            const labels: Record<string, string> = {};
            for (const [slug, info] of Object.entries(data)) {
              labels[slug] = (info as any).name ?? slug;
            }
            setStadiumLabels(labels);
          }
        } catch {
          // non-critical, fall back to slug
        }

        // devices
        const devRes = await fetch(`${API_BASE}/api/devices`, commonOpts);
        if (devRes.status === 401 || devRes.status === 403) {
          onUnauthorized?.();
          return;
        }
        setDevices(await devRes.json());

        // relays
        const relRes = await fetch(`${API_BASE}/api/relays`, commonOpts);
        if (relRes.status === 401 || relRes.status === 403) {
          onUnauthorized?.();
          return;
        }
        setRelays(await relRes.json());
      } catch (e) {
        console.error('initial fetch failed', e);
      }
    };

    loadInitial();
    connectWebSocket();

    return () => {
      ws.current?.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [token]);

  // ----- filter + search + sort -----
  const queryLc = query.trim().toLowerCase();

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-800 p-4 space-y-6">
      {/* Stadium Pattern Overlay */}
      <div className="fixed inset-0 opacity-5 pointer-events-none">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 25% 25%, white 2px, transparent 2px),
                           radial-gradient(circle at 75% 75%, white 2px, transparent 2px)`,
          backgroundSize: '50px 50px'
        }}></div>
      </div>

      <div className="relative z-10">
        <ChampionRelay
          data={relays["championdata"]}
          wsConnected={connectionStatus === "Connected"}
        />

        {/* Enhanced Header */}
        <div className="text-center mb-8 mt-8">
          <div className="inline-flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
              <div className="w-4 h-4 border-2 border-white rounded-full"></div>
            </div>
            <h1 className="text-3xl font-bold text-white tracking-wide">
              {isAdmin ? "Admin Device Overview" : `${stadiumName} Control Hub`}
            </h1>
            <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
              <div className="w-4 h-4 border-2 border-white rounded-full"></div>
            </div>
          </div>
        </div>

        {/* Enhanced Control Panel */}
        {(() => {
          const deviceEntries = Object.entries(devices);
          const onlineCount = deviceEntries.filter(([_, d]) => d.wifiConnected).length;
          const offlineCount = deviceEntries.filter(([_, d]) => !d.wifiConnected).length;
          const allCount = deviceEntries.length;

          return (
            <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-6 shadow-xl border border-white/20" mx-8>
              {/* Controls Row */}
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                {/* Status Filter Buttons */}
                <div className="flex gap-3">
                  {([
                    { key: "all" as const, label: `All`, count: allCount, color: "bg-gray-600" },
                    { key: "online" as const, label: `Online`, count: onlineCount, color: "bg-green-600" },
                    { key: "offline" as const, label: `Offline`, count: offlineCount, color: "bg-red-600" }
                  ]).map(({ key, label, count, color }) => (
                    <button
                      key={key}
                      onClick={() => setFilter(key)}
                      className={`relative px-6 py-3 rounded-xl font-semibold transition-all duration-200 flex items-center gap-2
                                  ${filter === key 
                                    ? `${color} text-white shadow-lg scale-105` 
                                    : "bg-gray-100 text-gray-700 hover:bg-gray-200 hover:scale-102"}`}
                    >
                      <span>{label}</span>
                      <span className={`px-2 py-1 text-xs rounded-full font-bold
                                      ${filter === key ? "bg-white/20" : "bg-gray-300 text-gray-600"}`}>
                        {count}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Search and Sort Controls */}
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="relative">
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search devices, stadiums, firmware..."
                      className="w-full sm:w-80 pl-10 pr-4 py-3 border-2 border-gray-200 rounded-xl focus:border-emerald-500 focus:outline-none transition-colors"
                    />
                    <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
                      🔍
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-4 py-3">
                    <span className="text-sm font-medium text-gray-600">Sort:</span>
                    <select
                      value={sortAsc ? "asc" : "desc"}
                      onChange={(e) => setSortAsc(e.target.value === "asc")}
                      className="bg-transparent border-none outline-none font-medium text-gray-800"
                    >
                      <option value="asc">A → Z</option>
                      <option value="desc">Z → A</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Connection Status */}
        <div className="flex items-center justify-center mt-8">
          <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                          ${connectionStatus === 'Connected' 
                            ? 'bg-green-100 text-green-800 border border-green-200' 
                            : 'bg-orange-100 text-orange-800 border border-orange-200'}`}>
            <div className={`w-2 h-2 rounded-full ${connectionStatus === 'Connected' ? 'bg-green-500 animate-pulse' : 'bg-orange-500'}`}></div>
            <span>Connection Status: {connectionStatus}</span>
          </div>
        </div>

        {/* Device Grid */}
        {(() => {
          const filteredDevices = Object.entries(devices).filter(([_, d]) => {
            const statusOk =
              filter === "all" ? true : filter === "online" ? d.wifiConnected : !d.wifiConnected;
            if (!statusOk) return false;

            if (!queryLc) return true;
            const haystack = [
              d.name ?? "",
              d.stadium ?? "",
              d.firmwareVersion ?? ""
            ].map(s => s.toLowerCase()).join(" ");
            return haystack.includes(queryLc);
          });

return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredDevices
                .sort(([a], [b]) => (sortAsc ? a.localeCompare(b) : b.localeCompare(a)))
                .map(([deviceName, device]) => (
                  <div
                    key={deviceName}
                    className="bg-gray-100 rounded-2xl p-6 transform transition-all duration-200 hover:scale-105 hover:shadow-2xl border border-gray-200 mt-8 mx-8"
                  >
                    <DeviceComponent
                      name={device.name}
                      wifiConnected={device.wifiConnected}
                      batteryCharge={device.batteryCharge}
                      temperature={device.temperature}
                      firmwareVersion={device.firmwareVersion}
                      latencyMs={device.latencyMs}
                    />
                  </div>
                ))}
            </div>
          );
        })()}

        {/* Enhanced Toast Container */}
        <ToastContainer 
          position="bottom-right" 
          newestOnTop 
          closeOnClick 
          limit={5} 
          draggable
          theme="colored"
          toastClassName="backdrop-blur-sm"
        />
      </div>
    </div>
  );
};

export default Dashboard;
