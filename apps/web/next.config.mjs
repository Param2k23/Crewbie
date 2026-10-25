/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // three / r3f ship ESM that Next must transpile for the client bundle.
  transpilePackages: ["three"],
  // The public site opens on the Cubbie x Crewbie landing page. The Mission Control demo
  // (Campus Pulse) stays available at /demo and /arena.
  async redirects() {
    return [{ source: "/", destination: "/unlocks", permanent: false }];
  },
  async rewrites() {
    return [{ source: "/demo", destination: "/" }];
  },
};
export default nextConfig;
