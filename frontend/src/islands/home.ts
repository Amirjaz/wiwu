// The home page's small interactions, besides the 3D (hero.ts): the view switcher under the bag, the
// lock demo, and the tabs and markers of the parts diagram. Everything here works by keyboard too.

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

// View switcher: names the tour's five views and follows the tour (hero.ts sends 'hero:stop'). A tap
// scrolls that view's text to where the tour picks it up: the middle of the screen, or on phones the
// middle of what the pinned bag leaves visible.
function viewSwitcher() {
  const stage = document.querySelector<HTMLElement>('[data-hero-stage]');
  const views = [...document.querySelectorAll<HTMLButtonElement>('[data-view]')];
  const mark = (index: number) =>
    views.forEach((view) => view.setAttribute('aria-current', String(Number(view.dataset.view) === index)));
  stage?.addEventListener('hero:stop', (event) => mark((event as CustomEvent<number>).detail));
  views.forEach((view) =>
    view.addEventListener('click', () => {
      const index = Number(view.dataset.view);
      const stop = document.querySelector<HTMLElement>(`[data-stop="${index}"]`);
      if (!stop) return;
      const narrow = matchMedia('(max-width: 767px)').matches;
      const top = index === 0 ? 0 : stop.getBoundingClientRect().top + scrollY - innerHeight * (narrow ? 0.5 : 0.3);
      scrollTo({ top, behavior: reducedMotion() ? 'auto' : 'smooth' });
    }),
  );
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

// Parts diagram: one tab per photo; pointing at a marker or its line in the list lights up both.
function partsDiagram() {
  const tabs = [...document.querySelectorAll<HTMLButtonElement>('[role="tab"][data-parts-tab]')];
  const select = (tab: HTMLButtonElement, focus = false) => {
    tabs.forEach((other) => {
      const on = other === tab;
      other.setAttribute('aria-selected', String(on));
      other.tabIndex = on ? 0 : -1;
      document.getElementById(other.getAttribute('aria-controls') ?? '')?.toggleAttribute('hidden', !on);
    });
    if (focus) tab.focus();
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', (event) => {
      // Right-to-left: the right arrow goes to the previous tab.
      const step = event.key === 'ArrowLeft' ? 1 : event.key === 'ArrowRight' ? -1 : 0;
      if (step) select(tabs[(i + step + tabs.length) % tabs.length], true);
    });
  });

  document.querySelectorAll<HTMLElement>('[data-parts-panel]').forEach((panel) => {
    const items = [...panel.querySelectorAll<HTMLElement>('[data-part]')];
    const light = (part: string | null) =>
      items.forEach((item) => item.toggleAttribute('data-active', part !== null && item.dataset.part === part));
    // A mouse lights a part while it's over it; a tap lights it until the next tap.
    items.forEach((item) => {
      item.addEventListener('pointerenter', (event) => event.pointerType === 'mouse' && light(item.dataset.part ?? null));
      item.addEventListener('pointerleave', (event) => event.pointerType === 'mouse' && light(null));
      item.addEventListener('click', () => light(item.dataset.part ?? null));
    });
  });
}

viewSwitcher();
lockDemo();
partsDiagram();
