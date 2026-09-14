import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle: the deployment image stays small and needs no node_modules.
  output: "standalone",
  outputFileTracingRoot: __dirname,
  images: {
    // Demo catalogue images; replace with the real media host when boats bring their own photos.
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
};

export default nextConfig;
