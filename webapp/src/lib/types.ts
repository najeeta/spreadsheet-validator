/**
 * Shared TypeScript types matching backend PipelineState.
 */

export type PipelineStatus =
  | "IDLE"
  | "UPLOADING"
  | "INGESTING"
  | "RUNNING"
  | "VALIDATING"
  | "WAITING_FOR_USER"
  | "FIXING"
  | "TRANSFORMING"
  | "PACKAGING"
  | "COMPLETED"
  | "FAILED";

export type UsdRounding = "cents" | "whole";

export interface CostCenterMapping {
  [department: string]: string; // dept → cost_center_code
}

export interface RunGlobals {
  as_of: string; // ISO date string (YYYY-MM-DD)
  usd_rounding: UsdRounding;
  cost_center_map: CostCenterMapping;
}

export interface FixRequest {
  row_index: number;
  field: string;
  current_value: string;
  error_message: string;
}

export interface AgentState {
  status: PipelineStatus;
  file_name: string | null;
  // User-provided globals for the run
  globals?: RunGlobals;
  // Data fields are optional - they're set by the backend only
  // and should NOT be in the initial state to avoid overwriting backend data
  dataframe_records?: Record<string, unknown>[];
  dataframe_columns?: string[];
  pending_fixes?: FixRequest[];
  skipped_fixes?: FixRequest[];
  waiting_since?: number;
  total_error_rows?: number;
  artifacts?: Record<string, string>;
  validation_errors?: unknown[];
  validation_complete?: boolean;
  uploaded_file?: string;
}

// Default globals with sensible defaults
export const DEFAULT_GLOBALS: RunGlobals = {
  as_of: new Date().toISOString().split("T")[0], // Today's date
  usd_rounding: "cents",
  cost_center_map: {},
};

// Initial state sent to CopilotKit - EXCLUDES data fields to prevent
// frontend state from overwriting backend data during ag-ui-adk sync
export const DEFAULT_INITIAL_STATE: AgentState = {
  status: "IDLE",
  file_name: null,
  globals: DEFAULT_GLOBALS,
  // NOTE: dataframe_records, dataframe_columns, pending_fixes,
  // artifacts are intentionally OMITTED here.
  // They are backend-only and will be received via SSE STATE_DELTA events.
};
