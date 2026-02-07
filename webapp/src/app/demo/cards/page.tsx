"use client";

import { useState, Fragment } from "react";
import {
  AlertTriangle,
  Send,
  SkipForward,
  Timer,
  CheckCircle2,
  FileSpreadsheet,
  UploadCloud,
} from "lucide-react";
import { ProcessingSkeleton } from "@/components/a2ui/ProcessingSkeleton";

/**
 * Standalone demo page for all card components.
 * Visit /demo/cards to preview every card with dummy data.
 * No CopilotKit/ValidatorContext dependencies — buttons log to console.
 */

// ---------------------------------------------------------------------------
// Inline demo replicas of components that use hooks (CompletionCard, FixesTable)
// ---------------------------------------------------------------------------

function DemoCompletionCard({
  totalRows,
  validCount,
  errorCount,
  fixedCount,
  artifactNames,
}: {
  totalRows: number;
  validCount: number;
  errorCount: number;
  fixedCount: number;
  artifactNames: string[];
}) {
  return (
    <div className="animate-card-in rounded-lg border border-gray-300 bg-white p-8 mx-auto max-w-md space-y-4">
      <div className="flex items-center gap-2 text-emerald-700">
        <CheckCircle2 className="h-5 w-5" />
        <span className="font-semibold">Validation Complete</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-500">Total rows:</span>{" "}
          <span className="font-bold">{totalRows}</span>
        </div>
        <div>
          <span className="text-gray-500">Valid:</span>{" "}
          <span className="font-bold text-emerald-600">{validCount}</span>
        </div>
        <div>
          <span className="text-gray-500">Errors:</span>{" "}
          <span className="font-bold text-red-600">{errorCount}</span>
        </div>
        <div>
          <span className="text-gray-500">Fixed:</span>{" "}
          <span className="font-bold text-burgundy-700">{fixedCount}</span>
        </div>
      </div>
      <div className="space-y-2">
        <div className="text-sm text-gray-500">Download artifacts:</div>
        <div className="flex gap-4">
          {artifactNames.map((name) => (
            <button
              key={name}
              onClick={() => console.log("[DemoCompletionCard] Download", name)}
              className="flex flex-col items-center gap-1 p-3 rounded-lg bg-white border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors cursor-pointer"
            >
              <FileSpreadsheet className="h-10 w-10 text-gray-400" />
              <span className="text-xs text-gray-600 text-center">{name}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="pt-3 border-t border-gray-200">
        <button
          onClick={() => console.log("[DemoCompletionCard] Upload Another clicked")}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[#800020] rounded-lg hover:bg-[#6b001a] transition-colors"
        >
          <UploadCloud className="h-4 w-4" />
          Upload Another File
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FixesTable demo replica (same DUMMY_FIXES as /demo/fixes)
// ---------------------------------------------------------------------------

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

function DemoFixesTable() {
  const [fixValues, setFixValues] = useState<Record<string, string>>({});
  const grouped = groupByRow(DUMMY_FIXES);
  const fixKey = (fix: FixRequest) => `${fix.row_index}-${fix.field}`;

  return (
    <div className="w-full rounded-lg border border-red-200 bg-red-50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-red-700">
          <AlertTriangle className="h-5 w-5" />
          <span className="font-semibold text-lg">
            Fixes Needed ({DUMMY_FIXES.length})
          </span>
        </div>
        <span className="text-sm text-green-600 font-medium">1 row handled</span>
      </div>

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
                                className="flex items-center gap-1 rounded bg-burgundy-800 px-2 py-1 text-xs font-medium text-white hover:bg-burgundy-700 transition-colors"
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
                      <tr
                        className={
                          isLast
                            ? "border-b border-red-200"
                            : "border-b border-red-100"
                        }
                      >
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

      <div className="flex items-center justify-between pt-1">
        <span className="text-sm text-gray-600">
          Fixing 3 of 4 error rows
        </span>
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium flex items-center gap-1 text-amber-600">
            <Timer className="h-3.5 w-3.5" />
            22s
          </span>
          <button
            onClick={() => console.log("[DemoFixesTable] Skip all clicked")}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Skip all
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main demo page
// ---------------------------------------------------------------------------

export default function CardsDemoPage() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto space-y-12">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Card Components Demo</h1>
          <p className="text-sm text-gray-500 mt-1">
            Preview of all card components with dummy data. Buttons log to console.
          </p>
        </div>

        {/* ProcessingSkeleton */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-800">ProcessingSkeleton</h2>
          <p className="text-xs text-gray-500">Shown during RUNNING/INGESTING/TRANSFORMING/PACKAGING statuses.</p>
          <ProcessingSkeleton />
        </section>

        {/* FixesTable */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-800">FixesTable</h2>
          <p className="text-xs text-gray-500">Shown during WAITING_FOR_USER status with pending fixes.</p>
          <DemoFixesTable />
        </section>

        {/* CompletionCard */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-800">CompletionCard</h2>
          <p className="text-xs text-gray-500">Shown when pipeline completes.</p>
          <DemoCompletionCard
            totalRows={100}
            validCount={92}
            errorCount={8}
            fixedCount={5}
            artifactNames={["success.xlsx", "errors.xlsx"]}
          />
        </section>
      </div>
    </div>
  );
}
