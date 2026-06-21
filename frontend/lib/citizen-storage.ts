const USER_REF_KEY = "citizen-user-ref";
const SUBSCRIPTIONS_KEY = "citizen-subscriptions";
const RECENT_REPORTS_KEY = "citizen-recent-reports";
const RECENT_REPORTS_MAX = 5;

export function getOrCreateUserRef(): string {
  if (typeof localStorage === "undefined") return "anon";
  try {
    const existing = localStorage.getItem(USER_REF_KEY);
    if (existing) return existing;
    const created = `CTZUSER-${crypto.randomUUID()}`;
    localStorage.setItem(USER_REF_KEY, created);
    return created;
  } catch {
    return "anon";
  }
}

export interface StoredSubscription {
  subscription_id: string;
  corridors: string[];
}

export function readSubscriptions(): StoredSubscription[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(SUBSCRIPTIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function writeSubscriptions(subscriptions: StoredSubscription[]): void {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(SUBSCRIPTIONS_KEY, JSON.stringify(subscriptions));
  } catch {
    // storage full or unavailable — best-effort only
  }
}

export interface StoredReport {
  report_id: string;
  corridor: string | null;
  created_at: string;
}

export function readRecentReports(): StoredReport[] {
  if (typeof localStorage === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_REPORTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function addRecentReport(report: StoredReport): void {
  if (typeof localStorage === "undefined") return;
  try {
    const existing = readRecentReports();
    const updated = [report, ...existing].slice(0, RECENT_REPORTS_MAX);
    localStorage.setItem(RECENT_REPORTS_KEY, JSON.stringify(updated));
  } catch {
    // storage full or unavailable — best-effort only
  }
}
