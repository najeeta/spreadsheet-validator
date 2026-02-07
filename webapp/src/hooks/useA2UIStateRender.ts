"use client";

import { useCoAgentStateRender } from "@copilotkit/react-core";
import type { AgentState } from "@/lib/types";

/**
 * Hook that subscribes to agent state changes via CopilotKit.
 * Cards are now rendered in StateCanvas via useCoAgent, so
 * the render function returns null (no cards in the chat stream).
 */
export function useA2UIStateRender() {
  useCoAgentStateRender<AgentState>({
    name: "spreadsheet_validator",
    render: () => {
      return null;
    },
  });
}
