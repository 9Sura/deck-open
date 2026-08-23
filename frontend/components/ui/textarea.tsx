import * as React from "react";
import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "hand-border-2 min-h-24 w-full resize-y bg-paper px-4 py-3 text-[0.95rem] text-ink outline-none transition-colors placeholder:text-muted focus-visible:ring-2 focus-visible:ring-support/50",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
