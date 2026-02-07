"use client";

import { CompletionCard } from "@/components/a2ui/CompletionCard";
import { FixesTable } from "@/components/a2ui/FixesTable";
import { ProcessingSkeleton } from "@/components/a2ui/ProcessingSkeleton";
import type { AgentState } from "@/lib/types";

/**
 * Maps agent state to the appropriate card component.
 * Extracted from useA2UIStateRender so both the hook and
 * StateCanvas can share this logic.
 */
export function renderForState(state: AgentState): React.ReactElement | null {
  if (!state) return null;

  const totalRows = state.dataframe_records?.length ?? 0;
  const pendingReview = state.pending_review ?? [];
  const allErrors = state.all_errors ?? [];
  const skippedRows = state.skipped_rows ?? [];

  // Count unique error rows from all_errors and skipped_rows
  const totalErrorRows = new Set(allErrors.map((e) => e.row_index)).size;
  const skippedRowCount = skippedRows.length;
  const errorCount =
    pendingReview.length > 0
      ? pendingReview.length
      : skippedRowCount;
  const validCount = totalRows - errorCount;
  const fixedCount = pendingReview.length;

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
      return <ProcessingSkeleton />;

    case "WAITING_FOR_USER":
      if (pendingReview.length > 0) {
        return (
          <FixesTable
            pendingReview={pendingReview}
            waitingSince={state.waiting_since}
            totalErrorRows={totalErrorRows}
          />
        );
      }
      return null;

    case "VALIDATING":
      return null;

    case "INGESTING":
    case "RUNNING":
      return <ProcessingSkeleton />;

    default:
      return null;
  }
}

// Alias for backward compatibility
export const renderCardForState = renderForState;
