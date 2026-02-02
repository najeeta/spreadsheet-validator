import { describe, it, expect } from "vitest";
import { DEFAULT_INITIAL_STATE } from "@/lib/types";
import type { PipelineStatus } from "@/lib/types";

describe("AgentState types", () => {
  it("DEFAULT_INITIAL_STATE has status IDLE", () => {
    expect(DEFAULT_INITIAL_STATE.status).toBe("IDLE");
  });

  it("DEFAULT_INITIAL_STATE has empty dataframe_records", () => {
    expect(DEFAULT_INITIAL_STATE.dataframe_records).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty dataframe_columns", () => {
    expect(DEFAULT_INITIAL_STATE.dataframe_columns).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty validation_errors", () => {
    expect(DEFAULT_INITIAL_STATE.validation_errors).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty pending_fixes", () => {
    expect(DEFAULT_INITIAL_STATE.pending_fixes).toEqual([]);
  });

  it("DEFAULT_INITIAL_STATE has empty artifacts", () => {
    expect(DEFAULT_INITIAL_STATE.artifacts).toEqual({});
  });

  it("DEFAULT_INITIAL_STATE has validation_complete false", () => {
    expect(DEFAULT_INITIAL_STATE.validation_complete).toBe(false);
  });

  it("DEFAULT_INITIAL_STATE has usd_rounding cents", () => {
    expect(DEFAULT_INITIAL_STATE.usd_rounding).toBe("cents");
  });

  it("PipelineStatus type allows all 10 values", () => {
    // TypeScript compile-time check — runtime assertion
    const statuses: PipelineStatus[] = [
      "IDLE",
      "UPLOADING",
      "RUNNING",
      "VALIDATING",
      "WAITING_FOR_USER",
      "FIXING",
      "TRANSFORMING",
      "PACKAGING",
      "COMPLETED",
      "FAILED",
    ];
    expect(statuses).toHaveLength(10);
  });
});
