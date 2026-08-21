import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: 'export',
  trailingSlash: true,
};

export default nextConfig;
