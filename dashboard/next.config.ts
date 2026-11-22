import type { NextConfig } from 'next';
const config: NextConfig = {
  poweredByHeader: false,
  outputFileTracingIncludes: { '/api/report': ['./recorded/run.v1.json'] },
};
export default config;
