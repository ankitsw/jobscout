import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Backend (FastAPI/uvicorn) runs on 8000 in dev; the built app is served
// by FastAPI itself in production, so this proxy only matters for `npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/jobs': 'http://127.0.0.1:8000',
      '/resumes': 'http://127.0.0.1:8000',
      '/agent': 'http://127.0.0.1:8000',
      '/cv': 'http://127.0.0.1:8000',
      '/hunter': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
