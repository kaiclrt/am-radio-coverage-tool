import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // The Flask API (../api/app.py) runs on :5000 and restricts CORS to
    // this dev-server origin. Proxying /api keeps the browser same-origin
    // in dev, so CORS never has to be relaxed. Override the target with
    // VITE_API_TARGET if the API runs elsewhere.
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
});
