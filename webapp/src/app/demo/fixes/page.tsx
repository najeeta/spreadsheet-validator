"use client";

import { useState, Fragment } from "react";
import { AlertTriangle, Send, SkipForward, Timer } from "lucide-react";

/**
 * Standalone demo page for the FixesTable design.
 * Visit /demo/fixes to preview the table with dummy data.
 * No CopilotKit dependency — buttons log to console.
 */

interface FixRequest {
  row_index: number;
  field: string;
  current_value: string;
  error_message: string;
}

const DUMMY_FIXES: FixRequest[] = [
  {
    row_index: 5,
    field: "employee_id",
    current_value: "EMP-INV",
    error_message:
      "Invalid employee_id format: 'EMP-INV'. Must be 4-12 alphanumeric characters (A-Z, 0-9).",
  },
  {
    row_index: 6,
    field: "dept",
    current_value: "NON",
    error_message:
      "Invalid department 'NON'. Must be one of: ['ENG', 'FIN', 'HR', 'OPS'].",
  },
  {
    row_index: 7,
    field: "amount",
    current_value: "-50.0",
    error_message: "Amount -50.0 out of range. Must be > 0 and <= 100,000.",
  },
  {
    row_index: 8,
    field: "currency",
    current_value: "ABC",
    error_message:
      "Invalid currency 'ABC'. Must be one of: ['EUR', 'GBP', 'INR', 'USD'].",
  },
  {
    row_index: 10,
    field: "fx_rate",
    current_value: "",
    error_message: "fx_rate is required for non-USD currency 'EUR'.",
  },
  // Multi-fix row example: row 12 has two errors
  {
    row_index: 12,
    field: "dept",
    current_value: "XXX",
    error_message:
      "Invalid department 'XXX'. Must be one of: ['ENG', 'FIN', 'HR', 'OPS'].",
  },
  {
    row_index: 12,
    field: "amount",
    current_value: "999999",
    error_message: "Amount 999999 out of range. Must be > 0 and <= 100,000.",
  },
];

interface RowGroup {
  rowIndex: number;
  fixes: FixRequest[];
}

function groupByRow(fixes: FixRequest[]): RowGroup[] {
  const groups = new Map<number, FixRequest[]>();
  for (const fix of fixes) {
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
}

export default function FixesDemoPage() {
  const [fixValues, setFixValues] = useState<Record<string, string>>({});
  const grouped = groupByRow(DUMMY_FIXES);
  const fixKey = (fix: FixRequest) => `${fix.row_index}-${fix.field}`;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">FixesTable Demo</h1>
          <p className="text-sm text-gray-500 mt-1">
            Preview of the compact fixes table design. Buttons log to console.
          </p>
        </div>

        {/* The actual table card */}
        <div className="w-full rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-red-700">
              <AlertTriangle className="h-5 w-5" />
              <span className="font-semibold text-lg">
                Fixes Needed ({DUMMY_FIXES.length})
              </span>
            </div>
            <span className="text-sm text-green-600 font-medium">
              1 row handled
            </span>
          </div>

          {/* Table */}
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
              {grouped.map((group) => {
                const rowSpan = group.fixes.length * 2;
                return (
                  <tbody key={group.rowIndex}>
                    {group.fixes.map((fix, fixIdx) => {
                      const key = fixKey(fix);
                      const isFirst = fixIdx === 0;
                      const isLast = fixIdx === group.fixes.length - 1;
                      return (
                        <Fragment key={key}>
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
                                className="w-full rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-burgundy-500 focus:border-burgundy-500"
                              />
                            </td>
                            {isFirst && (
                              <td rowSpan={rowSpan} className="px-2 align-middle">
                                <div className="flex items-center gap-1.5 justify-end">
                                  <button
                                    onClick={() =>
                                      console.log("Fix row", group.rowIndex, fixValues)
                                    }
                                    className="flex items-center gap-1 rounded bg-burgundy-800 px-2 py-1 text-xs font-medium text-white hover:bg-burgundy-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
                                    <Send className="h-3 w-3" />
                                    Fix
                                  </button>
                                  <button
                                    onClick={() =>
                                      console.log("Skip row", group.rowIndex)
                                    }
                                    className="flex items-center gap-1 rounded border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
                                  >
                                    <SkipForward className="h-3 w-3" />
                                    Skip
                                  </button>
                                </div>
                              </td>
                            )}
                          </tr>
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

          {/* Footer */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-sm text-gray-600">
              Fixing 5 of 6 error rows
            </span>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium flex items-center gap-1 text-amber-600">
                <Timer className="h-3.5 w-3.5" />
                22s
              </span>
              <button className="text-sm text-gray-500 hover:text-gray-700 underline">
                Skip all
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
