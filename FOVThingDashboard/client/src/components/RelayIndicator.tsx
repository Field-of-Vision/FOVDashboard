import { ActivitySquareIcon } from "lucide-react";

interface RelayEntry {
  stadiumName: string;
  alive: boolean;
  lastSeen: string | null; // ISO string or null
}

interface RelayIndicatorProps {
  entries: RelayEntry[];
  wsConnected?: boolean;
}

export default function RelayIndicator({ entries, wsConnected = true }: RelayIndicatorProps) {
  if (!wsConnected || entries.length === 0) return null;

  const timeoutMs = 90_000;

  return (
    <div
      className="
        fixed top-4 right-4 z-50
        flex items-center gap-3
        bg-white shadow-sm rounded-xl border border-blue-100
        px-3 py-2 text-sm"
    >
      <ActivitySquareIcon className="w-4 h-4 text-gray-600" />
      {entries.map((entry) => {
        const seen = entry.lastSeen ? new Date(entry.lastSeen).getTime() : null;
        const localAlive = !!seen && (Date.now() - seen) < timeoutMs;
        const alive = entry.alive !== undefined ? entry.alive : localAlive;
        const lastSeenStr = seen
          ? new Date(seen).toLocaleTimeString()
          : "never";

        return (
          <span key={entry.stadiumName} className="flex items-center gap-1.5">
            <span>{entry.stadiumName} Relay</span>
            <span className={alive ? "text-green-600" : "text-red-600"}>
              {alive ? "online" : "offline"}
            </span>
            <span className="text-gray-500">· last {lastSeenStr} UTC</span>
          </span>
        );
      })}
    </div>
  );
}
