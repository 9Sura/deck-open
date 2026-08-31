"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "hand-pill inline-flex items-center justify-center gap-2 font-semibold whitespace-nowrap transition-all disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-support/50 focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
  {
    variants: {
      variant: {
        // Filled DECA-blue sticker with an inked border + hard "drawn" shadow
        // that presses on click. The on-fill ink is theme-owned, not derived —
        // --on-accent/--on-support default to --paper but a theme with a
        // mid-tone fill overrides them (issue #247). Never hardcode text-paper
        // on either fill: --paper is tuned against --ink, not against the fill.
        primary:
          "border-2 border-ink bg-accent text-[var(--on-accent)] shadow-[var(--btn-shadow)] hover:-translate-y-0.5 hover:shadow-[4px_5px_0_0_var(--ink)] active:translate-y-0 active:shadow-[2px_2px_0_0_var(--ink)]",
        accent:
          "border-2 border-ink bg-support text-[var(--on-support)] shadow-[var(--btn-shadow)] hover:-translate-y-0.5 hover:shadow-[4px_5px_0_0_var(--ink)] active:translate-y-0 active:shadow-[2px_2px_0_0_var(--ink)]",
        outline:
          "border-2 border-ink bg-paper text-ink hover:-translate-y-0.5 hover:bg-paper-2 active:translate-y-0",
        ghost: "border-2 border-transparent bg-transparent text-ink hover:bg-ink/5",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-6 text-[0.95rem]",
        lg: "h-14 px-8 text-lg",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, children, ...props }, ref) => {
    const classes = cn(buttonVariants({ variant, size }), className);

    // Minimal "asChild": render the single child element with merged classes,
    // so <Button asChild><Link/></Button> yields a styled anchor (no Radix dep).
    if (asChild && React.isValidElement(children)) {
      const child = children as React.ReactElement<{ className?: string }>;
      return React.cloneElement(child, {
        className: cn(classes, child.props.className),
      });
    }

    return (
      <button ref={ref} className={classes} {...props}>
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { buttonVariants };
