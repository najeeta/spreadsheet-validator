"use client";

import { ProgressCard } from "@/components/a2ui/ProgressCard";
import { CompletionCard } from "@/components/a2ui/CompletionCard";
import { FixesTable } from "@/components/a2ui/FixesTable";
import { UploadCard } from "@/components/a2ui/UploadCard";
import type { AgentState } from "@/lib/types";

/**
 * Maps agent state to the appropriate card component.
 * Extracted from useA2UIStateRender so both the hook and
 * StateCanvas can share this logic.
 */
export function renderForState(state: AgentState): React.ReactElement | null {
  if (!state) return null;

  const totalRows = state.dataframe_records?.length ?? 0;
  const pendingFixes = state.pending_fixes ?? [];
  const skippedFixes = state.skipped_fixes ?? [];

  // Count unique error rows from skipped fixes (mirrors package_results logic)
  const skippedRowIndices = new Set(skippedFixes.map((f) => f.row_index));
  const errorCount =
    pendingFixes.length > 0
      ? pendingFixes.length
      : skippedRowIndices.size;
  const validCount = totalRows - errorCount;
  const fixedCount = pendingFixes.length;

  switch (state.status) {
    case "COMPLETED":
      return (
        <CompletionCard
          totalRows={totalRows}
          validCount={validCount}
          errorCount={errorCount}
          fixedCount={fixedCount}
          artifactNames={Object.keys(state.artifacts ?? {})}
        />
      );

    case "TRANSFORMING":
    case "PACKAGING":
      return (
        <ProgressCard
          phaseName={
            state.status === "TRANSFORMING"
              ? "Transforming data..."
              : "Packaging results..."
          }
        />
      );

    case "WAITING_FOR_USER":
      if (pendingFixes.length > 0) {
        return (
          <FixesTable
            pendingFixes={pendingFixes}
            waitingSince={state.waiting_since}
            totalErrorRows={state.total_error_rows}
          />
        );
      }
      return null;

    case "FIXING":
      if (pendingFixes.length > 0) {
        return (
          <FixesTable
            pendingFixes={pendingFixes}
            waitingSince={state.waiting_since}
            totalErrorRows={state.total_error_rows}
          />
        );
      }
      return null;

    case "VALIDATING":
      return null;

    case "UPLOADING":
      if (totalRows === 0) {
        return <UploadCard />;
      }
      return <ProgressCard phaseName="Processing upload..." />;

    case "INGESTING":
      return <ProgressCard phaseName="Ingesting spreadsheet..." />;

    case "RUNNING":
      return null;

    default:
      return null;
  }
}

// Alias for backward compatibility
export const renderCardForState = renderForState;
