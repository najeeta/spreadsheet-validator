"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, Plus, Check } from "lucide-react";

const BACKEND_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";

interface Run {
    session_id: string;
    // thread_id: string; // Removed
    status?: string;
    file_name?: string;
}

export function RunsDropdown({
    currentRunId,
}: {
    currentRunId: string;
}) {
    const router = useRouter();
    const [isOpen, setIsOpen] = useState(false);
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchRuns = useCallback(async () => {
        try {
            setLoading(true);
            const res = await fetch(`${BACKEND_URL}/runs`);
            if (res.ok) {
                const data = await res.json();
                setRuns(data);
            }
        } catch (err) {
            console.error("Failed to fetch runs", err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (isOpen) {
            fetchRuns();
        }
    }, [isOpen, fetchRuns]);

    const handleCreateRun = useCallback(async () => {
        // Create new run on backend
        try {
            const res = await fetch(`${BACKEND_URL}/run`, { method: "POST" });
            if (res.ok) {
                const data = await res.json();
                router.push(`/runs/${data.session_id}`);
                setIsOpen(false);
            }
        } catch (e) {
            console.error("Failed to create run", e);
        }
    }, [router]);

    const handleSelectRun = (sessionId: string) => {
        if (sessionId !== currentRunId) {
            router.push(`/runs/${sessionId}`);
        }
        setIsOpen(false);
    };

    // Find current run details for display
    const currentRun = runs.find((r) => r.session_id === currentRunId);

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-md border border-gray-200 transition-colors"
            >
                <span>
                    {currentRun?.file_name
                        ? currentRun.file_name
                        : "Runs"}
                </span>
                <ChevronDown className="h-4 w-4 text-gray-400" />
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-1 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
                    <div className="p-2 border-b border-gray-100">
                        <button
                            onClick={handleCreateRun}
                            className="flex items-center gap-2 w-full px-2 py-1.5 text-sm text-burgundy-700 hover:bg-burgundy-50 rounded-md transition-colors"
                        >
                            <Plus className="h-4 w-4" />
                            <span>New Run</span>
                        </button>
                    </div>

                    <div className="max-h-64 overflow-y-auto py-1">
                        {loading ? (
                            <div className="px-4 py-2 text-xs text-gray-400 text-center">
                                Loading...
                            </div>
                        ) : runs.length === 0 ? (
                            <div className="px-4 py-2 text-xs text-gray-400 text-center">
                                No runs found
                            </div>
                        ) : (
                            runs.map((run) => (
                                <button
                                    key={run.session_id}
                                    onClick={() => handleSelectRun(run.session_id)}
                                    className="w-full flex items-center justify-between px-4 py-2 text-left hover:bg-gray-50 transition-colors group"
                                >
                                    <div className="flex flex-col min-w-0">
                                        <span className="text-sm font-medium text-gray-700 truncate group-hover:text-gray-900">
                                            {run.file_name || "Untitled Run"}
                                        </span>
                                        <span className="text-xs text-gray-400 truncate font-mono">
                                            {run.session_id.slice(0, 8)}
                                        </span>
                                    </div>
                                    {run.session_id === currentRunId && (
                                        <Check className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                                    )}
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}

            {isOpen && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsOpen(false)}
                />
            )}
        </div>
    );
}
