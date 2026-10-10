// Proxy /api/* to the FastAPI backend so the browser makes same-origin calls
// (no CORS). Override the target with API_BASE when the backend runs elsewhere.
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8137";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_BASE}/:path*` }];
  },
};

export default nextConfig;
