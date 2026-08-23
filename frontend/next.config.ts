import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Pin the app root. Turbopack otherwise infers it from the nearest
    // lockfile, so a stray package-lock.json in the repo root (this dir's
    // parent) silently rebases module paths and breaks the client manifest.
    root: __dirname,
  },
};

export default nextConfig;
