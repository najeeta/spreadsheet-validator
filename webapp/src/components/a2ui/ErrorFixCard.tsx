"use client";

import { useState } from "react";
import { AlertTriangle, Send } from "lucide-react";
import { useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, Role } from "@copilotkit/runtime-client-gql";
import type { FixRequest } from "@/lib/types";

interface ErrorFixCardProps {
  pendingFixes: FixRequest[];
}

export function ErrorFixCard({ pendingFixes }: ErrorFixCardProps) {
  const { appendMessage } = useCopilotChat();
  const [fixValues, setFixValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});

  const fixKey = (fix: FixRequest) => `${fix.row_index}-${fix.field}`;

  const handleSubmitFix = async (fix: FixRequest) => {
    const key = fixKey(fix);
    const newValue = fixValues[key];
    if (!newValue?.trim()) return;

    setSubmitting((prev) => ({ ...prev, [key]: true }));

    await appendMessage(
      new TextMessage({
        content: `Fix row ${fix.row_index}, field "${fix.field}" to "${newValue.trim()}"`,
        role: Role.User,
      }),
    );

    setFixValues((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSubmitting((prev) => ({ ...prev, [key]: false }));
  };

  return (
    <div className="animate-card-in rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
      <div className="flex items-center gap-2 text-red-700">
        <AlertTriangle className="h-5 w-5" />
        <span className="font-semibold">
          Fixes Needed ({pendingFixes.length})
        </span>
      </div>
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {pendingFixes.map((fix) => {
          const key = fixKey(fix);
          return (
            <div
              key={key}
              className="rounded border border-gray-300 bg-white p-3 space-y-2"
            >
              <div className="flex items-center gap-2 text-sm">
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-mono text-gray-600">
                  Row {fix.row_index}
                </span>
                <span className="font-medium text-amber-700">
                  {fix.field}
                </span>
              </div>
              <div className="text-xs text-gray-500">
                Current:{" "}
                <span className="text-gray-700">
                  {fix.current_value || "(empty)"}
                </span>
              </div>
              <div className="text-xs text-red-600">{fix.error_message}</div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="New value..."
                  value={fixValues[key] ?? ""}
                  onChange={(e) =>
                    setFixValues((prev) => ({
                      ...prev,
                      [key]: e.target.value,
                    }))
                  }
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleSubmitFix(fix);
                    }
                  }}
                  className="flex-1 rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-burgundy-500"
                  disabled={submitting[key]}
                />
                <button
                  onClick={() => handleSubmitFix(fix)}
                  disabled={!fixValues[key]?.trim() || submitting[key]}
                  className="flex items-center gap-1 rounded bg-burgundy-800 px-2 py-1 text-sm font-medium text-white hover:bg-burgundy-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="h-3 w-3" />
                  Fix
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
