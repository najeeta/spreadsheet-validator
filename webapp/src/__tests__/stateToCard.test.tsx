import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import fs from "fs";
import path from "path";
import type { AgentState, FixRequest } from "@/lib/types";

// Mock CopilotKit modules that transitively import katex CSS
const mockAppendMessage = vi.fn().mockResolvedValue(undefined);
vi.mock("@copilotkit/react-core", () => ({
  useCopilotChat: () => ({ appendMessage: mockAppendMessage }),
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

// Mock ValidatorContext used by UploadCard
vi.mock("@/contexts/ValidatorContext", () => ({
  useValidator: () => ({
    threadId: "test-thread",
    setThreadId: vi.fn(),
  }),
}));

// Import after mocks are set up
import { renderForState, renderCardForState } from "@/lib/stateToCard";

describe("stateToCard", () => {
  const filePath = path.resolve(__dirname, "../lib/stateToCard.tsx");

  it("file exists", () => {
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("imports all card components", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("ProgressCard");
    expect(source).toContain("CompletionCard");
    expect(source).toContain("FixesTable");
    expect(source).toContain("UploadCard");
  });

  it("exports renderForState and renderCardForState", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("export function renderForState");
    expect(source).toContain("export const renderCardForState");
  });

  it("references all pipeline status values", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("COMPLETED");
    expect(source).toContain("TRANSFORMING");
    expect(source).toContain("PACKAGING");
    expect(source).toContain("WAITING_FOR_USER");
    expect(source).toContain("VALIDATING");
    expect(source).toContain("FIXING");
    expect(source).toContain("UPLOADING");
    expect(source).toContain("INGESTING");
    expect(source).toContain("RUNNING");
  });

  it("imports AgentState type", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("AgentState");
  });

  it("renderCardForState is an alias for renderForState", () => {
    expect(renderCardForState).toBe(renderForState);
  });
});

describe("renderForState — INGESTING", () => {
  it("renders a ProgressCard for INGESTING status", () => {
    const state: AgentState = {
      status: "INGESTING",
      file_name: "test.csv",
    };

    const element = renderForState(state);
    expect(element).not.toBeNull();

    render(element!);
    expect(screen.getByText("Ingesting spreadsheet...")).toBeInTheDocument();
  });
});

describe("renderForState — COMPLETED with skipped_fixes", () => {
  function makeRows(n: number): Record<string, unknown>[] {
    return Array.from({ length: n }, (_, i) => ({ id: i }));
  }

  it("shows correct counts when skipped_fixes is present", () => {
    const skippedFixes: FixRequest[] = [
      { row_index: 3, field: "amount", current_value: "-1", error_message: "negative" },
      { row_index: 7, field: "date", current_value: "bad", error_message: "invalid date" },
    ];

    const state: AgentState = {
      status: "COMPLETED",
      file_name: "test.csv",
      dataframe_records: makeRows(15),
      pending_fixes: [],
      skipped_fixes: skippedFixes,
      artifacts: { "success.xlsx": "success.xlsx", "errors.xlsx": "errors.xlsx" },
    };

    const element = renderForState(state);
    expect(element).not.toBeNull();

    render(element!);

    // Total = 15, Valid = 13, Errors = 2, Fixed = 0
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("deduplicates skipped_fixes by row_index", () => {
    // Two errors on the same row should count as 1 error row
    const skippedFixes: FixRequest[] = [
      { row_index: 5, field: "amount", current_value: "-1", error_message: "negative" },
      { row_index: 5, field: "date", current_value: "bad", error_message: "invalid date" },
      { row_index: 9, field: "name", current_value: "", error_message: "empty" },
    ];

    const state: AgentState = {
      status: "COMPLETED",
      file_name: "test.csv",
      dataframe_records: makeRows(10),
      pending_fixes: [],
      skipped_fixes: skippedFixes,
      artifacts: { "success.xlsx": "s" },
    };

    const element = renderForState(state);
    render(element!);

    // 2 unique error rows (indices 5 and 9), not 3
    expect(screen.getByText("10")).toBeInTheDocument(); // total
    expect(screen.getByText("8")).toBeInTheDocument();  // valid = 10 - 2
  });

  it("shows all valid when no skipped_fixes", () => {
    const state: AgentState = {
      status: "COMPLETED",
      file_name: "test.csv",
      dataframe_records: makeRows(5),
      pending_fixes: [],
      skipped_fixes: [],
      artifacts: { "success.xlsx": "s" },
    };

    const element = renderForState(state);
    render(element!);

    // Total = 5, Valid = 5 (same value appears twice), Errors = 0, Fixed = 0
    const fives = screen.getAllByText("5");
    expect(fives).toHaveLength(2); // total + valid
    const zeros = screen.getAllByText("0");
    expect(zeros).toHaveLength(2); // errors + fixed
  });

  it("shows all valid when skipped_fixes is undefined", () => {
    const state: AgentState = {
      status: "COMPLETED",
      file_name: "test.csv",
      dataframe_records: makeRows(8),
      pending_fixes: [],
      artifacts: {},
    };

    const element = renderForState(state);
    render(element!);

    // Total = 8, Valid = 8 (same value appears twice)
    const eights = screen.getAllByText("8");
    expect(eights).toHaveLength(2); // total + valid
  });
});
