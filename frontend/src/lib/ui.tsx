import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Check, Copy, WarningCircle, Info, CheckCircle } from '@phosphor-icons/react';
import clsx from 'clsx';

/** A form field: label above, the control, help or error below. */
export function Field(props: {
  label: string;
  error?: string;
  help?: ReactNode;
  children: (id: string, describedBy: string | undefined) => ReactNode;
  className?: string;
}) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = props.error || props.help;
  return (
    <div className={clsx('grid gap-2', props.className)}>
      <label htmlFor={id} className="label">{props.label}</label>
      {props.children(id, note ? noteId : undefined)}
      {props.error ? (
        <p id={noteId} className="error-text">{props.error}</p>
      ) : props.help ? (
        <p id={noteId} className="help">{props.help}</p>
      ) : null}
    </div>
  );
}

export function Notice(props: { tone?: 'info' | 'warn' | 'error' | 'ok'; children: ReactNode; className?: string }) {
  const tone = props.tone ?? 'info';
  const Icon = tone === 'ok' ? CheckCircle : tone === 'info' ? Info : WarningCircle;
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={clsx(
        'flex gap-3 rounded-[var(--radius-field)] p-4 leading-relaxed',
        tone === 'info' && 'bg-surface border border-line text-ink-soft',
        tone === 'warn' && 'bg-warn-soft text-warn',
        tone === 'error' && 'bg-danger-soft text-danger',
        tone === 'ok' && 'bg-accent-soft text-accent-ink',
        props.className,
      )}
    >
      <Icon size={22} className="mt-0.5 flex-none" aria-hidden />
      <div className="min-w-0">{props.children}</div>
    </div>
  );
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // In-app browsers (Instagram, Telegram) often block the clipboard API.
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

export function CopyButton(props: { text: string; label: string; className?: string }) {
  const [state, setState] = useState<'idle' | 'done' | 'failed'>('idle');
  const timer = useRef<number>();
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return (
    <button
      type="button"
      className={clsx('btn btn-ghost btn-sm', props.className)}
      onClick={async () => {
        setState((await writeClipboard(props.text)) ? 'done' : 'failed');
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setState('idle'), 2200);
      }}
    >
      {state === 'done' ? <Check size={18} aria-hidden /> : <Copy size={18} aria-hidden />}
      <span aria-live="polite">{state === 'done' ? 'کپی شد' : state === 'failed' ? 'کپی نشد؛ دستی بنویسید' : props.label}</span>
    </button>
  );
}

/** Milliseconds left until `until`, corrected for the gap between this device's clock and the server's. */
export function useCountdown(until: string | null, serverNow: string | null): number {
  const skew = useRef(0);
  useEffect(() => {
    if (serverNow) skew.current = new Date(serverNow).getTime() - Date.now();
  }, [serverNow]);
  const [left, setLeft] = useState(() => (until ? new Date(until).getTime() - Date.now() : 0));
  useEffect(() => {
    if (!until) return;
    const tick = () => setLeft(new Date(until).getTime() - (Date.now() + skew.current));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [until]);
  return left;
}
