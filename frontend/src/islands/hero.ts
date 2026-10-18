// The product tour on the home page. Each text stop ([data-stop]) has a photo ([data-poster]) that
// fades in when the stop reaches the middle of the screen, so the tour works everywhere. On devices
// that can take it, the 3D bag (hero/scene.ts) replaces the photos once the page has loaded: it
// turns to each stop, and at the first one people can drag it and open the hotspots.
import type { HeroScene } from '../hero/scene';

const stage = document.querySelector<HTMLElement>('[data-hero-stage]');
const stops = [...document.querySelectorAll<HTMLElement>('[data-stop]')];

function canRender3d(): boolean {
  const nav = navigator as Navigator & { connection?: { saveData?: boolean }; deviceMemory?: number };
  if (nav.connection?.saveData) return false;
  if (nav.deviceMemory !== undefined && nav.deviceMemory < 2) return false;
  try {
    return !!document.createElement('canvas').getContext('webgl2');
  } catch {
    return false;
  }
}

function setup(stage: HTMLElement) {
  const posters = [...stage.querySelectorAll<HTMLElement>('[data-poster]')];
  const hotspotLayer = stage.querySelector<HTMLElement>('[data-hotspots]');
  const hint = stage.querySelector<HTMLElement>('[data-drag-hint]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const small = Math.min(screen.width, screen.height) < 768;
  let scene: HeroScene | null = null;
  let active = 0;

  const showPoster = (index: number) => {
    for (const poster of posters) {
      const serves = (poster.dataset.poster ?? '').split(' ').map(Number);
      poster.classList.toggle('opacity-0', !serves.includes(index) || !!scene);
    }
  };

  const setActive = (index: number) => {
    if (index === active) return;
    active = index;
    stage.dispatchEvent(new CustomEvent('hero:stop', { detail: index })); // for the view switcher (home.ts)
    showPoster(index);
    scene?.goTo(index);
    hotspotLayer?.classList.toggle('opacity-0', index !== 0);
    hint?.classList.toggle('opacity-0', index !== 0);
    closeTips();
  };

  // The stop crossing the middle of the screen is the active one. On phones the stops are cards in a
  // sideways scroller under the bag ([data-stops], site.css): there it's the card mostly in view.
  const scroller = document.querySelector<HTMLElement>('[data-stops]');
  const sideways = !!scroller && getComputedStyle(scroller).overflowX === 'auto';
  const stopObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && (!sideways || entry.intersectionRatio >= 0.6)) {
          setActive(Number((entry.target as HTMLElement).dataset.stop));
        }
      }
    },
    sideways ? { root: scroller, threshold: 0.6 } : { rootMargin: '-45% 0px -45% 0px' },
  );
  stops.forEach((stop) => stopObserver.observe(stop));

  // Hotspots: buttons the scene positions over the bag; each opens a short note.
  const buttons = new Map<string, HTMLButtonElement>();
  hotspotLayer?.querySelectorAll<HTMLButtonElement>('[data-hotspot]').forEach((button) => {
    buttons.set(button.dataset.hotspot!, button);
    button.addEventListener('click', () => {
      const open = button.getAttribute('aria-expanded') !== 'true';
      closeTips();
      button.setAttribute('aria-expanded', String(open));
    });
  });
  function closeTips() {
    buttons.forEach((b) => b.setAttribute('aria-expanded', 'false'));
  }
  document.addEventListener('keydown', (e) => e.key === 'Escape' && closeTips());

  // Notes are 13rem wide under their dot; near the stage's edges they slide sideways to stay on screen.
  const tipHalf = 104;
  const placeHotspots = (positions: Map<string, { x: number; y: number } | null>) => {
    const width = stage.clientWidth;
    positions.forEach((pos, id) => {
      const button = buttons.get(id);
      if (!button) return;
      button.hidden = !pos;
      if (!pos) return;
      button.style.transform = `translate(${pos.x}px, ${pos.y}px)`;
      const shift = Math.max(8 - (pos.x - tipHalf), Math.min(0, width - 8 - (pos.x + tipHalf)));
      button.style.setProperty('--tip-shift', `${Math.round(shift)}px`);
    });
  };

  // The hint has done its job once someone touches the bag.
  stage.addEventListener('pointerdown', () => hint?.remove(), { once: true });

  if (!canRender3d()) return;

  const load3d = async () => {
    try {
      const { HeroScene } = await import('../hero/scene');
      const instance = new HeroScene(stage, { reducedMotion, small, onHotspots: placeHotspots });
      const visibility = new IntersectionObserver(([entry]) => instance.setVisible(entry.isIntersecting));
      visibility.observe(stage.closest('section') ?? stage);
      document.addEventListener('visibilitychange', () => instance.setVisible(!document.hidden));
      await instance.load((small ? stage.dataset.modelSmall : stage.dataset.model) ?? '');
      scene = instance;
      if (import.meta.env.DEV) (window as unknown as { __hero: HeroScene }).__hero = instance;
      instance.goTo(active);
      showPoster(active);
      hotspotLayer?.classList.remove('hidden');
      hint?.classList.remove('hidden');
    } catch (error) {
      // The photos stay; the page works the same without the 3D.
      console.warn('3D hero unavailable', error);
    }
  };

  // After everything the page needs: the model is a nice-to-have, never in the way of buying.
  const whenIdle = () =>
    'requestIdleCallback' in window ? requestIdleCallback(() => load3d(), { timeout: 2500 }) : setTimeout(load3d, 600);
  if (document.readyState === 'complete') whenIdle();
  else window.addEventListener('load', whenIdle, { once: true });
}

if (stage && stops.length) setup(stage);
