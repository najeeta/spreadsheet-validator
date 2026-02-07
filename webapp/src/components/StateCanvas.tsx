"use client";

import { useState, useCallback, useEffect } from "react";
import type { PipelineStatus, RunGlobals, UsdRounding } from "@/lib/types";
import { DEFAULT_INITIAL_STATE, DEFAULT_GLOBALS } from "@/lib/types";
import { renderForState } from "@/lib/stateToCard";
import {
  FileSpreadsheet,
  Upload as UploadIcon,
  Database,
  ShieldCheck,
  Wrench,
  Package,
  Calendar,
  DollarSign,
  Building2,
  Plus,
  Trash2,
  Play,
} from "lucide-react";
import { useValidator } from "@/contexts/ValidatorContext";

const STATUS_LABELS: Record<PipelineStatus, string> = {
  IDLE: "Idle",
  UPLOADING: "Uploading",
  INGESTING: "Ingesting",
  RUNNING: "Running",
  VALIDATING: "Validating",
  WAITING_FOR_USER: "Waiting for Fix",
  FIXING: "Applying Fix",
  TRANSFORMING: "Transforming",
  PACKAGING: "Packaging",
  COMPLETED: "Completed",
  FAILED: "Failed",
};

function statusBadgeClasses(status: PipelineStatus): string {
  switch (status) {
    case "COMPLETED":
      return "bg-emerald-100 text-emerald-700";
    case "FAILED":
      return "bg-red-100 text-red-700";
    case "WAITING_FOR_USER":
      return "bg-amber-100 text-amber-700";
    case "IDLE":
      return "bg-gray-100 text-gray-500";
    default:
      return "bg-burgundy-100 text-burgundy-700";
  }
}

/**
 * Left-panel canvas that renders a pipeline status dashboard
 * showing all agent state attributes, plus the active card.
 */
