import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FixesTable } from "@/components/a2ui/FixesTable";
import type { FixRequest } from "@/lib/types";

// Mock useCopilotChat
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

const SAMPLE_FIXES: FixRequest[] = [
  {
    row_index: 2,
    field: "dept",
    current_value: "SALES",
    error_message:
      "Invalid department 'SALES'. Must be one of: ['ENG', 'FIN', 'HR', 'OPS'].",
  },
  {
    row_index: 2,
    field: "amount",
    current_value: "-100",
    error_message: "Amount -100 out of range. Must be > 0 and <= 100,000.",
  },
  {
    row_index: 5,
    field: "currency",
    current_value: "XYZ",
    error_message:
      "Invalid currency 'XYZ'. Must be one of: ['EUR', 'GBP', 'INR', 'USD'].",
  },
];

describe("FixesTable", () => {
  beforeEach(() => {
    mockAppendMessage.mockClear();
  });

  it("groups fixes by row and shows row numbers", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    // Row numbers displayed as plain numbers (header says "Row")
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("displays error messages in sub-rows", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    expect(
      screen.getByText(/Invalid department 'SALES'/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Amount -100 out of range/)).toBeInTheDocument();
    expect(screen.getByText(/Invalid currency 'XYZ'/)).toBeInTheDocument();
  });

  it("displays current values", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    expect(screen.getByText("SALES")).toBeInTheDocument();
    expect(screen.getByText("-100")).toBeInTheDocument();
    expect(screen.getByText("XYZ")).toBeInTheDocument();
  });

  it("renders Fix and Skip buttons per row group via aria-labels", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    expect(screen.getByRole("button", { name: "Fix Row 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip Row 2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fix Row 5" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip Row 5" })).toBeInTheDocument();
  });

  it("renders input fields for each fix", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    const inputs = screen.getAllByRole("textbox");
    // 3 fixes = 3 inputs
    expect(inputs).toHaveLength(3);
  });

  it("skip row sends skip message", async () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    const skipBtn = screen.getByRole("button", { name: "Skip Row 2" });
    fireEvent.click(skipBtn);
    // Wait for async
    await vi.waitFor(() => {
      expect(mockAppendMessage).toHaveBeenCalledTimes(1);
    });
    const msg = mockAppendMessage.mock.calls[0][0];
    expect(msg.content).toBe("Skip row 2");
  });

  it("fix row sends batch fix message with filled values", async () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    const inputs = screen.getAllByRole("textbox");
    // Fill in the dept fix for row 2
    fireEvent.change(inputs[0], { target: { value: "ENG" } });

    const fixBtn = screen.getByRole("button", { name: "Fix Row 2" });
    fireEvent.click(fixBtn);

    await vi.waitFor(() => {
      expect(mockAppendMessage).toHaveBeenCalledTimes(1);
    });
    const msg = mockAppendMessage.mock.calls[0][0];
    expect(msg.content).toContain("Batch fix row 2");
    expect(msg.content).toContain('dept="ENG"');
  });

  it("renders batch label with totalErrorRows", () => {
    render(
      <FixesTable
        pendingReview={SAMPLE_FIXES}
        totalErrorRows={20}
      />,
    );
    expect(screen.getByText(/Fixing 2 of 20 error rows/)).toBeInTheDocument();
  });

  it("renders skip all link", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    expect(screen.getByText("Skip all")).toBeInTheDocument();
  });

  it("skip all sends skip message", async () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    const skipAll = screen.getByText("Skip all");
    fireEvent.click(skipAll);

    await vi.waitFor(() => {
      expect(mockAppendMessage).toHaveBeenCalledTimes(1);
    });
    const msg = mockAppendMessage.mock.calls[0][0];
    expect(msg.content).toBe("Skip remaining fixes and continue");
  });

  it("renders timer when waitingSince is provided", () => {
    // Set waitingSince to 10 seconds ago
    const tenSecondsAgo = Date.now() / 1000 - 10;
    render(
      <FixesTable
        pendingReview={SAMPLE_FIXES}
        waitingSince={tenSecondsAgo}
      />,
    );
    // Should show seconds remaining (around 20s)
    expect(screen.getByText(/\d+s/)).toBeInTheDocument();
  });

  it("resets countdown when waitingSince changes", () => {
    // Start with 10 seconds elapsed (20s remaining)
    const tenSecondsAgo = Date.now() / 1000 - 10;
    const { rerender } = render(
      <FixesTable
        pendingReview={SAMPLE_FIXES}
        waitingSince={tenSecondsAgo}
      />,
    );
    // Should show ~20s remaining
    expect(screen.getByText(/20s/)).toBeInTheDocument();

    // Simulate a fix applied — backend resets waitingSince to now
    const justNow = Date.now() / 1000;
    rerender(
      <FixesTable
        pendingReview={SAMPLE_FIXES}
        waitingSince={justNow}
      />,
    );
    // Timer should reset to ~30s
    expect(screen.getByText(/30s/)).toBeInTheDocument();
  });

  it("shows header with fix count", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    // 3 active fixes total
    expect(screen.getByText(/Fixes Needed \(3\)/)).toBeInTheDocument();
  });

  it("renders table headers including Current column", () => {
    render(<FixesTable pendingReview={SAMPLE_FIXES} />);
    expect(screen.getByText("Row")).toBeInTheDocument();
    expect(screen.getByText("Field")).toBeInTheDocument();
    expect(screen.getByText("Current")).toBeInTheDocument();
    expect(screen.getByText("New Value")).toBeInTheDocument();
  });
});
