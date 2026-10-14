// Loaded on every page: the styles, and the small bits of behaviour the Django pages need.
import './site.css';

// Mobile menu.
const toggle = document.querySelector<HTMLButtonElement>('[data-menu-toggle]');
const menu = document.getElementById('mobile-menu');
if (toggle && menu) {
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    menu.hidden = !open;
  });
  menu.addEventListener('click', (event) => {
    if ((event.target as HTMLElement).closest('a')) {
      toggle.setAttribute('aria-expanded', 'false');
      menu.hidden = true;
    }
  });
}
