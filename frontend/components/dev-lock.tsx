import { TapeLabel } from "@/components/tape-label";
import { MarkerText } from "@/components/marker-text";
import { cn } from "@/lib/utils";

/** Hand-inked padlock — matches the doodle stroke style (no lock in the set). */
export function LockGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <rect x="4.5" y="10.5" width="15" height="9.5" rx="2.5" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
      <path d="M12 14.2v2.4" />
    </svg>
  );
}

/**
 * A simplified version of the roleplay page's "in development" lock overlay:
 * a translucent, blurred layer with a padlock + an "in development" tape,
 * dropped over any `position: relative` container to flag a not-yet-built
 * feature — the content behind shows through, faded. Blocks pointer events so
 * the covered control can't be clicked.
 *
 * `compact` renders a small horizontal badge sized to sit over a single button;
 * the default is a centered stack sized for a card.
 */
export function DevLock({
  label = "in development",
  note = "locked for now",
  compact = false,
  className,
}: {
  label?: string;
  note?: string;
  compact?: boolean;
  className?: string;
}) {
  if (compact) {
    return (
      <div
        className={cn(
          "absolute inset-0 z-20 flex items-center justify-center gap-2 rounded-[inherit] bg-paper/70 backdrop-blur-[1px]",
          className,
        )}
      >
        <LockGlyph className="h-4 w-4 text-ink/75" />
        <TapeLabel color="highlight" rotate={-2}>
          {label}
        </TapeLabel>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-[inherit] bg-paper/70 px-4 text-center backdrop-blur-[2px]",
        className,
      )}
    >
      <LockGlyph className="h-9 w-9 text-ink/75" />
      <TapeLabel color="highlight" rotate={-2}>
        {label}
      </TapeLabel>
      {note ? (
        <MarkerText rotate={-2} className="text-sm">
          {note}
        </MarkerText>
      ) : null}
    </div>
  );
}
