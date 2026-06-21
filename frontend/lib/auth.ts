// ---------------------------------------------------------------------------
// Client-side RBAC — roles per PRD user stories
// ---------------------------------------------------------------------------
//
// Role definitions (from PRD):
//   commander  — Traffic Commander. Primary M15 user. Approves/rejects dispatch
//                recommendations, manages planned 72h event briefings, triages
//                citizen reports. Cannot touch tier control or model promotion.
//   admin      — Platform Governance Admin. Everything a commander can do, plus:
//                manual tier override, shadow mode toggle, cascade drill trigger,
//                model promotion approval (PRD user stories 19–22).
//   dispatcher — Field Officer / Station Dispatcher. Read-only access on M15;
//                primary interface is M16 (FieldOfficerApp, not yet built).
//                Needs tier status visibility and queue awareness.
// ---------------------------------------------------------------------------

export type Role = "commander" | "admin" | "dispatcher";

export interface AuthUser {
  email: string;
  name: string;
  role: Role;
}

const STORAGE_KEY = "gridunlocked_session";

interface DemoUser extends AuthUser {
  password: string;
}

const DEMO_USERS: DemoUser[] = [
  {
    email: "commander@gridunlocked.in",
    password: "demo-cmd",
    name: "Traffic Commander",
    role: "commander",
  },
  {
    email: "admin@gridunlocked.in",
    password: "demo-admin",
    name: "Platform Admin",
    role: "admin",
  },
  {
    email: "dispatcher@gridunlocked.in",
    password: "demo-dispatch",
    name: "Field Dispatcher",
    role: "dispatcher",
  },
];

export const DEMO_CREDENTIALS = DEMO_USERS.map(({ email, password, role }) => ({
  email,
  password,
  role,
}));

// ---------------------------------------------------------------------------
// Session helpers
// ---------------------------------------------------------------------------

export function login(email: string, password: string): AuthUser | null {
  const u = DEMO_USERS.find(
    (d) => d.email.toLowerCase() === email.toLowerCase() && d.password === password
  );
  if (!u) return null;
  const session: AuthUser = { email: u.email, name: u.name, role: u.role };
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(session)); } catch {}
  return session;
}

export function logout(): void {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
}

export function getSession(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch { return null; }
}

// ---------------------------------------------------------------------------
// Tour state (per-user, persisted in localStorage)
// ---------------------------------------------------------------------------

export function isTourCompleted(email: string): boolean {
  if (typeof window === "undefined") return true;
  try { return localStorage.getItem(`gridunlocked_tour_${email}`) === "done"; }
  catch { return true; }
}

export function markTourCompleted(email: string): void {
  try { localStorage.setItem(`gridunlocked_tour_${email}`, "done"); } catch {}
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export const ROLE_LABELS: Record<Role, string> = {
  commander:  "Commander",
  admin:      "Admin",
  dispatcher: "Dispatcher",
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  commander:  "Approves dispatch recommendations and manages planned events",
  admin:      "Full governance access — tier control, shadow mode, model promotion",
  dispatcher: "Read-only on M15; primary interface is the Field Officer App (M16)",
};

export const ROLE_BADGE_STYLES: Record<Role, string> = {
  admin:      "bg-destructive/10 text-destructive border-destructive/30",
  commander:  "bg-primary/10 text-primary border-primary/30",
  dispatcher: "bg-muted text-muted-foreground border-border",
};

// ---------------------------------------------------------------------------
// Permission helpers (UI gating only — backend enforces its own authz)
// ---------------------------------------------------------------------------

export const can = {
  // Governance — admin only
  overrideTier:     (role: Role) => role === "admin",
  approvPromotion:  (role: Role) => role === "admin",
  runDrill:         (role: Role) => role === "admin",
  toggleShadowMode: (role: Role) => role === "admin",

  // Planned events — commander + admin
  addPlannedEvent:  (role: Role) => role === "admin" || role === "commander",
  editPlannedEvent: (role: Role) => role === "admin" || role === "commander",

  // Live recommendations — commander + admin (dispatchers read-only on M15)
  approveCard:      (role: Role) => role === "admin" || role === "commander",
};
