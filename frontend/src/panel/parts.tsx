import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { Gift, ChatCircleText } from '@phosphor-icons/react';
import { fa, toman, when } from '../lib/format';
import { STATUS_TONE, type OrderRow, type Status } from './types';

export function Title({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
      <h1 className="text-2xl sm:text-3xl font-extrabold">{children}</h1>
      {aside}
    </div>
  );
}

export function Chip({ status, label }: { status: Status; label: string }) {
  return <span className={clsx('inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold whitespace-nowrap', STATUS_TONE[status])}>{label}</span>;
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="grid gap-3 animate-pulse" aria-busy="true" aria-label="در حال بارگذاری">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="h-20 rounded-[var(--radius-field)] bg-line/70" />)}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-[var(--radius-surface)] border border-dashed border-line-strong p-8 text-center text-muted">{children}</p>;
}

export function OrderList({ orders }: { orders: OrderRow[] }) {
  return (
    <ul className="grid gap-2">
      {orders.map((o) => (
        <li key={o.id}>
          <Link to={`/orders/${o.id}`} className="grid gap-2 rounded-[var(--radius-field)] border border-line bg-raised p-4 hover:border-ink-soft sm:grid-cols-[1fr_auto] sm:items-center">
            <span className="grid gap-0.5 min-w-0">
              <span className="flex flex-wrap items-center gap-2 font-bold">
                <span className="ltr">{o.code}</span>
                <span className="font-semibold text-ink-soft truncate">{o.name}</span>
                {o.is_gift && <Gift size={18} className="text-muted" aria-label="هدیه" />}
                {o.claimed && <ChatCircleText size={18} className="text-warn" aria-label="خریدار اعلام پرداخت کرده" />}
              </span>
              <span className="text-sm text-muted">
                {when(o.created)} · {o.city} · {o.shipping} · <span className="ltr">{fa(o.phone)}</span>
              </span>
            </span>
            <span className="flex items-center justify-between gap-3 sm:justify-end">
              <span className="font-bold">{toman(o.amount_rial)} <span className="text-sm text-muted font-medium">تومان</span></span>
              <Chip status={o.status} label={o.status_label} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
