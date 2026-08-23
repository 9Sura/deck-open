import * as React from "react";
import { SketchFrame } from "@/components/sketch-frame";
import { cn } from "@/lib/utils";

/** Hand-inked surface — content wrapped in a drawn <SketchFrame> border. */
export function Card({
  className,
  variant = 0,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: number }) {
  return <SketchFrame variant={variant} className={cn(className)} {...props} />;
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-6 sm:p-8", className)} {...props} />;
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-6 pb-6 sm:px-8 sm:pb-8", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("font-display text-2xl font-bold tracking-tight", className)}
      {...props}
    />
  );
}
