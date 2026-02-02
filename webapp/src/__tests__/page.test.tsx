import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Main page", () => {
  const pagePath = path.resolve(__dirname, "../app/page.tsx");

  it("page.tsx exists", () => {
    expect(fs.existsSync(pagePath)).toBe(true);
  });

  it("is a client component", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("use client");
  });

  it("generates threadId", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("threadId");
    expect(source).toContain("randomUUID");
  });

  it("uses useA2UIStateRender hook", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("useA2UIStateRender");
  });

  it("renders CopilotChat or similar chat component", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    // Should use CopilotChat or CopilotPopup
    expect(
      source.includes("CopilotChat") || source.includes("CopilotPopup"),
    ).toBe(true);
  });

  it("uploads to /upload endpoint", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("/upload");
  });

  it("accepts csv and xlsx files", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain(".csv");
    expect(source).toContain(".xlsx");
  });

  it("passes agentId spreadsheet_validator", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });
});
