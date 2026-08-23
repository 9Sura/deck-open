import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TapeLabel } from "@/components/tape-label";
import { DevLock } from "@/components/dev-lock";
import { cn } from "@/lib/utils";

export function ToolCard({
  href,
  eyebrow,
  title,
  blurb,
  cta,
  tape,
  tapeColor = "support",
  doodle,
  variant = 0,
  locked = false,
  focusable = true,
  className,
}: {
  href: string;
  eyebrow: string;
  title: React.ReactNode;
  blurb: string;
  cta: string;
  tape: string;
  tapeColor?: "accent" | "support" | "highlight";
  doodle: React.ReactNode;
  variant?: number;
  locked?: boolean;
  /** false for cloned carousel copies — keeps them out of the tab order */
  focusable?: boolean;
  className?: string;
}) {
  const unfocusable = locked || !focusable;
  return (
    <Card
      variant={variant}
      className={cn(
        "group relative flex flex-col p-7 transition-transform sm:p-9",
        locked ? "select-none" : "hover:-translate-y-1",
        className,
      )}
    >
      <div className="mb-6 flex items-start justify-between gap-3">
        <div className="min-w-0 shrink text-ink/80">{doodle}</div>
        <TapeLabel color={tapeColor} rotate={4} className="shrink-0">
          {tape}
        </TapeLabel>
      </div>

      <p className="marker text-sm text-muted">{eyebrow}</p>
      <h3 className="mt-1 font-display text-3xl font-extrabold leading-tight tracking-tight">
        {title}
      </h3>
      <p className="mt-3 max-w-sm text-ink/70">{blurb}</p>

      <div className="mt-7 flex-1" />
      <Button
        asChild
        variant="primary"
        size="md"
        className={cn("w-fit", locked && "pointer-events-none opacity-70")}
        tabIndex={unfocusable ? -1 : undefined}
        aria-disabled={locked || undefined}
      >
        <Link href={href} tabIndex={unfocusable ? -1 : undefined}>
          {cta}
        </Link>
      </Button>

      {locked ? <DevLock /> : null}
    </Card>
  );
}
