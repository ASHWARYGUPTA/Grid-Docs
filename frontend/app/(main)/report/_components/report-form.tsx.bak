"use client";

import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Loader2, MapPin, Camera } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { CitizenReport } from "@/lib/types";
import { cn } from "@/lib/utils";

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
      setLocationNote("Location captured successfully.");
    } else {
      setLocationNote(
        "Couldn't get your location. Ensure location is enabled in your browser."
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
      toast.success("Report submitted — thank you!");
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
        <CardTitle className="text-base">Submit a report</CardTitle>
        <CardDescription>
          Share a photo and/or your location to help the network respond faster.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Photo upload */}
        <div className="space-y-1.5">
          <Label htmlFor="report-photo" className="flex items-center gap-1.5">
            <Camera className="size-3.5 text-muted-foreground" />
            Photo
          </Label>
          <div
            className={cn(
              "relative border-2 border-dashed rounded-lg p-4 text-center cursor-pointer",
              "transition-colors hover:border-primary/50 hover:bg-primary/5",
              photo ? "border-primary/40 bg-primary/5" : "border-border"
            )}
          >
            <input
              id="report-photo"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />
            {photo ? (
              <p className="text-sm text-primary font-medium flex items-center justify-center gap-2">
                <CheckCircle2 className="size-4" />
                {photo.name}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Tap to capture or upload a photo
              </p>
            )}
          </div>
        </div>

        {/* Location */}
        <div className="space-y-1.5">
          <Label className="flex items-center gap-1.5">
            <MapPin className="size-3.5 text-muted-foreground" />
            Location
          </Label>
          <Button
            type="button"
            variant="outline"
            className="w-full gap-2"
            onClick={handleLocate}
            disabled={locating}
          >
            {locating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : coords ? (
              <CheckCircle2 className="size-4 text-live" />
            ) : (
              <MapPin className="size-4" />
            )}
            {locating
              ? "Locating…"
              : coords
                ? `${coords.lat.toFixed(4)}, ${coords.lon.toFixed(4)}`
                : "Share my location"}
          </Button>
          {locationNote && (
            <p
              className={cn(
                "text-xs",
                coords ? "text-live" : "text-muted-foreground"
              )}
            >
              {locationNote}
            </p>
          )}
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <Label htmlFor="report-description">
            What&apos;s happening?{" "}
            <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Textarea
            id="report-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="e.g. accident blocking a lane, water logging…"
          />
        </div>

        <Button
          onClick={submit}
          disabled={submitting}
          className="w-full gap-2"
        >
          {submitting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : null}
          {submitting ? "Submitting…" : "Submit report"}
        </Button>
      </CardContent>
    </Card>
  );
}
