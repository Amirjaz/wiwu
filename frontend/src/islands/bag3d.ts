// The bag in 3D, in the parts section (#parts). On devices that can take it the stage shows the bag
// (bag3d/scene.ts): each tab turns it to that side with the side's numbered pins on it, a tapped row or
// pin turns it to that part, and it can be dragged round. The tabs, the list and the lit numbers are
// home.ts's (partsDiagram), which says what was picked through 'parts:view' and 'parts:focus' on the
// section. Each side also has a photo with the same numbers ([data-parts-photo]), the backup: shown where
// the 3D can't run, and where it fails or takes longer than PHOTO_DELAY. Until then a thin line shows the
// model loading. The model only loads once the page has, the section is about a screen away and the hero
// has moved past its opening photo: the hero's photos come first.
import type { BagScene, Pin } from '../bag3d/scene';

const PHOTO_DELAY = 6000;
const section = document.getElementById('parts');
const stage = section?.querySelector<HTMLElement>('[data-bag-stage]');

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

const vector = (text = '') => text.split(' ').map(Number) as [number, number, number];

function setup(section: HTMLElement, stage: HTMLElement) {
  const hint = stage.querySelector<HTMLElement>('[data-drag-hint]');
  const loading = stage.querySelector<HTMLElement>('[data-bag-loading]');
  const progress = loading?.querySelector<HTMLElement>('[data-bag-progress]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const small = Math.min(screen.width, screen.height) < 768;

  // Each side's pins: the numbers on the stage, and where they sit on the bag.
  const pinSets = new Map<string, { el: HTMLElement; pin: Pin }[]>();
  stage.querySelectorAll<HTMLElement>('[data-pins]').forEach((layer) => {
    const pins = [...layer.querySelectorAll<HTMLElement>('[data-pin]')].map((el) => ({
      el, pin: { at: vector(el.dataset.at), normal: vector(el.dataset.normal) },
    }));
    pinSets.set(layer.dataset.partsGroup ?? '', pins);
  });
  const pinsOf = (view: string) => (pinSets.get(view) ?? []).map(({ pin }) => pin);
  let view = section.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.dataset.partsTab ?? 'front';
  let scene: BagScene | null = null;

  // Numbers set off to the side ([data-lead], the lock's: its parts are a centimetre apart) are kept a
  // number's height apart, as a group around where they point; their lines bend to reach them.
  const GAP = 30;
  const placePins = (positions: ({ x: number; y: number } | null)[]) => {
    const leads: { el: HTMLElement; y: number }[] = [];
    pinSets.get(view)?.forEach(({ el }, i) => {
      const pos = positions[i];
      el.hidden = !pos;
      if (!pos) return;
      el.style.translate = `${pos.x.toFixed(1)}px ${pos.y.toFixed(1)}px`;
      if (el.hasAttribute('data-lead')) leads.push({ el, y: pos.y });
    });
    leads.sort((a, b) => a.y - b.y);
    const spread = leads.map((lead) => lead.y);
    for (let i = 1; i < spread.length; i++) spread[i] = Math.max(spread[i], spread[i - 1] + GAP);
    const shift = leads.reduce((sum, lead, i) => sum + lead.y - spread[i], 0) / (leads.length || 1);
    leads.forEach((lead, i) => {
      const dy = (spread[i] + shift - lead.y).toFixed(1);
      lead.el.querySelector<HTMLElement>('[data-pin-number]')!.style.top = `${dy}px`;
      lead.el.querySelector('line')?.setAttribute('y2', dy);
    });
  };
  section.addEventListener('parts:view', (event) => {
    view = (event as CustomEvent<string>).detail;
    scene?.show(view, pinsOf(view));
  });
  // The colour picked on the page (home.ts), now or before the model loaded.
  document.addEventListener('bag:color', (event) => scene?.setColor((event as CustomEvent<string>).detail));
  section.addEventListener('parts:focus', (event) => {
    const detail = (event as CustomEvent<{ view: string; part: number }>).detail;
    const pin = pinSets.get(detail.view)?.[detail.part - 1]?.pin;
    if (pin) scene?.focus(pin);
  });
  // The hint has done its job once someone touches the bag.
  stage.addEventListener('pointerdown', (event) => event.target instanceof HTMLCanvasElement && hint?.remove());

  const showPhotos = () => {
    stage.removeAttribute('data-pending');
    stage.setAttribute('data-photos', '');
  };
  if (!canRender3d()) {
    showPhotos();
    return;
  }
  stage.setAttribute('data-pending', '');

  const load3d = async () => {
    const slow = window.setTimeout(showPhotos, PHOTO_DELAY);
    const onProgress = (fraction: number | null) => {
      if (!loading || !progress || fraction === null) return;
      loading.setAttribute('data-known', '');
      progress.style.transform = `scaleX(${fraction})`;
    };
    let created: BagScene | null = null;
    try {
      const { BagScene } = await import('../bag3d/scene');
      const instance = (created = new BagScene(stage, { reducedMotion, small, onPins: placePins }));
      const picked = document.documentElement.dataset.bagColor;
      if (picked) instance.setColor(picked);
      const visibility = new IntersectionObserver(([entry]) => instance.setVisible(entry.isIntersecting));
      visibility.observe(section);
      document.addEventListener('visibilitychange', () => instance.setVisible(!document.hidden));
      await instance.load((small ? stage.dataset.modelSmall : stage.dataset.model) ?? '', onProgress);
      if (!instance.drawsTheBag()) throw new Error('the 3D bag drew nothing');
      // If the browser drops the GPU later (it can, under memory pressure), the picture takes over.
      stage.querySelector('canvas')?.addEventListener('webglcontextlost', () => {
        instance.dispose();
        scene = null;
        stage.removeAttribute('data-3d');
        showPhotos();
      }, { once: true });
      scene = instance;
      const latest = document.documentElement.dataset.bagColor; // picked while it loaded
      if (latest) instance.setColor(latest);
      window.clearTimeout(slow);
      instance.show(view, pinsOf(view), true);
      stage.removeAttribute('data-pending');
      stage.removeAttribute('data-photos');
      stage.setAttribute('data-3d', '');
      if (hint) hint.hidden = false;
      if (import.meta.env.DEV) (window as unknown as { __bag: BagScene }).__bag = instance;
    } catch (error) {
      // The picture takes over (and the canvas goes, blank or half drawn); the section works the same.
      window.clearTimeout(slow);
      (created as BagScene | null)?.dispose();
      showPhotos();
      console.warn('3D bag unavailable', error);
    }
  };

  // Not while the hero's opening photo is up: starting the 3D holds the page for a second or more, and its
  // 3 seconds stretched to 5 (2026-10-21). The hero says when it moves on (home.ts); scrolling, or a
  // slider that won't move by itself, doesn't wait.
  const heroDone = new Promise<void>((resolve) => {
    const slider = document.querySelector('[data-slider]');
    if (!slider || slider.hasAttribute('data-moved') || reducedMotion || scrollY > 0) return resolve();
    addEventListener('scroll', () => resolve(), { once: true, passive: true });
    document.addEventListener('hero:moved', () => resolve(), { once: true });
  });
  const near = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      near.disconnect();
      heroDone.then(load3d);
    },
    { rootMargin: '100% 0px' },
  );
  if (document.readyState === 'complete') near.observe(section);
  else addEventListener('load', () => near.observe(section), { once: true });
}

if (section && stage) setup(section, stage);
