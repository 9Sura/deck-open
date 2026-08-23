# Team photos

Drop developer / contributor profile pictures here. Anything in `public/` is
served from the site root, so a file at `public/team/kelton.jpg` is reachable at
`/team/kelton.jpg` and referenced that way from
[`app/developers/page.tsx`](../../app/developers/page.tsx).

## Conventions

- **Filename:** lowercase, hyphenated, matching the person — e.g. `kelton-yu.jpg`.
- **Shape:** square. The card crops to a square/rounded frame, so a 1:1 source
  avoids distortion.
- **Size:** ~512×512 is plenty (it renders at 128px). Keep files small
  (< ~200 KB); prefer `.webp` or `.jpg`, or `.png` if you need transparency.
- **Content:** a clear headshot. This page is public and often seen by minors —
  keep it appropriate.

## Adding your photo

1. Save your image here following the naming convention above.
2. In `app/developers/page.tsx`, replace the "photo soon" placeholder box with a
   `next/image` pointing at `/team/<your-file>` (ask a maintainer if unsure —
   it's a small, drop-in swap).
