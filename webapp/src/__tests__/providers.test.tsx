import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Providers", () => {
  it("does not use renderActivityMessages prop", () => {
    const source = fs.readFileSync(
      path.resolve(__dirname, "../app/Providers.tsx"),
      "utf8"
    );
    expect(source).not.toContain("renderActivityMessages");
  });

  it("has CopilotKitProvider with runtimeUrl in run page", () => {
    // CopilotKitProvider is now in the runs/[runId]/page.tsx client component
    const source = fs.readFileSync(
      path.resolve(__dirname, "../app/runs/[runId]/page.tsx"),
      "utf8"
    );
    expect(source).toContain("CopilotKitProvider");
    expect(source).toContain("/api/copilotkit");
  });
});
