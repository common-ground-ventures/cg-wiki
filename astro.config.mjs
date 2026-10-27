// @ts-check
import { defineConfig } from 'astro/config';

// Static HTML only: every page is a finished file, so search and AI crawlers
// read it without running JavaScript. Workers serves dist/ as static assets.
export default defineConfig({
  site: 'https://wiki.commonground.ventures',
  output: 'static',
  trailingSlash: 'always',
  build: { format: 'directory' },
  compressHTML: false,
  devToolbar: { enabled: false },
});
