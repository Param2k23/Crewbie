/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // three / r3f ship ESM that Next must transpile for the client bundle.
  transpilePackages: ["three"],
};
export default nextConfig;
