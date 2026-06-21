"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Bell, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { writeSubscriptions, type StoredSubscription } from "@/lib/citizen-storage";

export const CORRIDORS = [
  "Airport New South Road",
  "Bannerghatta Road",
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
    toast.success("Subscription removed");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Bell className="size-4 text-muted-foreground" />
          Corridor alerts
        </CardTitle>
        <CardDescription>
          Get notified when a hotspot or congestion is detected near subscribed corridors.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="corridor-select">Corridor</Label>
            <Select value={selectedCorridor} onValueChange={(v) => v && setSelectedCorridor(v)}>
              <SelectTrigger id="corridor-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-64">
                {CORRIDORS.map((corridor) => (
                  <SelectItem key={corridor} value={corridor}>
                    {corridor}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              onClick={addSubscription}
              disabled={submitting}
              className="gap-1.5"
            >
              <Bell className="size-3.5" />
              Subscribe
            </Button>
          </div>
        </div>

        {subscriptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No corridor subscriptions yet.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {subscriptions.map((sub) => (
              <Badge
                key={sub.subscription_id}
                variant="secondary"
                className="gap-1.5 pr-1 pl-2.5"
              >
                {sub.corridors.join(", ")}
                <button
                  type="button"
                  onClick={() => removeSubscription(sub.subscription_id)}
                  aria-label={`Remove ${sub.corridors.join(", ")} subscription`}
                  className="rounded-sm hover:bg-background/50 p-0.5 transition-colors"
                >
                  <X className="size-3" />
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
