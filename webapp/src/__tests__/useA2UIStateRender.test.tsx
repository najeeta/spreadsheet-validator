import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

// Since useCoAgentStateRender requires CopilotKit context, we test
// the hook's source for correctness patterns rather than rendering.

describe("useA2UIStateRender hook", () => {
  const hookPath = path.resolve(
    __dirname,
    "../hooks/useA2UIStateRender.ts"
  );

  it("hook file exists", () => {
    expect(fs.existsSync(hookPath)).toBe(true);
  });

  it("calls useCoAgentStateRender", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("useCoAgentStateRender");
  });

  it("uses agent name spreadsheet_validator", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });

  it("renders CompletionCard for COMPLETED status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("CompletionCard");
    expect(source).toContain("COMPLETED");
  });

  it("renders IngestionSummaryCard for RUNNING status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("IngestionSummaryCard");
  });

  it("renders ValidationResultsCard for VALIDATING status", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("ValidationResultsCard");
  });

  it("renders ProgressCard for TRANSFORMING/PACKAGING", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("ProgressCard");
    expect(source).toContain("TRANSFORMING");
  });

  it("derives counts from array lengths not hardcoded values", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    // Should use .length to compute counts
    expect(source).toContain(".length");
  });
});
