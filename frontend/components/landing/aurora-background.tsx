/**
 * AuroraBackground — purely decorative, slow-drifting gradient blobs for the
 * landing hero. CSS-only (no animation library) so it costs zero new
 * dependencies; animations are disabled under prefers-reduced-motion via the
 * .animate-aurora-* utilities in globals.css.
 */
export function AuroraBackground() {
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 z-0 overflow-hidden mask-[radial-gradient(ellipse_80%_60%_at_50%_0%,black,transparent)]"
    >
      <div className="absolute top-[-10%] left-[10%] size-[36rem] rounded-full bg-chart-1/50 blur-3xl animate-aurora-1" />
      <div className="absolute top-[5%] right-[5%] size-[32rem] rounded-full bg-chart-5/45 blur-3xl animate-aurora-2" />
      <div className="absolute top-[20%] left-[35%] size-[28rem] rounded-full bg-chart-2/40 blur-3xl animate-aurora-3" />
    </div>
  );
}
