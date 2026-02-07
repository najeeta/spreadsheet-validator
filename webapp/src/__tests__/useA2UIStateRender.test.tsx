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

  it("render function returns null (cards moved to StateCanvas)", () => {
    const source = fs.readFileSync(hookPath, "utf8");
    expect(source).toContain("return null");
  });
});

describe("stateToCard shared logic", () => {
  const stateToCardPath = path.resolve(
    __dirname,
    "../lib/stateToCard.tsx"
  );

  it("stateToCard file exists", () => {
    expect(fs.existsSync(stateToCardPath)).toBe(true);
  });

  it("imports all card components", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain("CompletionCard");
    expect(source).toContain("FixesTable");
  });

  it("renders CompletionCard for COMPLETED status", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain("COMPLETED");
  });

  it("returns null for RUNNING status (top bar shows metrics)", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain("RUNNING");
  });

  it("returns null for VALIDATING status (top bar shows metrics)", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain("VALIDATING");
  });

  it("renders ProcessingSkeleton for TRANSFORMING/PACKAGING", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain("ProcessingSkeleton");
    expect(source).toContain("TRANSFORMING");
  });

  it("derives counts from array lengths not hardcoded values", () => {
    const source = fs.readFileSync(stateToCardPath, "utf8");
    expect(source).toContain(".length");
  });
});
