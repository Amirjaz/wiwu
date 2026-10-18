// Copies the Phosphor icons the Django templates use into backend/shop/templates/shop/icons/,
// so the server (which has no node_modules) can inline them: {% include "shop/icons/lock.svg" %}.
// Run after changing the list: npm run icons
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICONS = [
  'fingerprint', 'lock-simple', 'lock-simple-open', 'truck', 'arrow-u-up-left', 'credit-card', 'seal-check',
  'clock', 'map-pin', 'phone', 'envelope-simple', 'instagram-logo', 'arrow-left', 'caret-down', 'drop',
  'battery-charging', 'hand-grabbing', 'package', 'shield-check', 'list', 'x', 'magnifying-glass', 'pause',
  'play',
];
const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, '..', 'node_modules', '@phosphor-icons', 'core', 'assets', 'regular');
const to = join(here, '..', '..', 'backend', 'shop', 'templates', 'shop', 'icons');
mkdirSync(to, { recursive: true });
for (const name of ICONS) copyFileSync(join(from, `${name}.svg`), join(to, `${name}.svg`));
console.log(`copied ${ICONS.length} icons to ${to}`);
