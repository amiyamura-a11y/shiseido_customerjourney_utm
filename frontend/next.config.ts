import type { NextConfig } from "next";

const API = process.env.API_ORIGIN || "http://127.0.0.1:8000";
// NEXT_OUTPUT=export builds a static site (frontend/out) that FastAPI serves together with the API.
const isExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = isExport
  ? { output: "export", trailingSlash: true, images: { unoptimized: true } }
  : {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
      },
    };

export default nextConfig;
