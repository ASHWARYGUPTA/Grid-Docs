import { describe, expect, it, beforeEach } from "vitest";
import { addRecentReport, getOrCreateUserRef, readRecentReports } from "@/lib/citizen-storage";

describe("citizen-storage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("creates a user_ref once and returns the same one on subsequent calls", () => {
    const first = getOrCreateUserRef();
    const second = getOrCreateUserRef();
    expect(first).toBe(second);
    expect(first).toMatch(/^CTZUSER-/);
  });

  it("caps recent reports at 5, dropping the oldest", () => {
    for (let i = 0; i < 7; i++) {
      addRecentReport({ report_id: `CTZ-${i}`, corridor: "Mysore Road", created_at: `t${i}` });
    }
    const reports = readRecentReports();
    expect(reports).toHaveLength(5);
    expect(reports[0].report_id).toBe("CTZ-6");
    expect(reports.map((r) => r.report_id)).not.toContain("CTZ-0");
    expect(reports.map((r) => r.report_id)).not.toContain("CTZ-1");
  });
});
