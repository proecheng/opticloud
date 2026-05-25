import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow workspace packages to be transpiled (Tailwind directives in @opticloud/ui)
  transpilePackages: ["@opticloud/ui"],
  // Service URLs (env vars defaulting to local dev)
  env: {
    NEXT_PUBLIC_AUTH_SERVICE_URL: process.env.NEXT_PUBLIC_AUTH_SERVICE_URL ?? "http://localhost:8001",
    NEXT_PUBLIC_SOLVER_SERVICE_URL: process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002",
  },
};

export default withNextIntl(nextConfig);
