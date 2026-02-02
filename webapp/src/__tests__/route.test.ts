import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("CopilotKit API Route", () => {
  const routePath = path.resolve(
    __dirname,
    "../app/api/copilotkit/[[...handle]]/route.ts"
  );

  it("route.ts exists", () => {
    expect(fs.existsSync(routePath)).toBe(true);
  });

  it("exports GET handler", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toMatch(/export\s+.*GET/);
  });

  it("exports POST handler", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toMatch(/export\s+.*POST/);
  });

  it("uses HttpAgent", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("HttpAgent");
  });

  it("uses CopilotRuntime", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("CopilotRuntime");
  });

  it("agent key is spreadsheet_validator", () => {
    const source = fs.readFileSync(routePath, "utf8");
    expect(source).toContain("spreadsheet_validator");
  });
});
