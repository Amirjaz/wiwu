import { useState } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { fa, toman, when } from '../../lib/format';
import { message } from '../../lib/messages';
import { Notice } from '../../lib/ui';
import { useLoad } from '../session';
import { Empty, Skeleton, Title } from '../parts';
import { ACTIONS } from '../types';

interface PaymentEvent { id: number; source: string; amount_rial: number | null; outcome: string; order: { id: number; code: string } | null; payload: unknown; at: string }
interface Sms { phone: string; kind: string; text: string; status: string; error: string; at: string; order: number | null }
interface Activity { action: string; detail: string; at: string; user: string | null; order: { id: number; code: string } | null }

const OUTCOMES: Record<string, string> = {
  matched: 'به سفارش خورد',
  late: 'دیر رسید، بررسی شود',
  second: 'واریز دوم برای سفارش پرداخت‌شده',
  repeat: 'تکراری از سرویس',
  unmatched: 'به هیچ سفارشی نخورد',
  unparsed: 'قابل خواندن نبود',
  unverified: 'تأیید نشد',
};

function Payments() {
  const { data, error } = useLoad<{ events: PaymentEvent[] }>('/api/panel/payments/');
  if (error) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!data) return <Skeleton />;
  if (!data.events.length) return <Empty>هنوز واریزی از سرویس تأیید خودکار نرسیده.</Empty>;
  return (
    <ul className="grid gap-2">
      {data.events.map((e) => (
        <li key={e.id} className={clsx('rounded-[var(--radius-field)] border bg-raised p-4 grid gap-1', ['unmatched', 'unparsed', 'unverified', 'late', 'second'].includes(e.outcome) ? 'border-warn' : 'border-line')}>
          <span className="font-semibold">{e.amount_rial ? `${toman(e.amount_rial)} تومان` : 'بدون مبلغ'} · {OUTCOMES[e.outcome] ?? e.outcome}</span>
          <span className="text-sm text-muted">{when(e.at)}{e.order && <> · <Link to={`/orders/${e.order.id}`} className="underline ltr">{e.order.code}</Link></>}</span>
          {['unparsed', 'unmatched'].includes(e.outcome) && (
            <details className="text-sm"><summary className="cursor-pointer text-ink-soft">داده خام</summary><pre className="ltr mt-2 overflow-x-auto rounded bg-surface p-3 text-xs">{JSON.stringify(e.payload, null, 2)}</pre></details>
          )}
        </li>
      ))}
    </ul>
  );
}

function SmsLog() {
  const { data, error } = useLoad<{ sms: Sms[] }>('/api/panel/sms/');
  if (error) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!data) return <Skeleton />;
  if (!data.sms.length) return <Empty>هنوز پیامکی فرستاده نشده.</Empty>;
  return (
    <ul className="grid gap-2">
      {data.sms.map((m, i) => (
        <li key={i} className={clsx('rounded-[var(--radius-field)] border bg-raised p-4 grid gap-1', m.status === 'failed' ? 'border-danger' : 'border-line')}>
          <span>{m.text}</span>
          <span className="text-sm text-muted">
            <span className="ltr">{fa(m.phone)}</span> · {when(m.at)} · {m.status === 'failed' ? `ناموفق: ${m.error}` : m.status === 'console' ? 'آزمایشی (فرستاده نشد)' : 'ارسال شد'}
            {m.order && <> · <Link to={`/orders/${m.order}`} className="underline">سفارش</Link></>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function ActivityLog() {
  const { data, error } = useLoad<{ items: Activity[] }>('/api/panel/activity/');
  if (error) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!data) return <Skeleton />;
  return (
    <ol className="grid gap-3">
      {data.items.map((a, i) => (
        <li key={i} className="grid gap-0.5">
          <span className="font-semibold">{ACTIONS[a.action] ?? a.action}{a.user ? ` · ${a.user}` : ''}{a.order && <> · <Link to={`/orders/${a.order.id}`} className="underline ltr">{a.order.code}</Link></>}</span>
          <span className="text-sm text-muted">{when(a.at)}{a.detail ? ` · ${a.detail}` : ''}</span>
        </li>
      ))}
    </ol>
  );
}

const TABS = [
  ['payments', 'واریزها'],
  ['sms', 'پیامک‌ها'],
  ['activity', 'کارها'],
] as const;

export default function Logs() {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('payments');
  return (
    <>
      <Title>گزارش‌ها</Title>
      <div className="flex gap-2 mb-5" role="tablist" aria-label="گزارش‌ها">
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
            className={clsx('rounded-full px-4 py-2 text-sm font-semibold border', tab === id ? 'bg-ink text-raised border-ink' : 'border-line-strong text-ink-soft')}>
            {label}
          </button>
        ))}
      </div>
      {tab === 'payments' ? <Payments /> : tab === 'sms' ? <SmsLog /> : <ActivityLog />}
    </>
  );
}
