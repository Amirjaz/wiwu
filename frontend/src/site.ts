// Loaded on every page: the styles, and the small bits of behaviour the Django pages need.
import './site.css';

// Phone menu: a panel over the page. While it's open the page under it doesn't scroll; a link, the
// button again or Escape closes it.
const toggle = document.querySelector<HTMLButtonElement>('[data-menu-toggle]');
const menu = document.getElementById('mobile-menu');
if (toggle && menu) {
  const set = (open: boolean) => {
    toggle.setAttribute('aria-expanded', String(open));
    menu.hidden = !open;
    document.documentElement.classList.toggle('overflow-hidden', open);
  };
  toggle.addEventListener('click', () => set(toggle.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', (event) => {
    if ((event.target as HTMLElement).closest('a')) set(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !menu.hidden) {
      set(false);
      toggle.focus();
    }
  });
}
