/**
 * Shared TypeScript types matching backend PipelineState.
 */

export type PipelineStatus =
  | "IDLE"
  | "UPLOADING"
  | "RUNNING"
  | "VALIDATING"
  | "WAITING_FOR_USER"
  | "FIXING"
  | "TRANSFORMING"
  | "PACKAGING"
  | "COMPLETED"
  | "FAILED";

export interface ValidationError {
  row_index: number;
  row_data: Record<string, unknown>;
  errors: Array<{ field: string; error: string }>;
}

export interface FixRequest {
  row_index: number;
  field: string;
  current_value: string;
  error_message: string;
}

export interface AgentState {
  status: PipelineStatus;
  active_run_id: string | null;
  file_path: string | null;
  file_name: string | null;
  uploaded_file: string | null;
  dataframe_records: Record<string, unknown>[];
  dataframe_columns: string[];
  validation_errors: ValidationError[];
  validation_complete: boolean;
  pending_fixes: FixRequest[];
  artifacts: Record<string, string>;
  as_of: string | null;
  usd_rounding: "cents" | "whole" | null;
  cost_center_map: Record<string, string>;
}

export const DEFAULT_INITIAL_STATE: AgentState = {
  status: "IDLE",
  active_run_id: null,
  file_path: null,
  file_name: null,
  uploaded_file: null,
  dataframe_records: [],
  dataframe_columns: [],
  validation_errors: [],
  validation_complete: false,
  pending_fixes: [],
  artifacts: {},
  as_of: null,
  usd_rounding: "cents",
  cost_center_map: {},
};
