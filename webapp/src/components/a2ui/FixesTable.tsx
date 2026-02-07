"use client";

import { useState, useMemo, useEffect, useRef, useCallback, Fragment } from "react";
import { AlertTriangle, Send, CheckCircle2, SkipForward, Timer } from "lucide-react";
import { useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, Role } from "@copilotkit/runtime-client-gql";
import type { FixRequest } from "@/lib/types";

const TIMEOUT_SECONDS = 30;

interface FixesTableProps {
  pendingReview: FixRequest[];
  waitingSince?: number;
  totalErrorRows?: number;
}

interface RowGroup {
  rowIndex: number;
  fixes: FixRequest[];
}

export function FixesTable({
  pendingReview,
  waitingSince,
  totalErrorRows,
}: FixesTableProps) {
  const { appendMessage } = useCopilotChat();
  // Per-row fix values: key = `${rowIndex}-${field}`
  const [fixValues, setFixValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<number, boolean>>({});
  const [submitted, setSubmitted] = useState<Set<number>>(new Set());
  const [exiting, setExiting] = useState<Set<number>>(new Set());
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const skipSentRef = useRef(false);

  const fixKey = (fix: FixRequest) => `${fix.row_index}-${fix.field}`;

  // Filter out submitted rows
  const activeFixes = pendingReview.filter(
    (fix) => !submitted.has(fix.row_index),
  );

  // Group by row
  const groupedByRow: RowGroup[] = useMemo(() => {
    const groups = new Map<number, FixRequest[]>();
    for (const fix of activeFixes) {
      const existing = groups.get(fix.row_index);
      if (existing) {
        existing.push(fix);
      } else {
        groups.set(fix.row_index, [fix]);
      }
    }
    return [...groups.entries()]
      .sort(([a], [b]) => a - b)
      .map(([rowIndex, fixes]) => ({ rowIndex, fixes }));
  }, [activeFixes]);

  // Countdown timer
  useEffect(() => {
    if (!waitingSince) {
      setSecondsLeft(null);
      return;
    }

    const update = () => {
      const elapsed = (Date.now() / 1000) - waitingSince;
      const remaining = Math.max(0, TIMEOUT_SECONDS - Math.floor(elapsed));
      setSecondsLeft(remaining);
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [waitingSince]);

  // Auto-skip on timeout
  useEffect(() => {
    if (secondsLeft === 0 && !skipSentRef.current && activeFixes.length > 0) {
      skipSentRef.current = true;
      appendMessage(
        new TextMessage({
          content: "Skip remaining fixes and continue",
          role: Role.User,
        }),
      );
    }
  }, [secondsLeft, activeFixes.length, appendMessage]);

  // Reset skip guard when waitingSince changes (new batch)
  useEffect(() => {
    skipSentRef.current = false;
  }, [waitingSince]);

  // Trigger exit animation then move to submitted after animation completes
  const exitRow = useCallback(
    (rowIdx: number) => {
      setExiting((prev) => new Set(prev).add(rowIdx));
      setTimeout(() => {
        setExiting((prev) => {
          const next = new Set(prev);
          next.delete(rowIdx);
          return next;
        });
        setSubmitted((prev) => new Set(prev).add(rowIdx));
      }, 550);
    },
    [],
  );

  const handleFixRow = useCallback(
    async (group: RowGroup) => {
      const rowIdx = group.rowIndex;
      // Collect values for this row's fields
      const fixes: Record<string, string> = {};
      let hasValues = false;
      for (const fix of group.fixes) {
        const key = fixKey(fix);
        const val = fixValues[key]?.trim();
        if (val) {
          fixes[fix.field] = val;
          hasValues = true;
        }
      }
      if (!hasValues) return;

      setSubmitting((prev) => ({ ...prev, [rowIdx]: true }));

      const fixPairs = Object.entries(fixes)
        .map(([field, val]) => `${field}="${val}"`)
        .join(", ");

      await appendMessage(
        new TextMessage({
          content: `Batch fix row ${rowIdx}: ${fixPairs}`,
          role: Role.User,
        }),
      );

      // Clear fix values for this row
      setFixValues((prev) => {
        const next = { ...prev };
        for (const fix of group.fixes) {
          delete next[fixKey(fix)];
        }
        return next;
      });
      setSubmitting((prev) => ({ ...prev, [rowIdx]: false }));
      // Animate row out
      exitRow(rowIdx);
    },
    [fixValues, appendMessage, exitRow],
  );

  const handleSkipRow = useCallback(
    async (rowIndex: number) => {
      setSubmitting((prev) => ({ ...prev, [rowIndex]: true }));

      await appendMessage(
        new TextMessage({
          content: `Skip row ${rowIndex}`,
          role: Role.User,
        }),
      );

      setSubmitting((prev) => ({ ...prev, [rowIndex]: false }));
      // Animate row out
      exitRow(rowIndex);
    },
    [appendMessage, exitRow],
  );

  const handleSkipAll = useCallback(async () => {
    if (skipSentRef.current) return;
    skipSentRef.current = true;
    await appendMessage(
      new TextMessage({
        content: "Skip remaining fixes and continue",
        role: Role.User,
      }),
    );
  }, [appendMessage]);

  // All fixes submitted
  if (activeFixes.length === 0 && submitted.size > 0) {
    return (
      <div className="animate-card-in w-full rounded-lg border border-green-200 bg-green-50 p-6">
        <div className="flex items-center gap-2 text-green-700">
          <CheckCircle2 className="h-5 w-5" />
          <span className="font-semibold text-lg">All fixes submitted</span>
        </div>
        <p className="text-sm text-green-600 mt-2">
          Waiting for validation to complete...
        </p>
      </div>
    );
  }

  const timerColor =
    secondsLeft !== null && secondsLeft <= 10
      ? "text-red-600"
      : secondsLeft !== null && secondsLeft <= 20
        ? "text-amber-600"
        : "text-gray-600";

  const batchLabel = totalErrorRows
    ? `Fixing ${Math.min(groupedByRow.length, 5)} of ${totalErrorRows} error rows`
    : `${groupedByRow.length} rows need fixes`;

  return (
    <div className="animate-card-in w-full rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span className="font-semibold text-lg">
            Fixes Needed ({activeFixes.length})
          </span>
        </div>
        {submitted.size > 0 && (
          <span className="text-sm text-green-600 font-medium">
            {submitted.size} row{submitted.size !== 1 ? "s" : ""} handled
          </span>
        )}
      </div>

      {/* Compact table */}
      <div className="overflow-x-auto rounded-md border border-red-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-red-200 bg-red-50/50 text-xs text-gray-500 uppercase tracking-wide">
              <th className="text-left py-2 px-3 font-medium w-12">Row</th>
              <th className="text-left py-2 px-3 font-medium">Field</th>
              <th className="text-left py-2 px-3 font-medium w-24">Current</th>
              <th className="text-left py-2 px-3 font-medium w-40">New Value</th>
              <th className="py-2 px-2 w-24"></th>
            </tr>
          </thead>
          {groupedByRow.map((group) => {
            const isRowSubmitting = submitting[group.rowIndex];
            const isExiting = exiting.has(group.rowIndex);
            // Each fix renders 2 <tr>: data row + error row
            const rowSpan = group.fixes.length * 2;
            return (
              <tbody
                key={group.rowIndex}
                className={isExiting ? "animate-row-out" : "animate-card-in"}
              >
                {group.fixes.map((fix, fixIdx) => {
                  const key = fixKey(fix);
                  const isFirst = fixIdx === 0;
                  const isLast = fixIdx === group.fixes.length - 1;
                  return (
                    <Fragment key={key}>
                      {/* Data row */}
                      <tr>
                        {isFirst && (
                          <td
                            rowSpan={rowSpan}
                            className="px-3 align-middle text-center font-bold text-gray-800"
                          >
                            {group.rowIndex}
                          </td>
                        )}
                        <td className="pt-2.5 pb-0.5 px-3 font-medium text-gray-800">
                          {fix.field}
                        </td>
                        <td className="pt-2.5 pb-0.5 px-3 font-mono text-xs text-gray-500 truncate max-w-[6rem]">
                          {fix.current_value || "\u2014"}
                        </td>
                        <td className="pt-2.5 pb-0.5 px-3">
                          <input
                            type="text"
                            placeholder={fix.field}
                            value={fixValues[key] ?? ""}
                            onChange={(e) =>
                              setFixValues((prev) => ({
                                ...prev,
                                [key]: e.target.value,
                              }))
                            }
                            onKeyDown={(e) => {
                              if (
                                e.key === "Enter" &&
                                group.fixes.length === 1
                              ) {
                                e.preventDefault();
                                handleFixRow(group);
                              }
                            }}
                            className="w-full rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-burgundy-500 focus:border-burgundy-500"
                            disabled={isRowSubmitting}
                          />
                        </td>
                        {isFirst && (
                          <td
                            rowSpan={rowSpan}
                            className="px-2 align-middle"
                          >
                            <div className="flex items-center gap-1.5 justify-end">
                              <button
                                aria-label={`Fix Row ${group.rowIndex}`}
                                onClick={() => handleFixRow(group)}
                                disabled={
                                  isRowSubmitting ||
                                  !group.fixes.some((f) => fixValues[fixKey(f)]?.trim())
                                }
                                className="flex items-center gap-1 rounded bg-burgundy-800 px-2 py-1 text-xs font-medium text-white hover:bg-burgundy-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                <Send className="h-3 w-3" />
                                Fix
                              </button>
                              <button
                                aria-label={`Skip Row ${group.rowIndex}`}
                                onClick={() => handleSkipRow(group.rowIndex)}
                                disabled={isRowSubmitting}
                                className="flex items-center gap-1 rounded border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                <SkipForward className="h-3 w-3" />
                                Skip
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                      {/* Error reason sub-row — wrapped text constrained to Field column width */}
                      <tr className={isLast ? "border-b border-red-200" : "border-b border-red-100"}>
                        <td colSpan={3} className="pb-2 pt-0 px-3">
                          <p className="text-xs text-red-600 leading-snug break-words">
                            {fix.error_message}
                          </p>
                        </td>
                      </tr>
                    </Fragment>
                  );
                })}
              </tbody>
            );
          })}
        </table>
      </div>

      {/* Footer: batch info + timer */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-sm text-gray-600">{batchLabel}</span>
        <div className="flex items-center gap-3">
          {secondsLeft !== null && (
            <span className={`text-sm font-medium flex items-center gap-1 ${timerColor}`}>
              <Timer className="h-3.5 w-3.5" />
              {secondsLeft}s
            </span>
          )}
          <button
            onClick={handleSkipAll}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Skip all
          </button>
        </div>
      </div>
    </div>
  );
}
