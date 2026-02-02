import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Scaffold", () => {
  it("package.json exists", () => {
    const pkg = path.resolve(__dirname, "../../package.json");
    expect(fs.existsSync(pkg)).toBe(true);
  });

  it("has @copilotkit/react-core dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@copilotkit/react-core"]).toBeDefined();
  });

  it("has @ag-ui/client dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@ag-ui/client"]).toBeDefined();
  });

  it("does NOT have @copilotkit/a2ui-renderer dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@copilotkit/a2ui-renderer"]).toBeUndefined();
  });

  it("does NOT have @a2ui/lit dependency", () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.resolve(__dirname, "../../package.json"), "utf8")
    );
    expect(pkg.dependencies["@a2ui/lit"]).toBeUndefined();
  });

  it("layout.tsx exists", () => {
    const layout = path.resolve(__dirname, "../app/layout.tsx");
    expect(fs.existsSync(layout)).toBe(true);
  });
});
