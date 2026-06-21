"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { CitizenReport } from "@/lib/types";

interface GeoResult {
  lat: number | null;
  lon: number | null;
  attempted: boolean;
}

function getGeolocation(): Promise<GeoResult> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve({ lat: null, lon: null, attempted: true });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude, attempted: true }),
      () => resolve({ lat: null, lon: null, attempted: true }),
      { timeout: 5000 }
    );
  });
}

export function canSubmitReport(hasPhoto: boolean, hasLocation: boolean): boolean {
  return hasPhoto || hasLocation;
}

interface ReportFormProps {
  onSubmitted: (report: CitizenReport) => void;
}

export function ReportForm({ onSubmitted }: ReportFormProps) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [locating, setLocating] = useState(false);
  const [locationNote, setLocationNote] = useState<string | null>(null);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleLocate() {
    setLocating(true);
    setLocationNote(null);
    const result = await getGeolocation();
    setLocating(false);
    if (result.lat !== null && result.lon !== null) {
      setCoords({ lat: result.lat, lon: result.lon });
      setLocationNote("Location captured.");
    } else {
      setLocationNote(
        "Couldn't get your location — make sure your photo has location enabled, or try again."
      );
    }
  }

  async function submit() {
    if (!canSubmitReport(photo !== null, coords !== null)) {
      toast.error("Add a photo or share your location before submitting.");
      return;
    }

    const formData = new FormData();
    if (photo) formData.append("photo", photo);
    else {
      toast.error("A photo is required.");
      return;
    }
    if (coords) {
      formData.append("lat", String(coords.lat));
      formData.append("lon", String(coords.lon));
    }
    if (description) formData.append("description", description);

    setSubmitting(true);
    try {
      const report = await api.citizenReport(formData);
      toast.success("Report submitted");
      onSubmitted(report);
      setPhoto(null);
      setDescription("");
      setCoords(null);
      setLocationNote(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit report");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Report congestion</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="report-photo">
            Photo
          </label>
          <input
            id="report-photo"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            className="w-full text-sm"
          />
        </div>

        <div className="space-y-1">
          <Button type="button" variant="outline" onClick={handleLocate} disabled={locating}>
            {locating ? "Locating…" : "Share my location"}
          </Button>
          {locationNote && <p className="text-xs text-muted-foreground">{locationNote}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium" htmlFor="report-description">
            What's happening? (optional)
          </label>
          <textarea
            id="report-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-md border bg-transparent px-3 py-1.5 text-sm"
            placeholder="e.g. accident blocking a lane, water logging"
          />
        </div>

        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Submitting…" : "Submit report"}
        </Button>
      </CardContent>
    </Card>
  );
}
