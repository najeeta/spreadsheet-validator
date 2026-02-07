import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Main page (server component - redirects to run)", () => {
  const pagePath = path.resolve(__dirname, "../app/page.tsx");

  it("page.tsx exists", () => {
    expect(fs.existsSync(pagePath)).toBe(true);
  });

  it("is a server component (async function)", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("async function");
    expect(source).not.toContain("use client");
  });

  it("creates a run via POST /run", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("/run");
    expect(source).toContain("POST");
  });

  it("redirects to /runs/{runId}", () => {
    const source = fs.readFileSync(pagePath, "utf8");
    expect(source).toContain("redirect");
    expect(source).toContain("/runs/");
  });
});

describe("Run page (client component - main UI)", () => {
  const runPagePath = path.resolve(__dirname, "../app/runs/[runId]/page.tsx");

  it("run page exists", () => {
    expect(fs.existsSync(runPagePath)).toBe(true);
  });

  it("is a client component", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("use client");
  });

  it("uses useA2UIStateRender hook", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("useA2UIStateRender");
  });

  it("renders CopilotChat", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("CopilotChat");
  });

  it("uploads to /upload endpoint (via ValidatorContext)", () => {
    // Upload logic is in ValidatorContext, not the page itself
    const contextPath = path.resolve(__dirname, "../contexts/ValidatorContext.tsx");
    const source = fs.readFileSync(contextPath, "utf8");
    expect(source).toContain("/upload");
  });

  it("accepts csv and xlsx files (via ValidatorContext)", () => {
    // File input is in ValidatorContext, not the page itself
    const contextPath = path.resolve(__dirname, "../contexts/ValidatorContext.tsx");
    const source = fs.readFileSync(contextPath, "utf8");
    expect(source).toContain(".csv");
    expect(source).toContain(".xlsx");
  });

  it("passes agent spreadsheet_validator", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });

  it("imports StateCanvas component", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("StateCanvas");
  });

  it("uses two-panel flex layout", () => {
    const source = fs.readFileSync(runPagePath, "utf8");
    expect(source).toContain("flex h-screen");
    expect(source).toContain('w-[400px]');
  });
});
