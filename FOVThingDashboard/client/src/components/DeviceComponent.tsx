import React, { useState } from 'react';
import { BatteryIcon, CpuIcon, ThermometerIcon, WifiIcon, ClockIcon } from "lucide-react";
import DeviceHistoryModal from './DeviceHistoryModal';
import { API_BASE } from '../config'; // ← use shared base URL

interface HistoryEntry {
  id: number;
  timestamp: string;   // modal expects "timestamp"
  metricType: string;  // modal expects "metricType"
  value: string;
}

interface DeviceProps {
    name: string;
    wifiConnected?: boolean;
    batteryCharge?: number;
    temperature?: number;
    firmwareVersion?: string;
    latencyMs?: number;
}

function DeviceComponent({
    name,
    wifiConnected,
    batteryCharge,
    temperature,
    firmwareVersion,
    latencyMs = -1,
}: DeviceProps) {
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [history, setHistory] = useState<HistoryEntry[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [hasMore, setHasMore] = useState(true);

    const handleClick = async () => {
        setIsModalOpen(true);
        setIsLoading(true);
        const data = await fetchHistory();
        setHistory(data.logs);
        setHasMore(data.hasMore);
        setIsLoading(false);
    };

    const handleLoadMore = async (lastId: number) => {
        const data = await fetchHistory(lastId);
        setHistory(prev => [...prev, ...data.logs]);
        setHasMore(data.hasMore);
    };

    const fetchHistory = async (lastId?: number) => {
        try {
            const token = localStorage.getItem('token') || '';
            const url = new URL(`${API_BASE}/api/device/${encodeURIComponent(name)}/history`);
            url.searchParams.set('hours', '3');
            url.searchParams.set('page_size', '20');
            if (lastId) url.searchParams.set('last_id', String(lastId));

            const response = await fetch(url.toString(), {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Map API fields (id, ts, metric, value) -> component shape
            const logs: HistoryEntry[] = (data.logs || []).map((l: any) => ({
                id: l.id,
                timestamp: l.ts,
                metricType: l.metric,
                value: l.value,
            }));

            return {
                logs,
                hasMore: !!data.hasMore
            };
        } catch (error) {
            console.error('Error fetching device history:', error);
            return { logs: [], hasMore: false };
        }
    };

    return (
        <>
            <div
                className="bg-card text-card-foreground rounded-lg shadow-md p-4 flex flex-col space-y-4 cursor-pointer hover:shadow-lg transition-shadow"
                onClick={handleClick}
            >
                <h3 className="text-sm font-semibold">{name}</h3>
                <div className="flex items-center space-x-2">
                    <WifiIcon className={`h-5 w-5 ${wifiConnected ? 'text-green-500' : 'text-red-500'}`} />
                    <span>{wifiConnected ? 'Connected' : 'Disconnected'}</span>
                </div>
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <BatteryIcon className="h-5 w-5" />
                            <span>Battery</span>
                        </div>
                        <span className="font-medium">{batteryCharge}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5">
                        <div
                            className="bg-blue-500 h-2.5 rounded-full"
                            style={{ width: `${batteryCharge}%` }}
                        ></div>
                    </div>
                </div>
                <div className="flex items-center space-x-2">
                    <ThermometerIcon className="h-5 w-5" />
                    <span>Temperature: {temperature}°C</span>
                </div>

                {latencyMs >= 0 && (
                    <div className="flex items-center space-x-2">
                        <ClockIcon className="h-5 w-5" />
                        <span>RTT: {latencyMs.toFixed(1)} ms</span>
                    </div>
                )}

                <div className="flex items-center space-x-2">
                    <CpuIcon className="h-5 w-5" />
                    <span>Firmware: {firmwareVersion}</span>
                </div>
            </div>

            <DeviceHistoryModal
                deviceName={name}
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                history={history}
                isLoading={isLoading}
                hasMore={hasMore}
                onLoadMore={handleLoadMore}
            />
        </>
    );
}

export default DeviceComponent;
