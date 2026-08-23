"use client";

// The app-wide notice slot (issue #196).
//
// The storage- and sync-error notices in progress-provider.tsx are global: they
// can fire on any route at any time, so the modal's `notice` prop — which
// explains the SET a quiz is about to serve — is the wrong home for them. But
// they were rendered in the app tree at `z-50`, while LiveQuizModal and
// ui/Dialog are `createPortal`'d to document.body at the same `z-50`. Equal
// z-index, later in the DOM wins, so the blurred backdrop painted over them —
// and both notices sat outside the dialog's `aria-modal="true"` subtree (screen
// readers skip it) and outside its Tab focus trap (the Dismiss button was
// unreachable). Raising the z-index fixes only the paint; issue #123 already
// recorded that, which is why this is a slot and not a number.
//
// So: the provider PUBLISHES the notice here, and an open overlay CLAIMS the
// slot by rendering <NoticeOutlet /> inside its own focus-trapped panel. With no
// overlay open the layer renders it at body level exactly as before.
//
// Two properties matter.
//
// - The notice keeps its own `fixed inset-x-0 bottom-4` positioning in both
//   homes. Inside an overlay its containing block is the backdrop div, which is
//   itself `fixed inset-0` (and `backdrop-filter` makes it a containing block
//   for fixed descendants), so the notice lands in the same place on screen —
//   only its position in the DOM moved, which is the half that was broken.
// - Only the TOPMOST claim renders. Two overlays can be open at once (the
//   settings Dialog over a quiz), and the last one to claim is the one painting
//   on top, so it is the one that gets the notice. Without this both outlets
//   would render the same node twice.

import * as React from "react";

interface NoticeLayerValue {
  /** The published notice, or null when there is nothing to say. */
  node: React.ReactNode;
  /** Claim ids in mount order — the last entry is the topmost overlay. */
  hosts: readonly string[];
  claim: (id: string) => void;
  release: (id: string) => void;
}

const NoticeLayerContext = React.createContext<NoticeLayerValue | null>(null);

/** Publishes `node` and renders it at body level whenever no overlay has claimed
 *  the slot. Mounted by ProgressProvider around its children. */
export function NoticeLayerProvider({
  node,
  children,
}: {
  node: React.ReactNode;
  children: React.ReactNode;
}) {
  const [hosts, setHosts] = React.useState<readonly string[]>([]);

  const claim = React.useCallback((id: string) => {
    setHosts((h) => (h.includes(id) ? h : [...h, id]));
  }, []);
  const release = React.useCallback((id: string) => {
    setHosts((h) => h.filter((x) => x !== id));
  }, []);

  const value = React.useMemo<NoticeLayerValue>(
    () => ({ node, hosts, claim, release }),
    [node, hosts, claim, release],
  );

  return (
    <NoticeLayerContext.Provider value={value}>
      {children}
      {hosts.length === 0 ? node : null}
    </NoticeLayerContext.Provider>
  );
}

/** Rendered by an overlay INSIDE its focus-trapped panel, so a notice raised
 *  while it is open is painted above the backdrop, announced by a screen reader
 *  and reachable by Tab. Renders nothing when another overlay opened later. */
export function NoticeOutlet() {
  const ctx = React.useContext(NoticeLayerContext);
  const id = React.useId();
  const claim = ctx?.claim;
  const release = ctx?.release;

  React.useEffect(() => {
    if (!claim || !release) return;
    claim(id);
    return () => release(id);
  }, [claim, release, id]);

  if (!ctx) return null;
  return ctx.hosts[ctx.hosts.length - 1] === id ? <>{ctx.node}</> : null;
}
