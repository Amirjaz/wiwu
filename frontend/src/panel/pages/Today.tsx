import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { Notice } from '../../lib/ui';
import { fa, toman, when } from '../../lib/format';
import { message } from '../../lib/messages';
import { useLoad } from '../session';
import { Empty, OrderList, Skeleton, Title } from '../parts';
import type { OrderRow } from '../types';

interface Summary {
  counts: Record<string, number>;
  returns_open: number;
  unmatched: number;
  paid_today: { count: number; rial: number };
  last_auto_match: string | null;
  provider: string;
}

export default function Today() {
  const summary = useLoad<Summary>('/api/panel/summary/');
  const queue = useLoad<{ orders: OrderRow[] }>('/api/panel/orders/?queue=action');
  const s = summary.data;
  const count = (k: string) => s?.counts[k] ?? 0;

  const tiles = [
    { label: 'بررسی پرداخت', value: count('needs_review'), to: '/orders?queue=review', urgent: count('needs_review') > 0 },
    { label: 'آماده ارسال', value: count('paid') + count('preparing'), to: '/orders?queue=to_ship', urgent: false },
    { label: 'در انتظار پرداخت', value: count('awaiting_payment'), to: '/orders?queue=awaiting', urgent: false },
    { label: 'بازگشت باز', value: s?.returns_open ?? 0, to: '/returns', urgent: false },
  ];

  return (
    <>
      <Title>امروز</Title>
      {summary.error && <Notice tone="error" className="mb-6">{message(summary.error.error)}</Notice>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {tiles.map((t) => (
          <Link
            key={t.label}
            to={t.to}
            className={clsx('rounded-[var(--radius-surface)] border p-4 sm:p-5 grid gap-1', t.urgent ? 'border-warn bg-warn-soft' : 'border-line bg-raised hover:border-ink-soft')}
          >
            <span className="text-sm text-ink-soft">{t.label}</span>
            <span className="text-3xl font-black">{s ? fa(t.value) : '…'}</span>
          </Link>
        ))}
      </div>
      {s && (
        <div className="grid gap-3 sm:grid-cols-2 mb-8 text-ink-soft">
          <p className="rounded-[var(--radius-field)] bg-surface border border-line p-4">
            پرداخت‌شده امروز: <strong className="text-ink">{fa(s.paid_today.count)}</strong> سفارش، {toman(s.paid_today.rial)} تومان
          </p>
          <p className="rounded-[var(--radius-field)] bg-surface border border-line p-4">
            {s.provider === 'cartbecart' ? (
              <>آخرین تأیید خودکار: <strong className="text-ink">{s.last_auto_match ? when(s.last_auto_match) : 'هنوز نه'}</strong></>
            ) : (
              'تأیید خودکار خاموش است؛ پرداخت‌ها را دستی تأیید کنید.'
            )}
          </p>
          {s.unmatched > 0 && (
            <Notice tone="warn" className="sm:col-span-2">
              {fa(s.unmatched)} واریز در هفته گذشته به هیچ سفارشی نخورد. <Link to="/logs" className="underline">گزارش واریزها</Link>
            </Notice>
          )}
        </div>
      )}
      <h2 className="text-lg font-bold mb-3">نیاز به اقدام</h2>
      {queue.loading && !queue.data ? <Skeleton /> : queue.data?.orders.length ? <OrderList orders={queue.data.orders} /> : <Empty>کاری منتظر شما نیست.</Empty>}
    </>
  );
}
