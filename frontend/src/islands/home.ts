// The home page's small interactions: the hero's photo slider, the colour picker, the lock demo, and the
// parts section's tabs. Everything here works by keyboard too. (The 3D bag, islands/bag3d.ts, is off the
// page since 2026-10-23: pictures of the bags instead.)

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// The hero's pictures, one at a time behind its text, the next fading in after each one's --slide-time
// (the slider's 6 s, or the slide's own: the opening photo stays 3 s). No controls
// (Amir, 2026-10-20: the thumbnails crowded it): it waits while keyboard focus is in the hero, while it's
// touched, off screen or in a background tab, and never moves on its own for people who turn motion off.
// A sideways swipe anywhere on the hero moves it by hand (right to left: the next picture is to the left),
// and a colour dot picked in the hero brings up that colour's poster.
function photoSlider() {
  const slider = document.querySelector<HTMLElement>('[data-slider]');
  if (!slider) return;
  const slides = [...slider.querySelectorAll<HTMLElement>('[data-slide]')];
  if (slides.length < 2) return;
  const time = (slide: HTMLElement) => (parseFloat(getComputedStyle(slide).getPropertyValue('--slide-time')) || 6) * 1000;

  let current = 0;
  let timer = 0;
  // The first picture's time counts from when it shows, not from when the script runs: on a slow
  // connection the opening photo's 3 seconds were mostly spent loading it.
  let started = false;
  const holds = new Set<string>();
  const schedule = () => {
    window.clearTimeout(timer);
    slider.toggleAttribute('data-paused', holds.size > 0);
    if (started && !holds.size && !reducedMotion()) timer = window.setTimeout(() => show(current + 1), time(slides[current]));
  };
  const hold = (reason: string, on: boolean) => {
    if (on) holds.add(reason);
    else holds.delete(reason);
    schedule();
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
    schedule();
  };

  // The other pictures load once the page has (the first one is the page's largest picture).
  const reveal = () => slides.forEach((slide) => (slide.hidden = false));
  if (document.readyState === 'complete') reveal();
  else addEventListener('load', reveal, { once: true });

  // Keyboard focus only: a tapped link keeps focus, and the pictures shouldn't stop for good after a tap.
  slider.addEventListener('focusin', (event) => hold('focus', (event.target as Element).matches(':focus-visible')));
  slider.addEventListener('focusout', (event) => {
    if (!slider.contains(event.relatedTarget as Node | null)) hold('focus', false);
  });
  new IntersectionObserver(([entry]) => hold('away', !entry.isIntersecting)).observe(slider);
  document.addEventListener('visibilitychange', () => hold('hidden', document.hidden));
  slider.addEventListener('color:picked', (event) => {
    const poster = slides.findIndex((slide) => slide.dataset.colorName === (event as CustomEvent<string>).detail);
    if (poster >= 0) show(poster);
  });

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
  const begin = () => {
    started = true;
    schedule();
  };
  const first = slides[0].querySelector<HTMLImageElement>('.slide-main, picture img');
  if (!first || first.complete) begin();
  else {
    first.addEventListener('load', begin, { once: true });
    first.addEventListener('error', begin, { once: true });
  }
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

// The colour picker in the hero, shown once more than one colour is on show: the pick is named beside the
// dots and rides along to checkout on every buy link (?color=).
function colorPicker() {
  const pickers = [...document.querySelectorAll<HTMLElement>('[data-color-picker]')];
  if (!pickers.length) return;
  const dots = pickers.flatMap((picker) => [...picker.querySelectorAll<HTMLButtonElement>('[data-color]')]);
  const pick = (id: string) => {
    let chosen: HTMLButtonElement | undefined;
    dots.forEach((dot) => {
      const on = dot.dataset.color === id;
      dot.setAttribute('aria-checked', String(on));
      if (on) chosen = dot;
    });
    if (!chosen) return;
    pickers.forEach((picker) => {
      const label = picker.querySelector<HTMLElement>('[data-color-label]');
      if (label) label.textContent = chosen?.dataset.colorName ?? '';
    });
    // (Not the links to one bag in one colour: the parts section's pictures, the two-zipper section, the
    // closing section.)
    document.querySelectorAll<HTMLAnchorElement>('a[href*="/checkout/"]:not([data-color-link])').forEach((link) => {
      const url = new URL(link.href);
      url.searchParams.set('color', id);
      link.href = url.pathname + url.search;
    });
  };
  const usable = dots.filter((dot) => dot.getAttribute('aria-disabled') !== 'true');
  usable.forEach((dot) => dot.addEventListener('click', () => {
    pick(dot.dataset.color ?? '');
    // Told to the section it was picked in: the hero shows that colour's poster.
    dot.dispatchEvent(new CustomEvent('color:picked', { bubbles: true, detail: dot.dataset.colorName }));
  }));
  if (usable[0]) pick(usable[0].dataset.color ?? '');
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

// Parts: a tab per side of the bag, each showing that side's list ([data-parts-group]).
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
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', (event) => {
      // Right-to-left: the right arrow goes to the previous tab.
      const step = event.key === 'ArrowLeft' ? 1 : event.key === 'ArrowRight' ? -1 : 0;
      if (step) select(tabs[(i + step + tabs.length) % tabs.length], true);
    });
  });
}

photoSlider();
headerOverHero();
colorPicker();
lockDemo();
partsDiagram();
