import { fileURLToPath, URL } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react()],
  // Must match apps/windows/src-tauri/tauri.conf.json build.devUrl
  server: {
    port: 1421,
    strictPort: true,
    clearScreen: false,
  },
  resolve: {
    alias: {
      '@companion-type/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)),
      '@companion-type/ui': fileURLToPath(new URL('../../packages/ui/src/index.ts', import.meta.url)),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});

