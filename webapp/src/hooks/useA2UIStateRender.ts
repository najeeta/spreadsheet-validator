"use client";

import { useCoAgentStateRender } from "@copilotkit/react-core";
import { IngestionSummaryCard } from "@/components/a2ui/IngestionSummaryCard";
import { ValidationResultsCard } from "@/components/a2ui/ValidationResultsCard";
import { ProgressCard } from "@/components/a2ui/ProgressCard";
import { CompletionCard } from "@/components/a2ui/CompletionCard";
import type { AgentState } from "@/lib/types";
import { createElement } from "react";

/**
 * Hook that subscribes to agent state changes and renders
 * the appropriate card component based on pipeline status.
 *
 * This is the core of Plan A's state-driven rendering approach.
 * No A2UI protocol — just state transitions mapped to React cards.
 */
export function useA2UIStateRender() {
  useCoAgentStateRender<AgentState>({
    name: "spreadsheet_validator",
    render: ({ state }) => {
      if (!state) return null;

      const totalRows = state.dataframe_records?.length ?? 0;
      const errorCount = state.validation_errors?.length ?? 0;
      const validCount = totalRows - errorCount;
      const fixedCount = state.pending_fixes?.length ?? 0;
      const columns = state.dataframe_columns ?? [];

      switch (state.status) {
        case "COMPLETED":
          return createElement(CompletionCard, {
            totalRows,
            validCount,
            errorCount,
            fixedCount,
            artifactNames: Object.keys(state.artifacts ?? {}),
          });

        case "TRANSFORMING":
        case "PACKAGING":
          return createElement(ProgressCard, {
            phaseName:
              state.status === "TRANSFORMING"
                ? "Transforming data..."
                : "Packaging results...",
          });

        case "VALIDATING":
        case "FIXING":
        case "WAITING_FOR_USER":
          if (totalRows > 0) {
            return createElement(ValidationResultsCard, {
              totalRows,
              validCount,
              errorCount,
            });
          }
          return null;

        case "RUNNING":
          if (totalRows > 0) {
            return createElement(IngestionSummaryCard, {
              fileName: state.file_name ?? "Unknown",
              rowCount: totalRows,
              columnCount: columns.length,
              columns,
            });
          }
          return null;

        default:
          return null;
      }
    },
  });
}
