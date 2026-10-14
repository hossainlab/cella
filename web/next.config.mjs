// Two build modes, chosen by NEXT_PUBLIC_DATA_MODE (see lib/api.ts):
//  - server (default): /api/* is proxied to the FastAPI backend, so the browser
//    makes same-origin calls (no CORS). Override the target with API_BASE.
//  - static: a plain file export (`out/`) that reads data written by
//    `cella export`, for hosting without a backend (e.g. GitHub Pages, where the
//    site lives under a sub-path set by NEXT_PUBLIC_BASE_PATH, e.g. "/cella").
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8137";
const STATIC = process.env.NEXT_PUBLIC_DATA_MODE === "static";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

/** @type {import('next').NextConfig} */
const nextConfig = STATIC
  ? {
      output: "export",
      basePath: BASE_PATH,
      trailingSlash: true, // /organs/Lung/ -> organs/Lung/index.html on static hosts
      images: { unoptimized: true },
    }
  : {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${API_BASE}/:path*` }];
      },
    };

export default nextConfig;
