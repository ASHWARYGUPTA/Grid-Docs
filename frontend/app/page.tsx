"use client";

import Link from "next/link";
import {
  ArrowRight,
  LayoutGrid,
  MapPin,
  MessageSquareWarning,
  Radar,
  Route,
  Send,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AuroraBackground } from "@/components/landing/aurora-background";
import { useAuth } from "@/context/auth-context";
import { HowItWorks } from "./_components/how-it-works";

const CAPABILITIES = [
  {
    icon: Radar,
    title: "Real-time hotspots",
    description: "Live density clustering surfaces emerging congestion as it forms.",
  },
  {
    icon: TrendingUp,
    title: "Predicted hotspots",
    description: "Forecasts corridor-level risk hours ahead using historical patterns.",
  },
  {
    icon: MapPin,
    title: "Auto station assignment",
    description: "Matches the nearest capable unit to every incident automatically.",
  },
  {
    icon: Route,
    title: "Diversion detection",
    description: "Suggests alternate routes the moment a corridor closure is likely.",
  },
  {
    icon: Sparkles,
    title: "AI recommendations",
    description: "Calibrated, explainable action cards for every commander decision.",
  },
  {
    icon: MessageSquareWarning,
    title: "Citizen reporting",
    description: "Photo + GPS reports from commuters feed straight into triage.",
  },
];

function HeroCta() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="h-9 w-40 rounded-lg bg-muted animate-pulse" />;
  }

  return (
    <Button
      size="lg"
      className="gap-1.5"
      nativeButton={false}
      render={<Link href={user ? "/live" : "/login"} />}
    >
      {user ? "Open dashboard" : "Sign in"}
      <ArrowRight className="size-4" />
    </Button>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto max-w-5xl px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <LayoutGrid className="size-4" />
            </div>
            <span className="font-semibold tracking-tight">Grid Unlocked</span>
          </div>
          <nav className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              nativeButton={false}
              render={<Link href="#how-it-works" />}
            >
              How it works
            </Button>
            <Button
              variant="outline"
              size="sm"
              nativeButton={false}
              render={<Link href="/login" />}
            >
              Sign in
            </Button>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <AuroraBackground />
        <div className="relative z-10 mx-auto max-w-5xl px-6 py-24 sm:py-32 text-center">
          <Badge variant="outline" className="mb-5">
            Intelligence layer for ASTraM
          </Badge>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight">
            Grid Unlocked
          </h1>
          <p className="mt-5 max-w-2xl mx-auto text-lg text-muted-foreground leading-relaxed">
            Real-time hotspots, AI dispatch recommendations, and citizen reporting for Bengaluru
            Traffic Police — built on calibrated ML models trained on 8,173 real ASTraM incidents.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <HeroCta />
            <Button
              variant="outline"
              size="lg"
              nativeButton={false}
              render={<Link href="#how-it-works" />}
            >
              How it works
            </Button>
          </div>
        </div>
      </section>

      {/* Capability strip */}
      <section className="border-t py-16 sm:py-20">
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {CAPABILITIES.map(({ icon: Icon, title, description }) => (
              <Card key={title}>
                <CardHeader className="pb-2">
                  <div className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary mb-2">
                    <Icon className="size-4" />
                  </div>
                  <CardTitle className="text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{description}</CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <HowItWorks />

      {/* Footer */}
      <footer className="border-t py-10">
        <div className="mx-auto max-w-5xl px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <LayoutGrid className="size-4" />
            <span>Grid Unlocked — all 18 planned modules implemented</span>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="link"
              size="sm"
              className="text-muted-foreground"
              nativeButton={false}
              render={<Link href="/login" />}
            >
              Sign in
              <Send className="size-3.5" />
            </Button>
          </div>
        </div>
        <Separator className="mt-8 mb-4 mx-auto max-w-5xl" />
        <p className="text-center text-xs text-muted-foreground">
          An intelligence layer for ASTraM — not a replacement.
        </p>
      </footer>
    </div>
  );
}
