import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import { MagnifyingGlass } from '@phosphor-icons/react';
import { Notice } from '../../lib/ui';
import { fa } from '../../lib/format';
import { message } from '../../lib/messages';
import { useLoad } from '../session';
import { Empty, OrderList, Skeleton, Title } from '../parts';
import type { OrderRow } from '../types';

const QUEUES: [string, string][] = [
  ['action', 'نیاز به اقدام'],
  ['review', 'بررسی پرداخت'],
  ['to_ship', 'آماده ارسال'],
  ['awaiting', 'در انتظار پرداخت'],
  ['shipped', 'ارسال‌شده'],
  ['delivered', 'تحویل‌شده'],
  ['closed', 'منقضی و لغو'],
  ['all', 'همه'],
];

export default function Orders() {
  const [params, setParams] = useSearchParams();
  const queue = params.get('queue') || 'action';
  const page = Number(params.get('page') || 1);
  const q = params.get('q') || '';
  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);

  const url = `/api/panel/orders/?queue=${queue}&page=${page}&q=${encodeURIComponent(q)}`;
  const { data, error, loading } = useLoad<{ orders: OrderRow[]; total: number; page_size: number }>(url);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const go = (changes: Record<string, string>) => setParams({ queue, page: '1', q, ...changes });

  return (
    <>
      <Title>سفارش‌ها</Title>
      <form
        className="relative mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          go({ q: search, queue: search ? 'all' : queue });
        }}
      >
        <label htmlFor="order-search" className="sr-only">جستجو</label>
        <input id="order-search" className="input pe-12" placeholder="کد سفارش، موبایل، نام، کد رهگیری یا کد پرداخت" value={search} onChange={(e) => setSearch(e.target.value)} />
        <button type="submit" className="absolute inset-y-0 end-0 px-4 text-muted" aria-label="جستجو"><MagnifyingGlass size={20} /></button>
      </form>
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 -mx-4 px-4 snap-x" role="tablist" aria-label="صف سفارش‌ها">
        {QUEUES.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={queue === id}
            onClick={() => go({ queue: id, q: '' })}
            className={clsx('snap-start whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold border', queue === id ? 'bg-ink text-raised border-ink' : 'border-line-strong text-ink-soft')}
          >
            {label}
          </button>
        ))}
      </div>
      {error && <Notice tone="error" className="mb-4">{message(error.error)}</Notice>}
      {loading && !data ? <Skeleton /> : data?.orders.length ? <OrderList orders={data.orders} /> : <Empty>سفارشی اینجا نیست.</Empty>}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <button type="button" className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => go({ page: String(page - 1) })}>قبلی</button>
          <span className="text-muted">{fa(page)} از {fa(pages)}</span>
          <button type="button" className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => go({ page: String(page + 1) })}>بعدی</button>
        </div>
      )}
    </>
  );
}
