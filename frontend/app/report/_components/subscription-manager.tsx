"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { writeSubscriptions, type StoredSubscription } from "@/lib/citizen-storage";

export const CORRIDORS = [
  "Airport New South Road",
  "Bannerghata Road",
  "Bellary Road 1",
  "Bellary Road 2",
  "CBD 1",
  "CBD 2",
  "Hennur Main Road",
  "Hosur Road",
  "IRR(Thanisandra road)",
  "Magadi Road",
  "Mysore Road",
  "ORR East 1",
  "ORR East 2",
  "ORR North 1",
  "ORR North 2",
  "ORR West 1",
  "Old Airport Road",
  "Old Madras Road",
  "Tumkur Road",
  "Varthur Road",
  "West of Chord Road",
  "Non-corridor",
];

interface SubscriptionManagerProps {
  userRef: string;
  subscriptions: StoredSubscription[];
  onSubscriptionsChange: (subscriptions: StoredSubscription[]) => void;
}

export function SubscriptionManager({
  userRef,
  subscriptions,
  onSubscriptionsChange,
}: SubscriptionManagerProps) {
  const [selectedCorridor, setSelectedCorridor] = useState(CORRIDORS[0]);
  const [submitting, setSubmitting] = useState(false);

  async function addSubscription() {
    setSubmitting(true);
    try {
      const res = await api.citizenSubscribe({
        user_ref: userRef,
        corridors: [selectedCorridor],
        h3_cells: [],
      });
      const updated = [
        ...subscriptions,
        { subscription_id: res.subscription_id, corridors: res.corridors },
      ];
      writeSubscriptions(updated);
      onSubscriptionsChange(updated);
      toast.success(`Subscribed to ${selectedCorridor}`);
    } catch {
      toast.error("Failed to subscribe");
    } finally {
      setSubmitting(false);
    }
  }

  async function removeSubscription(subscriptionId: string) {
    try {
      await api.citizenUnsubscribe(subscriptionId);
    } catch {
      // best-effort — still remove locally so the UI doesn't get stuck
    }
    const updated = subscriptions.filter((s) => s.subscription_id !== subscriptionId);
    writeSubscriptions(updated);
    onSubscriptionsChange(updated);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Corridor alerts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <select
            value={selectedCorridor}
            onChange={(e) => setSelectedCorridor(e.target.value)}
            className="flex-1 rounded-md border bg-transparent px-3 py-1.5 text-sm"
          >
            {CORRIDORS.map((corridor) => (
              <option key={corridor} value={corridor}>
                {corridor}
              </option>
            ))}
          </select>
          <Button type="button" onClick={addSubscription} disabled={submitting}>
            Subscribe
          </Button>
        </div>

        {subscriptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No corridor alerts yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {subscriptions.map((sub) => (
              <Badge key={sub.subscription_id} variant="secondary" className="gap-1">
                {sub.corridors.join(", ")}
                <button
                  type="button"
                  onClick={() => removeSubscription(sub.subscription_id)}
                  aria-label={`Remove ${sub.corridors.join(", ")} subscription`}
                  className="ml-1"
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function matchesSubscription(
  payload: { subscription_id: string },
  subscriptions: StoredSubscription[]
): boolean {
  return subscriptions.some((s) => s.subscription_id === payload.subscription_id);
}
