import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable faster data fetching
  serverExternalPackages: ['apache-arrow'],
  // Optimize for dashboard workloads
  images: {
    domains: ['localhost'],
  },
  // Enable streaming for large datasets
  httpAgentOptions: {
    keepAlive: true,
  },
  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
};

export default nextConfig;
