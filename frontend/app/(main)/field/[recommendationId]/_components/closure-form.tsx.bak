"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { enqueueClosure } from "@/lib/field-offline-queue";
import type { ClosureRequest } from "@/lib/types";

const OFFICER_ID = "OFFICER-FIELD-APP";

export interface ClosureFormValidation {
  barricadesError: string | null;
  officersError: string | null;
  valid: boolean;
}

export function validateClosure(barricadesUsed: number, officersUsed: number): ClosureFormValidation {
  const barricadesError =
    Number.isInteger(barricadesUsed) && barricadesUsed >= 0
      ? null
      : "Barricades used must be a whole number, 0 or more.";
  const officersError =
    Number.isInteger(officersUsed) && officersUsed >= 1
      ? null
      : "Officers used must be a whole number, 1 or more.";
  return { barricadesError, officersError, valid: !barricadesError && !officersError };
}

interface ClosureFormProps {
  eventId: string;
  alreadyClosed: boolean;
  onClosed: () => void;
}

export function ClosureForm({ eventId, alreadyClosed, onClosed }: ClosureFormProps) {
  const [barricadesUsed, setBarricadesUsed] = useState(0);
  const [officersUsed, setOfficersUsed] = useState(1);
  const [diversionActivated, setDiversionActivated] = useState(false);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const validation = validateClosure(barricadesUsed, officersUsed);

  async function submit() {
    if (!validation.valid) {
      toast.error(validation.barricadesError ?? validation.officersError ?? "Invalid input");
      return;
    }

    const request: ClosureRequest = {
      closed_datetime: new Date().toISOString(),
      barricades_used: barricadesUsed,
      officers_used: officersUsed,
      diversion_activated: diversionActivated,
      notes: notes || null,
      officer_id: OFFICER_ID,
    };

    setSubmitting(true);
    try {
      await api.fieldClose(eventId, request);
      toast.success("Closure recorded");
      onClosed();
    } catch {
      enqueueClosure(eventId, request);
      toast.warning("Closure queued — will sync when back online");
      onClosed();
    } finally {
      setSubmitting(false);
    }
  }

  if (alreadyClosed) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Closure</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          This event has already been closed.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Close event</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="barricades-used">
            Barricades used
          </label>
          <input
            id="barricades-used"
            type="number"
            min={0}
            step={1}
            value={barricadesUsed}
            onChange={(e) => setBarricadesUsed(Number(e.target.value))}
            className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
          />
          {validation.barricadesError && (
            <p className="text-xs text-destructive">{validation.barricadesError}</p>
          )}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="officers-used">
            Officers used
          </label>
          <input
            id="officers-used"
            type="number"
            min={1}
            step={1}
            value={officersUsed}
            onChange={(e) => setOfficersUsed(Number(e.target.value))}
            className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
          />
          {validation.officersError && (
            <p className="text-xs text-destructive">{validation.officersError}</p>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={diversionActivated}
            onChange={(e) => setDiversionActivated(e.target.checked)}
          />
          Diversion activated
        </label>

        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="closure-notes">
            Notes
          </label>
          <textarea
            id="closure-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
          />
        </div>

        <Button onClick={submit} disabled={submitting || !validation.valid}>
          {submitting ? "Submitting…" : "Close event"}
        </Button>
      </CardContent>
    </Card>
  );
}
