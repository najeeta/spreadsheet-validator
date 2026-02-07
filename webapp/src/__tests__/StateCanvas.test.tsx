import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("StateCanvas", () => {
  const filePath = path.resolve(
    __dirname,
    "../components/StateCanvas.tsx"
  );

  it("file exists", () => {
    expect(fs.existsSync(filePath)).toBe(true);
  });

  it("uses useValidator hook from context", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("useValidator");
  });

  it("gets agent state and startPipeline from context", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("agentState");
    expect(source).toContain("startPipeline");
  });

  it("imports renderForState from stateToCard", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("renderForState");
    expect(source).toContain("stateToCard");
  });

  it("uses DEFAULT_INITIAL_STATE", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("DEFAULT_INITIAL_STATE");
  });

  it("exports StateCanvas component", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("export function StateCanvas");
  });

  it("shows pipeline metrics as pills", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("MetricPill");
    expect(source).toContain("totalRows");
    expect(source).toContain("columnCount");
    expect(source).toContain("errorCount");
    expect(source).toContain("fixCount");
    expect(source).toContain("artifactCount");
  });

  it("supports globals configuration", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("as_of");
    expect(source).toContain("usd_rounding");
    expect(source).toContain("cost_center_map");
  });

  it("includes status badge with all pipeline status labels", () => {
    const source = fs.readFileSync(filePath, "utf8");
    expect(source).toContain("STATUS_LABELS");
    expect(source).toContain("IDLE");
    expect(source).toContain("COMPLETED");
    expect(source).toContain("FAILED");
  });
});
