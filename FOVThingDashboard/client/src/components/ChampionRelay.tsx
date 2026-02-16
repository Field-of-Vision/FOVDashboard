import { ActivitySquareIcon } from "lucide-react";

interface ChampionRelayProps {
  /** relay heartbeat object coming from the WS – may be undefined */
  data?: {
    alive?: boolean;
    last_seen?: string;   // ISO string from backend
  };
  wsConnected?: boolean;
}

export default function ChampionRelay({ data, wsConnected = true }: ChampionRelayProps) {
  if (!wsConnected) return null;   // hide while reconnecting

  // Use backend's alive calculation when available, otherwise calculate locally
  // to prevent "flash to offline" on page refresh when backend hasn't sent data yet
  const timeoutMs = 90_000;                    // keep in sync with backend
  const seen      = data?.last_seen ? new Date(data.last_seen).getTime() : null;
  const localAlive = !!seen && (Date.now() - seen) < timeoutMs;
  const alive     = data?.alive !== undefined ? data.alive : localAlive;
  
  const lastSeen  = seen
      ? new Date(seen).toLocaleTimeString()
      : "never";

  return (
    <div
      className="
        fixed top-4 right-4 z-50
        flex items-center gap-2
        bg-white shadow-sm rounded-xl border border-blue-100
        px-3 py-2 text-sm"
    >
      <ActivitySquareIcon className="w-4 h-4 text-gray-600" />
	  <span>Champion Data Relay</span>
      <span className={alive ? "text-green-600" : "text-red-600"}>
        {alive ? "online" : "offline"}
      </span>
      <span className="text-gray-500">· last {lastSeen} UTC</span>
    </div>
  );
} 