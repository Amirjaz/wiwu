import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Django renders the pages (backend/shop/templates) and loads these entries with {% vite %}.
// No index.html: each entry is an island mounted on a page Django rendered. In development the
// pages load modules from this dev server; `origin` makes CSS url()s (fonts) point back here.
export default defineConfig({
  // Own ports (8030/5180) so it can run next to the other Nisatech projects' dev servers.
  server: { host: '127.0.0.1', port: 5180, strictPort: true, origin: 'http://127.0.0.1:5180', cors: true },
  plugins: [react(), tailwindcss()],
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        site: 'src/site.ts',
        hero: 'src/islands/hero.ts',
        home: 'src/islands/home.ts',
        checkout: 'src/islands/checkout.tsx',
        order: 'src/islands/order.tsx',
        lookup: 'src/islands/lookup.tsx',
        panel: 'src/panel/main.tsx',
      },
    },
  },
});
