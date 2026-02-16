import React, { useRef, useEffect, useState } from 'react';
import { X } from 'lucide-react';

interface HistoryEntry {
  id: number;
  timestamp: string;
  metricType: string;
  value: string;
}

interface DeviceHistoryModalProps {
  deviceName: string;
  isOpen: boolean;
  onClose: () => void;
  onLoadMore: (lastId: number) => Promise<void>;
  history: HistoryEntry[];
  isLoading: boolean;
  hasMore: boolean;
}

const DeviceHistoryModal: React.FC<DeviceHistoryModalProps> = ({
  deviceName,
  isOpen,
  onClose,
  onLoadMore,
  history = [],
  isLoading = false,
  hasMore = false
}) => {
  const [loadingMore, setLoadingMore] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleScroll = async () => {
    if (!containerRef.current || loadingMore || !hasMore) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    if (scrollHeight - scrollTop - clientHeight < 20) {
      setLoadingMore(true);
      const lastEntry = history[history.length - 1];
      if (lastEntry?.id) {
        await onLoadMore(lastEntry.id);
      }
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll);
      return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [hasMore, loadingMore, history]);

  if (!isOpen) return null;

  const formatValue = (entry: HistoryEntry) => {
    try {
      const parsed = JSON.parse(entry.value);
      if (entry.metricType === 'battery') {
        const pct =
          parsed['Battery_Percentage'] ?? parsed['Battery Percentage'] ?? parsed;
        return `${pct}%`;
      } else if (entry.metricType === 'temperature') {
        return `${parsed['Temperature']}°C`;
      }
      return entry.value;
    } catch {
      return entry.value;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden shadow-2xl border border-blue-100">
        <div className="p-4 border-b border-blue-100 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-800">{deviceName} History</h2>
          <button onClick={onClose} className="p-2 hover:bg-blue-50 rounded-full transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div
          ref={containerRef}
          className="p-4 overflow-auto max-h-[calc(80vh-8rem)]"
        >
          {isLoading && history.length === 0 ? (
            <div className="text-center py-4">Loading history...</div>
          ) : history.length === 0 ? (
            <div className="text-center py-4">No history available</div>
          ) : (
            <>
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Time</th>
                    <th className="text-left p-2">Type</th>
                    <th className="text-left p-2">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((entry) => (
                    <tr key={entry.id} className="border-b hover:bg-gray-50">
                      <td className="p-2">{formatTimestamp(entry.timestamp)}</td>
                      <td className="p-2">{entry.metricType}</td>
                      <td className="p-2">{formatValue(entry)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {loadingMore && (
                <div className="text-center py-4">Loading more...</div>
              )}
              {!hasMore && history.length > 0 && (
                <div className="text-center py-4 text-gray-500">No more history</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default DeviceHistoryModal;
