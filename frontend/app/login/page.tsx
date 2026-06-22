"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, LayoutGrid, LogIn, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/context/auth-context";
import { DEMO_CREDENTIALS, ROLE_BADGE_STYLES, ROLE_LABELS, type Role } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // If already authenticated, go to dashboard
  useEffect(() => {
    if (!loading && user) {
      router.replace("/live");
    }
  }, [loading, user, router]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    // Small delay for UX feedback
    setTimeout(() => {
      const ok = login(email.trim(), password);
      if (ok) {
        router.replace("/live");
      } else {
        setError("Invalid email or password. Try a demo credential below.");
        setSubmitting(false);
      }
    }, 300);
  };

  const fillDemo = (demoEmail: string, demoPassword: string) => {
    setEmail(demoEmail);
    setPassword(demoPassword);
    setError(null);
  };

  if (loading || user) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-5">

        {/* Brand */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
            <LayoutGrid className="size-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Grid Unlocked</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Command Dashboard</p>
          </div>
        </div>

        {/* Login card */}
        <Card className="shadow-lg border-border/60">
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Sign in</CardTitle>
            <CardDescription className="text-xs">
              Access requires operator credentials. Use a demo account below to get started.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@gridunlocked.in"
                  className="h-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPass ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className="h-9 pr-9"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => setShowPass((s) => !s)}
                    tabIndex={-1}
                  >
                    {showPass ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                  </button>
                </div>
              </div>

              {error && (
                <p className="text-xs text-destructive flex items-center gap-1.5 bg-destructive/8 border border-destructive/20 rounded-md px-3 py-2">
                  <ShieldCheck className="size-3.5 shrink-0" />
                  {error}
                </p>
              )}

              <Button type="submit" className="w-full gap-2" disabled={submitting}>
                {submitting ? (
                  <><span className="size-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />Signing in…</>
                ) : (
                  <><LogIn className="size-3.5" />Sign in</>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Demo credentials */}
        <Card className="border-dashed border-border/80 bg-muted/30">
          <CardHeader className="pb-3 pt-4 px-4">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Demo credentials
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {DEMO_CREDENTIALS.map(({ email: dEmail, password: dPass, role }) => (
              <div
                key={dEmail}
                className="flex items-center justify-between gap-3 rounded-md bg-background border border-border/60 px-3 py-2.5 hover:border-primary/30 transition-colors"
              >
                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge
                      variant="outline"
                      className={cn("text-[10px] py-0 h-4 shrink-0", ROLE_BADGE_STYLES[role as Role])}
                    >
                      {ROLE_LABELS[role as Role]}
                    </Badge>
                    <span className="text-xs font-mono text-foreground truncate">{dEmail}</span>
                  </div>
                  <p className="text-[11px] text-muted-foreground font-mono">
                    Password: <span className="text-foreground">{dPass}</span>
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 h-7 text-xs"
                  onClick={() => fillDemo(dEmail, dPass)}
                >
                  Use
                </Button>
              </div>
            ))}
            <p className="text-[10px] text-muted-foreground pt-1">
              Click <strong>Use</strong> to fill the form, then Sign in.
            </p>
          </CardContent>
        </Card>

        <Separator />
        <p className="text-center text-[10px] text-muted-foreground">
          Grid Unlocked · Bengaluru Traffic Management · Demo environment
        </p>
      </div>
    </div>
  );
}