export function StateCanvas() {
  // Get shared agent state from context (single source of truth)
  const { agentState, triggerUpload, startPipeline } = useValidator();

  // Use DEFAULT_INITIAL_STATE as fallback for any missing fields
  const state = { ...DEFAULT_INITIAL_STATE, ...agentState };

  // Debug: Log state changes
  useEffect(() => {
    console.log("[StateCanvas] State updated:", {
      status: state.status,
      pending_fixes_count: state.pending_fixes?.length ?? 0,
      pending_fixes: state.pending_fixes,
    });
  }, [state.status, state.pending_fixes]);

  // Local state for globals editing
  const [globals, setGlobals] = useState<RunGlobals>(state.globals ?? DEFAULT_GLOBALS);
  const [newDept, setNewDept] = useState("");
  const [newCostCenter, setNewCostCenter] = useState("");

  const card = renderForState(state);

  const totalRows = state.dataframe_records?.length ?? 0;
  const columnCount = state.dataframe_columns?.length ?? 0;
  const skippedRowIndices = new Set((state.skipped_fixes ?? []).map((f) => f.row_index));
  const errorCount =
    (state.validation_errors?.length ?? 0) > 0
      ? state.validation_errors!.length
      : skippedRowIndices.size;
  const fixCount = state.pending_fixes?.length ?? 0;
  const artifactCount = Object.keys(state.artifacts ?? {}).length;

  // Check if ready to submit (file uploaded + globals have defaults)
  const hasFile = Boolean(state.file_name || state.uploaded_file);
  const hasGlobals = Boolean(globals.as_of && globals.usd_rounding);
  const canSubmit = hasFile && hasGlobals && state.status === "IDLE";

  // Update globals handler
  const updateGlobals = useCallback((updates: Partial<RunGlobals>) => {
    setGlobals(prev => ({ ...prev, ...updates }));
  }, []);

  // Add cost center mapping
  const addCostCenterMapping = useCallback(() => {
    if (!newDept.trim() || !newCostCenter.trim()) return;
    setGlobals(prev => ({
      ...prev,
      cost_center_map: {
        ...prev.cost_center_map,
        [newDept.trim()]: newCostCenter.trim(),
      },
    }));
    setNewDept("");
    setNewCostCenter("");
  }, [newDept, newCostCenter]);

  // Remove cost center mapping
  const removeCostCenterMapping = useCallback((dept: string) => {
    setGlobals(prev => {
      const newMap = { ...prev.cost_center_map };
      delete newMap[dept];
      return { ...prev, cost_center_map: newMap };
    });
  }, []);

  // Submit handler - syncs globals to agent state and sends "Begin" to trigger pipeline
  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    startPipeline(globals);
  }, [canSubmit, globals, startPipeline]);

  const isSetupPhase = state.status === "IDLE";
  const isRunning = state.status !== "IDLE" && state.status !== "COMPLETED" && state.status !== "FAILED";

  return (
    <div className="flex flex-col h-full bg-white p-4">
      {/* Compact Status Summary Bar */}
      <div className="flex items-center gap-4 mb-4 pb-4 border-b border-gray-100">
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${statusBadgeClasses(state.status)}`}
        >
          {STATUS_LABELS[state.status]}
        </span>

        {/* Compact metrics row */}
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <MetricPill
            icon={<UploadIcon className="h-3 w-3" />}
            label={state.file_name ?? "No file"}
            active={state.status === "UPLOADING"}
          />
          <MetricPill
            icon={<Database className="h-3 w-3" />}
            label={totalRows > 0 ? `${totalRows} rows` : "—"}
            active={state.status === "RUNNING" || state.status === "INGESTING"}
          />
          <MetricPill
            icon={<ShieldCheck className="h-3 w-3" />}
            label={errorCount > 0 || state.validation_complete ? `${errorCount} errors` : "—"}
            active={state.status === "VALIDATING"}
          />
          <MetricPill
            icon={<Wrench className="h-3 w-3" />}
            label={fixCount > 0 ? `${fixCount} fixes` : "—"}
            active={state.status === "FIXING" || state.status === "WAITING_FOR_USER"}
          />
          <MetricPill
            icon={<Package className="h-3 w-3" />}
            label={artifactCount > 0 ? `${artifactCount} files` : "—"}
            active={state.status === "PACKAGING"}
          />
        </div>
      </div>

      {/* Setup Phase: Upload + Globals + Submit (vertically stacked, centered) */}
      {isSetupPhase && (
        <div className="flex flex-col gap-4 max-w-xl mx-auto w-full">
          {/* File Upload Card */}
          <div className="rounded-lg border border-gray-300 bg-white p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileSpreadsheet className="h-5 w-5 text-burgundy-700" />
              <span className="font-semibold text-gray-800">File Upload</span>
              {hasFile && (
                <span className="ml-auto text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                  Ready
                </span>
              )}
            </div>

            {!hasFile ? (
              <button
                onClick={triggerUpload}
                className="w-full flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-burgundy-200 bg-burgundy-50 px-6 py-8 hover:border-burgundy-400 hover:bg-burgundy-100 transition-colors cursor-pointer"
              >
                <UploadIcon className="h-8 w-8 text-burgundy-700" />
                <div className="text-center">
                  <div className="text-sm font-medium text-gray-800">
                    Upload Spreadsheet
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    CSV or Excel (.xlsx)
                  </div>
                </div>
              </button>
            ) : (
              <div className="flex items-center gap-3 p-3 rounded-lg bg-emerald-50 border border-emerald-200">
                <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-800">
                    {state.file_name || state.uploaded_file}
                  </div>
                  <div className="text-xs text-gray-500">Ready for validation</div>
                </div>
                <button
                  onClick={triggerUpload}
                  className="text-xs text-burgundy-600 hover:text-burgundy-800"
                >
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Globals Configuration Card */}
          <div className="rounded-lg border border-gray-300 bg-white p-4">
            <div className="flex items-center gap-2 mb-3">
              <Building2 className="h-5 w-5 text-burgundy-700" />
              <span className="font-semibold text-gray-800">Run Configuration</span>
              {hasGlobals && (
                <span className="ml-auto text-xs text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">
                  Set
                </span>
              )}
            </div>

            <div className="space-y-4">
              {/* As Of Date */}
              <div>
                <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-1">
                  <Calendar className="h-3 w-3" />
                  As Of Date
                </label>
                <input
                  type="date"
                  value={globals.as_of}
                  onChange={(e) => updateGlobals({ as_of: e.target.value })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                />
                <p className="text-xs text-gray-400 mt-1">Transactions must be on or before this date</p>
              </div>

              {/* USD Rounding */}
              <div>
                <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-1">
                  <DollarSign className="h-3 w-3" />
                  USD Rounding
                </label>
                <select
                  value={globals.usd_rounding}
                  onChange={(e) => updateGlobals({ usd_rounding: e.target.value as UsdRounding })}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                >
                  <option value="cents">Cents (e.g., $12.34)</option>
                  <option value="whole">Whole Dollars (e.g., $12)</option>
                </select>
              </div>

              {/* Cost Center Mapping */}
              <div>
                <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-1">
                  <Building2 className="h-3 w-3" />
                  Cost Center Mapping
                  <span className="text-gray-400 font-normal">(optional)</span>
                </label>

                {/* Existing mappings */}
                {Object.keys(globals.cost_center_map).length > 0 && (
                  <div className="mb-2 space-y-1">
                    {Object.entries(globals.cost_center_map).map(([dept, code]) => (
                      <div
                        key={dept}
                        className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1"
                      >
                        <span className="font-medium text-gray-700">{dept}</span>
                        <span className="text-gray-400">→</span>
                        <span className="text-gray-600">{code}</span>
                        <button
                          onClick={() => removeCostCenterMapping(dept)}
                          className="ml-auto text-gray-400 hover:text-red-500"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add new mapping */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Department"
                    value={newDept}
                    onChange={(e) => setNewDept(e.target.value)}
                    className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                  />
                  <span className="text-gray-400 text-xs">→</span>
                  <input
                    type="text"
                    placeholder="Cost Center"
                    value={newCostCenter}
                    onChange={(e) => setNewCostCenter(e.target.value)}
                    className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-burgundy-500"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCostCenterMapping();
                      }
                    }}
                  />
                  <button
                    onClick={addCostCenterMapping}
                    disabled={!newDept.trim() || !newCostCenter.trim()}
                    className="p-1.5 rounded-md bg-burgundy-100 text-burgundy-700 hover:bg-burgundy-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`w-full flex items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-medium transition-colors ${
              canSubmit
                ? "bg-burgundy-800 text-white hover:bg-burgundy-700"
                : "bg-gray-100 text-gray-400 cursor-not-allowed"
            }`}
          >
            <Play className="h-4 w-4" />
            {!hasFile
              ? "Upload a file to start"
              : !hasGlobals
                ? "Configure run settings"
                : "Start Validation"}
          </button>
          {!canSubmit && (
            <p className="text-xs text-gray-400 text-center">
              {!hasFile
                ? "Please upload a CSV or Excel file"
                : "Ready to validate"}
            </p>
          )}
        </div>
      )}

      {/* Active card from pipeline state */}
      {card && <div className="w-full">{card}</div>}

      {/* Running state indicator */}
      {isRunning && !card && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-pulse mb-2">
              <div className="h-8 w-8 mx-auto rounded-full bg-burgundy-100 flex items-center justify-center">
                <div className="h-4 w-4 rounded-full bg-burgundy-500"></div>
              </div>
            </div>
            <div className="text-sm text-gray-500">Processing...</div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricPill({
  icon,
  label,
  active,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 rounded-full ${
        active
          ? "bg-burgundy-100 text-burgundy-700"
          : label !== "—"
            ? "bg-gray-100 text-gray-600"
            : "text-gray-400"
      }`}
    >
      {icon}
      <span className="truncate max-w-[100px]">{label}</span>
    </div>
  );
}
