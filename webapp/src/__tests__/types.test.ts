import { describe, it, expect } from "vitest";
import { DEFAULT_INITIAL_STATE, DEFAULT_GLOBALS } from "@/lib/types";
import type { PipelineStatus } from "@/lib/types";

describe("AgentState types", () => {
  it("DEFAULT_INITIAL_STATE has status IDLE", () => {
    expect(DEFAULT_INITIAL_STATE.status).toBe("IDLE");
  });

  it("DEFAULT_INITIAL_STATE has file_name null", () => {
    expect(DEFAULT_INITIAL_STATE.file_name).toBeNull();
  });

  it("DEFAULT_INITIAL_STATE has globals with defaults", () => {
    expect(DEFAULT_INITIAL_STATE.globals).toBeDefined();
    expect(DEFAULT_INITIAL_STATE.globals?.usd_rounding).toBe("cents");
    expect(DEFAULT_INITIAL_STATE.globals?.cost_center_map).toEqual({});
  });

  it("DEFAULT_INITIAL_STATE omits data fields (backend-only)", () => {
    // These fields are intentionally NOT in DEFAULT_INITIAL_STATE
    // to prevent frontend state from overwriting backend data during ag-ui-adk sync
    expect(DEFAULT_INITIAL_STATE.dataframe_records).toBeUndefined();
    expect(DEFAULT_INITIAL_STATE.dataframe_columns).toBeUndefined();
    expect(DEFAULT_INITIAL_STATE.pending_fixes).toBeUndefined();
    expect(DEFAULT_INITIAL_STATE.artifacts).toBeUndefined();
  });

  it("DEFAULT_GLOBALS has sensible defaults", () => {
    expect(DEFAULT_GLOBALS.usd_rounding).toBe("cents");
    expect(DEFAULT_GLOBALS.cost_center_map).toEqual({});
    expect(DEFAULT_GLOBALS.as_of).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("PipelineStatus type allows all 11 values", () => {
    // TypeScript compile-time check — runtime assertion
    const statuses: PipelineStatus[] = [
      "IDLE",
      "UPLOADING",
      "INGESTING",
      "RUNNING",
      "VALIDATING",
      "WAITING_FOR_USER",
      "FIXING",
      "TRANSFORMING",
      "PACKAGING",
      "COMPLETED",
      "FAILED",
    ];
    expect(statuses).toHaveLength(11);
  });
});
