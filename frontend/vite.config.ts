import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Django renders the pages (backend/shop/templates) and loads these entries with {% vite %}.
// No index.html: each entry is an island mounted on a page Django rendered. In development the
// pages load modules from this dev server; `origin` makes CSS url()s (fonts) point back here.
// Own ports (8030/5180) so it can run next to the other Nisatech projects' dev servers. A second copy
// of the repo (a git worktree) runs beside the first with VITE_PORT, and Django's VITE_DEV_SERVER to match.
const port = Number(process.env.VITE_PORT || 5180);

export default defineConfig({
  server: { host: '127.0.0.1', port, strictPort: true, origin: `http://127.0.0.1:${port}`, cors: true },
  plugins: [react(), tailwindcss()],
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        site: 'src/site.ts',
        bag3d: 'src/islands/bag3d.ts',
        home: 'src/islands/home.ts',
        checkout: 'src/islands/checkout.tsx',
        order: 'src/islands/order.tsx',
        lookup: 'src/islands/lookup.tsx',
        panel: 'src/panel/main.tsx',
      },
    },
  },
});
