import { useState } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import { isApiError, post } from '../../lib/api';
import { toman, when } from '../../lib/format';
import { message } from '../../lib/messages';
import { CopyButton, Field, Notice } from '../../lib/ui';
import { useLoad, useSession } from '../session';
import { Empty, Skeleton, Title } from '../parts';
import type { ReturnRow } from '../types';

function ReturnCard({ ret, onChange }: { ret: ReturnRow; onChange: (r: ReturnRow) => void }) {
  const { user } = useSession();
  const [reference, setReference] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const open = ret.status === 'requested' || ret.status === 'received';

  async function act(action: string, extra: Record<string, string> = {}, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    setProblem('');
    try {
      onChange(await post<ReturnRow>(`/api/panel/returns/${ret.id}/action/`, { action, ...extra }));
    } catch (err) {
      setProblem(isApiError(err) ? message(err.error) : message('unknown'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={clsx('rounded-[var(--radius-surface)] border bg-raised p-5 grid gap-3', open ? 'border-line-strong' : 'border-line opacity-80')}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to={`/orders/${ret.order_id}`} className="font-bold">سفارش <span className="ltr">{ret.code}</span> · {ret.name}</Link>
        <span className="rounded-full bg-surface border border-line px-3 py-1 text-sm font-semibold">{ret.status_label}</span>
      </div>
      <p className="text-ink-soft">{ret.reason}</p>
      <p className="text-sm text-muted">{when(ret.created)} · مبلغ کالا {toman(ret.amount_rial)} تومان</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="ltr font-semibold">{ret.sheba}</span>
        <span className="text-ink-soft">به نام {ret.holder}</span>
        <CopyButton text={ret.sheba} label="کپی شبا" />
      </div>
      {ret.reference && <p>شماره پیگیری بازپرداخت: <span className="ltr font-bold">{ret.reference}</span></p>}
      {problem && <Notice tone="error">{problem}</Notice>}
      {open && (
        <div className="grid gap-3">
          {ret.status === 'requested' && (
            <button type="button" className="btn btn-ghost justify-self-start" disabled={busy} onClick={() => act('received')}>کالا رسید</button>
          )}
          {user!.can.refund && (
            <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
              <Field label="شماره پیگیری واریز به شبای خریدار">
                {(id) => <input id={id} className="input ltr" inputMode="numeric" value={reference} onChange={(e) => setReference(e.target.value)} />}
              </Field>
              <button type="button" className="btn btn-primary" disabled={busy || reference.trim().length < 4}
                onClick={() => act('refund', { reference }, `بازپرداخت ${toman(ret.amount_rial)} تومان ثبت و به خریدار پیامک شود؟`)}>
                ثبت بازپرداخت
              </button>
            </div>
          )}
          {user!.can.refund && (
            <button type="button" className="justify-self-start text-danger underline underline-offset-4" disabled={busy}
              onClick={() => act('reject', {}, 'درخواست بازگشت رد شود؟')}>رد درخواست</button>
          )}
        </div>
      )}
    </li>
  );
}

export default function Returns() {
  const [onlyOpen, setOnlyOpen] = useState(true);
  const { data, setData, error, loading } = useLoad<{ returns: ReturnRow[] }>(`/api/panel/returns/?open=${onlyOpen ? 1 : 0}`);
  return (
    <>
      <Title aside={
        <label className="flex items-center gap-2 text-ink-soft">
          <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} /> فقط باز
        </label>
      }>بازگشت‌ها</Title>
      {error && <Notice tone="error" className="mb-4">{message(error.error)}</Notice>}
      {loading && !data ? <Skeleton /> : data?.returns.length ? (
        <ul className="grid gap-3">
          {data.returns.map((r) => (
            <ReturnCard key={r.id} ret={r} onChange={(next) => setData({ returns: data.returns.map((x) => (x.id === next.id ? next : x)) })} />
          ))}
        </ul>
      ) : <Empty>درخواست بازگشتی نیست.</Empty>}
    </>
  );
}
