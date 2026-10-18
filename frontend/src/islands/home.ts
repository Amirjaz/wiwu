// The home page's small interactions, besides the 3D bag (bag3d.ts): the hero's photo slider, the colour
// picker, the lock demo, and the tabs and numbers of the parts section. Everything here works by keyboard
// too.

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const fa = (n: number) => n.toLocaleString('fa-IR');

// The hero's photos, one at a time behind its text. Each has a bar that fills over --slide-time; when
// it's full the next photo fades in (the CSS animation is the clock, so pausing is pausing it). It waits
// while its controls are pointed at, while keyboard focus is in the hero, while it's touched or off
// screen; it stays put after the pause button, and never moves on its own for people who turn motion
// off. A swipe anywhere on the hero, the bars, or the arrow keys on them move it by hand. Right to left:
// the next photo is to the left.
function photoSlider() {
  const slider = document.querySelector<HTMLElement>('[data-slider]');
  const controls = slider?.querySelector<HTMLElement>('[data-slider-controls]');
  if (!slider || !controls) return;
  const slides = [...slider.querySelectorAll<HTMLImageElement>('[data-slide]')];
  const bars = [...controls.querySelectorAll<HTMLButtonElement>('[data-goto]')];
  const count = slider.querySelector<HTMLElement>('[data-slider-count]');
  const toggle = slider.querySelector<HTMLButtonElement>('[data-slider-toggle]');
  if (slides.length < 2) return;
  controls.hidden = false;

  let current = 0;
  let stopped = reducedMotion();
  const holds = new Set<string>();
  const sync = () => {
    slider.toggleAttribute('data-still', stopped);
    slider.toggleAttribute('data-paused', holds.size > 0);
    const [pause, play] = toggle?.querySelectorAll('.icon') ?? [];
    pause?.classList.toggle('hidden', stopped);
    play?.classList.toggle('hidden', !stopped);
    toggle?.setAttribute('aria-label', stopped ? 'پخش' : 'توقف');
  };
  const hold = (reason: string, on: boolean) => {
    if (on) holds.add(reason);
    else holds.delete(reason);
    sync();
  };

  const show = (index: number) => {
    const next = (index + slides.length) % slides.length;
    if (next === current) return;
    slides.forEach((slide, i) => {
      slide.toggleAttribute('data-was', i === current);
      slide.toggleAttribute('data-on', i === next);
      slide.setAttribute('aria-hidden', String(i !== next));
    });
    current = next;
    slides[(current + 1) % slides.length].hidden = false; // the one after starts loading
    bars.forEach((bar, i) => {
      bar.dataset.state = i < current ? 'done' : i === current ? 'on' : '';
      bar.setAttribute('aria-current', String(i === current));
    });
    if (count) count.textContent = `${fa(current + 1)} / ${fa(slides.length)}`;
  };

  // The other photos load once the page has (the first one is the page's largest picture).
  const reveal = () => slides.forEach((slide) => (slide.hidden = false));
  if (document.readyState === 'complete') reveal();
  else addEventListener('load', reveal, { once: true });

  controls.addEventListener('animationend', (event) => {
    if ((event.target as Element).closest('[data-goto]') === bars[current]) show(current + 1);
  });
  bars.forEach((bar, i) => bar.addEventListener('click', () => show(i)));
  toggle?.addEventListener('click', () => {
    stopped = !stopped;
    sync();
  });
  controls.addEventListener('keydown', (event) => {
    const step = event.key === 'ArrowLeft' ? 1 : event.key === 'ArrowRight' ? -1 : 0;
    if (step) show(current + step);
  });

  // The hero fills the screen, so a mouse anywhere on it would stop it for good: only the controls.
  controls.addEventListener('pointerenter', (event) => event.pointerType === 'mouse' && hold('pointer', true));
  controls.addEventListener('pointerleave', (event) => event.pointerType === 'mouse' && hold('pointer', false));
  // Keyboard focus only: a tapped bar keeps focus, and the photos shouldn't stop for good after a tap.
  slider.addEventListener('focusin', (event) => hold('focus', (event.target as Element).matches(':focus-visible')));
  slider.addEventListener('focusout', (event) => {
    if (!slider.contains(event.relatedTarget as Node | null)) hold('focus', false);
  });
  new IntersectionObserver(([entry]) => hold('away', !entry.isIntersecting)).observe(slider);

  // A sideways swipe anywhere but on a link or button; up and down still scroll the page (touch-action:
  // pan-y on the hero).
  let start: { x: number; y: number } | null = null;
  slider.addEventListener('pointerdown', (event) => {
    if ((event.pointerType === 'mouse' && event.button !== 0) || (event.target as Element).closest('a, button')) return;
    start = { x: event.clientX, y: event.clientY };
    hold('touch', true);
  });
  slider.addEventListener('pointerup', (event) => {
    hold('touch', false);
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    start = null;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx > 0 ? 1 : -1));
  });
  slider.addEventListener('pointercancel', () => {
    start = null;
    hold('touch', false);
  });
  sync();
}

// The header laid over the hero's photo (data-header="clear"): see-through until the hero has scrolled
// up under it, then solid as on the other pages (site.css).
function headerOverHero() {
  const header = document.querySelector<HTMLElement>('header[data-header="clear"]');
  const hero = document.getElementById('hero');
  if (!header || !hero) return;
  new IntersectionObserver(([entry]) => header.toggleAttribute('data-solid', !entry.isIntersecting), {
    rootMargin: `-${header.offsetHeight}px 0px 0px 0px`,
  }).observe(hero);
}

