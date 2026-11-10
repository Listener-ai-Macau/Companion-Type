import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import {documentEngineAssets} from '../../packages/document-context/viteAssets';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: './',
  plugins: [react(),documentEngineAssets()],
  resolve: {
    alias: {
      '@companion-type/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)),
      '@companion-type/ui': fileURLToPath(new URL('../../packages/ui/src/index.ts', import.meta.url)),
    },
  },
  build: {
    // Vite's normal browser target is newer than many Android WebViews.
    // Chrome 64 is the minimum supported by Vite's module-loading runtime.
    target: 'chrome64',
    cssTarget: 'chrome64',
    outDir: 'dist',
    emptyOutDir: true,
  },
});

