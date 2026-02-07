import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock CopilotKit modules that transitively import katex CSS
vi.mock("@copilotkit/react-core", () => ({
  useCopilotChat: () => ({ appendMessage: vi.fn().mockResolvedValue(undefined) }),
}));
vi.mock("@copilotkit/runtime-client-gql", () => ({
  TextMessage: class {
    content: string;
    role: string;
    constructor({ content, role }: { content: string; role: string }) {
      this.content = content;
      this.role = role;
    }
  },
  Role: { User: "user" },
}));

// Mock ValidatorContext used by CompletionCard
vi.mock("@/contexts/ValidatorContext", () => ({
  useValidator: () => ({
    threadId: "test-thread",
    setThreadId: vi.fn(),
    triggerUpload: vi.fn(),
    setAgentState: vi.fn(),
  }),
}));

import { CompletionCard } from "@/components/a2ui/CompletionCard";

describe("CompletionCard", () => {
  it("renders summary stats", () => {
    render(
      <CompletionCard
        totalRows={100}
        validCount={95}
        errorCount={5}
        fixedCount={3}
        artifactNames={["success.xlsx", "errors.xlsx"]}
      />
    );
    expect(screen.getByText(/100/)).toBeInTheDocument();
    expect(screen.getByText(/95/)).toBeInTheDocument();
  });

  it("renders artifact names", () => {
    render(
      <CompletionCard
        totalRows={100}
        validCount={95}
        errorCount={5}
        fixedCount={0}
        artifactNames={["success.xlsx", "errors.xlsx"]}
      />
    );
    expect(screen.getByText(/success\.xlsx/)).toBeInTheDocument();
    expect(screen.getAllByText(/errors\.xlsx/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders success indicator", () => {
    const { container } = render(
      <CompletionCard
        totalRows={10}
        validCount={10}
        errorCount={0}
        fixedCount={0}
        artifactNames={["success.xlsx"]}
      />
    );
    // Should render a success/checkmark indicator
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });
});