// Colour picker, shown once more than one colour is on show: the pick is named beside the dots and
// rides along to checkout on every buy link (?color=).
function colorPicker() {
  const picker = document.querySelector<HTMLElement>('[data-color-picker]');
  if (!picker) return;
  const dots = [...picker.querySelectorAll<HTMLButtonElement>('[data-color]')];
  const label = picker.querySelector<HTMLElement>('[data-color-label]');
  const pick = (dot: HTMLButtonElement) => {
    dots.forEach((other) => other.setAttribute('aria-checked', String(other === dot)));
    if (label) label.textContent = dot.dataset.colorName ?? '';
    document.querySelectorAll<HTMLAnchorElement>('a[href*="/checkout/"]').forEach((link) => {
      const url = new URL(link.href);
      url.searchParams.set('color', dot.dataset.color ?? '');
      link.href = url.pathname + url.search;
    });
  };
  const usable = dots.filter((dot) => dot.getAttribute('aria-disabled') !== 'true');
  usable.forEach((dot) => dot.addEventListener('click', () => pick(dot)));
  if (usable[0]) pick(usable[0]);
}

// Lock demo: hold the sensor for half a second (the real lock's speed) and the light turns green.
// Let go early and it asks again. It reads nothing: it's only a drawing that times the press.
function lockDemo() {
  const sensor = document.querySelector<HTMLButtonElement>('[data-sensor]');
  const status = document.querySelector<HTMLElement>('[data-sensor-status]');
  if (!sensor || !status) return;
  const HOLD = 500;
  const text = {
    idle: status.textContent ?? '',
    reading: 'در حال خواندن',
    open: 'باز شد، در نیم ثانیه',
    short: 'زود برداشتید؛ کمی بیشتر نگه دارید',
  };
  let timer = 0;
  let relock = 0;
  const set = (state: keyof typeof text) => {
    sensor.dataset.state = state === 'short' ? 'idle' : state;
    status.textContent = text[state];
  };
  const press = () => {
    if (sensor.dataset.state === 'reading') return;
    window.clearTimeout(relock);
    set('reading');
    timer = window.setTimeout(() => {
      set('open');
      relock = window.setTimeout(() => set('idle'), 2600);
    }, HOLD);
  };
  const release = () => {
    if (sensor.dataset.state !== 'reading') return;
    window.clearTimeout(timer);
    set('short');
  };
  sensor.addEventListener('pointerdown', (event) => {
    sensor.setPointerCapture(event.pointerId);
    press();
  });
  sensor.addEventListener('pointerup', release);
  sensor.addEventListener('pointercancel', release);
  sensor.addEventListener('contextmenu', (event) => event.preventDefault()); // long press on phones
  sensor.addEventListener('keydown', (event) => {
    if ((event.key === ' ' || event.key === 'Enter') && !event.repeat) {
      event.preventDefault();
      press();
    }
  });
  sensor.addEventListener('keyup', (event) => {
    if (event.key === ' ' || event.key === 'Enter') release();
  });
}

// Parts: a tab per side of the bag. Each side's numbers appear three times, in its group
// ([data-parts-group]): in the list, as pins on the 3D bag and on the side's photo (whichever of the two
// is showing). Pointing at a number lights it everywhere; a tap also turns the 3D bag to that part. The 3D
// (bag3d.ts) hears about it on the section: 'parts:view' (a side) and 'parts:focus' (a part).
function partsDiagram() {
  const section = document.getElementById('parts');
  if (!section) return;
  const tabs = [...section.querySelectorAll<HTMLButtonElement>('[role="tab"][data-parts-tab]')];
  const group = (key: string) => [...section.querySelectorAll<HTMLElement>(`[data-parts-group="${key}"]`)];
  const select = (tab: HTMLButtonElement, focus = false) => {
    if (focus) tab.focus();
    if (tab.getAttribute('aria-selected') === 'true') return;
    tabs.forEach((other) => {
      const on = other === tab;
      other.setAttribute('aria-selected', String(on));
      other.tabIndex = on ? 0 : -1;
      group(other.dataset.partsTab ?? '').forEach((el) => (el.hidden = !on));
    });
    section.dispatchEvent(new CustomEvent('parts:view', { detail: tab.dataset.partsTab }));
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', (event) => {
      // Right-to-left: the right arrow goes to the previous tab.
      const step = event.key === 'ArrowLeft' ? 1 : event.key === 'ArrowRight' ? -1 : 0;
      if (step) select(tabs[(i + step + tabs.length) % tabs.length], true);
    });
  });

  tabs.forEach((tab) => {
    const view = tab.dataset.partsTab ?? '';
    const items = group(view).flatMap((el) => [...el.querySelectorAll<HTMLElement>('[data-part]')]);
    const light = (part: string | null) =>
      items.forEach((item) => item.toggleAttribute('data-active', part !== null && item.dataset.part === part));
    // A mouse lights a part while it's over it; a tap lights it until the next tap.
    let tapped: string | null = null;
    items.forEach((item) => {
      const part = item.dataset.part ?? null;
      item.addEventListener('pointerenter', (event) => event.pointerType === 'mouse' && light(part));
      item.addEventListener('pointerleave', (event) => event.pointerType === 'mouse' && light(tapped));
      item.addEventListener('click', () => {
        tapped = part;
        light(part);
        section.dispatchEvent(new CustomEvent('parts:focus', { detail: { view, part: Number(part) } }));
      });
    });
    section.addEventListener('parts:view', () => {
      tapped = null;
      light(null);
    });
  });
}

photoSlider();
headerOverHero();
colorPicker();
lockDemo();
partsDiagram();
