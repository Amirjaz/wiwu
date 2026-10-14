import { StrictMode, useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import clsx from 'clsx';
import { CheckCircle, Clock, Fingerprint, Package, Truck, HouseLine, ArrowUUpLeft } from '@phosphor-icons/react';
import { get, islandData, isApiError, post, postForm } from '../lib/api';
import { clock, fa, groupCard, latin, toman, tomanPlain, when } from '../lib/format';
import { message } from '../lib/messages';
import { CopyButton, Field, Notice, useCountdown } from '../lib/ui';

type Status = 'awaiting_payment' | 'needs_review' | 'paid' | 'preparing' | 'shipped' | 'delivered' | 'expired' | 'cancelled';

interface Order {
  code: string;
  status: Status;
  status_label: string;
  created: string;
  expires: string;
  now: string;
  amount_rial: number;
  price_rial: number;
  shipping_rial: number;
  offset_rial: number;
  product: string;
  shipping: string;
  is_gift: boolean;
  name: string;
  city: string;
  card: { bank: string; number: string; holder: string } | null;
  claimed: boolean;
  tracking: string;
  paid_at: string | null;
  shipped_at: string | null;
  return: { status: string; label: string } | null;
  can_return: boolean;
  return_until: string | null;
}

const POLL_MS = 5000;
const CARD_TO_CARD_ATM_LIMIT_RIAL = 100_000_000; // some ATMs and apps stop at 10M toman per transfer

function useOrder(token: string) {
  const [order, setOrder] = useState<Order | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    try {
      setOrder(await get<Order>(`/api/orders/${token}/`));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  // While a payment can still arrive: poll, and check at once when the buyer comes back from
  // their bank app (the page was hidden, maybe even reloaded by an in-app browser).
  const waiting = order?.status === 'awaiting_payment' || order?.status === 'needs_review';
  useEffect(() => {
    if (!waiting) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, POLL_MS);
    const onVisible = () => document.visibilityState === 'visible' && load();
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, [waiting, load]);

  return { order, setOrder, failed, reload: load };
}

function Amount({ order }: { order: Order }) {
  return (
    <div className="grid gap-3">
      <p className="label">مبلغ دقیق واریز</p>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <p className="text-4xl sm:text-5xl font-black">{toman(order.amount_rial)} <span className="text-xl font-bold text-muted">تومان</span></p>
        <CopyButton text={tomanPlain(order.amount_rial)} label="کپی مبلغ" />
      </div>
      <p className="text-ink-soft leading-relaxed">
        دقیقاً همین مبلغ را بفرستید و گرد نکنید. {fa(Math.round(order.offset_rial / 10))} تومانِ آخر، شناسه واریز شماست تا پرداخت بی‌اشتباه به همین سفارش وصل شود.
      </p>
      <details className="text-sm text-muted">
        <summary className="cursor-pointer w-fit">ریز مبلغ</summary>
        <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-6 gap-y-1">
          <dt>{order.product}</dt><dd>{toman(order.price_rial)}</dd>
          <dt>ارسال ({order.shipping})</dt><dd>{toman(order.shipping_rial)}</dd>
          <dt>شناسه واریز</dt><dd>{toman(order.offset_rial)}</dd>
        </dl>
      </details>
    </div>
  );
}

function CardBox({ card }: { card: NonNullable<Order['card']> }) {
  return (
    <div className="grid gap-4 rounded-[var(--radius-surface)] bg-ink text-raised p-6 sm:p-7">
      <div className="flex items-center justify-between gap-4 text-raised/75">
        <span>{card.bank}</span>
        <Fingerprint size={26} aria-hidden />
      </div>
      <p className="ltr text-[1.6rem] sm:text-3xl font-bold text-start tracking-wide" dir="ltr">{fa(groupCard(card.number))}</p>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p>به نام <strong className="font-bold">{card.holder}</strong></p>
        <CopyButton text={card.number} label="کپی شماره کارت" className="!border-raised/30 !text-raised" />
      </div>
    </div>
  );
}

function ClaimForm({ token, onDone }: { token: string; onDone: (o: Order) => void }) {
  const [reference, setReference] = useState('');
  const [last4, setLast4] = useState('');
  const [time, setTime] = useState('');
  const [note, setNote] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem('');
    if (!reference.trim() && !file) {
      setProblem(message('claim_empty'));
      return;
    }
    const form = new FormData();
    form.append('reference', latin(reference));
    form.append('last4', latin(last4));
    form.append('time', time);
    form.append('note', note);
    if (file) form.append('file', file);
    setBusy(true);
    try {
      onDone(await postForm<Order>(`/api/orders/${token}/claim/`, form));
    } catch (err) {
      setProblem(isApiError(err) ? message(err.error) : message('unknown'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5 rounded-[var(--radius-surface)] border border-line bg-surface p-5 sm:p-6" noValidate>
      <p className="font-bold text-lg">اعلام پرداخت</p>
      <p className="text-ink-soft leading-relaxed -mt-2">اطلاعات واریز را از رسید اپ بانک بنویسید یا تصویر رسید را بفرستید. همکاران ما بررسی و سفارش را تأیید می‌کنند.</p>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="شماره پیگیری واریز">
          {(id) => <input id={id} className="input ltr text-right" inputMode="numeric" value={reference} onChange={(e) => setReference(e.target.value)} />}
        </Field>
        <Field label="۴ رقم آخر کارت شما">
          {(id) => <input id={id} className="input ltr text-right" inputMode="numeric" maxLength={4} value={last4} onChange={(e) => setLast4(latin(e.target.value).replace(/\D/g, '').slice(0, 4))} />}
        </Field>
        <Field label="ساعت واریز">
          {(id) => <input id={id} className="input" placeholder="مثلاً ۱۸:۴۰" value={time} onChange={(e) => setTime(e.target.value)} />}
        </Field>
        <Field label="تصویر رسید (اختیاری)" help="تصویر یا PDF، حداکثر ۶ مگابایت.">
          {(id, d) => <input id={id} aria-describedby={d} type="file" accept="image/*,application/pdf" className="input !min-h-0 py-2.5 text-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
        </Field>
      </div>
      <Field label="توضیح (اختیاری)">
        {(id) => <input id={id} className="input" value={note} onChange={(e) => setNote(e.target.value)} />}
      </Field>
      {problem && <Notice tone="error">{problem}</Notice>}
      <button type="submit" className="btn btn-primary justify-self-start" disabled={busy}>{busy ? 'در حال ارسال…' : 'ارسال اعلام پرداخت'}</button>
    </form>
  );
}

function Awaiting({ order, token, onUpdate }: { order: Order; token: string; onUpdate: (o: Order) => void }) {
  const left = useCountdown(order.expires, order.now);
  const [claiming, setClaiming] = useState(false);
  const overLimit = order.amount_rial > CARD_TO_CARD_ATM_LIMIT_RIAL;
  return (
    <div className="grid gap-8">
      <div className="grid gap-2">
        <h1 className="text-3xl sm:text-4xl font-extrabold">مبلغ را کارت‌به‌کارت کنید.</h1>
        <p className="text-ink-soft flex flex-wrap items-center gap-x-2">
          <Clock size={18} aria-hidden className="text-muted" />
          {left > 0 ? <>مهلت پرداخت: <span className="font-bold text-ink tabular-nums" aria-live="off">{clock(left)}</span></> : 'مهلت پرداخت تمام شد؛ اگر واریز کرده‌اید، اعلام پرداخت کنید.'}
        </p>
      </div>
      {order.card && <CardBox card={order.card} />}
      <Amount order={order} />
      {overLimit && (
        <Notice tone="warn">با اپ بانک خود واریز کنید. بعضی خودپردازها و اپ‌ها کارت‌به‌کارت بیش از ۱۰ میلیون تومان را در یک تراکنش قبول نمی‌کنند.</Notice>
      )}
      <div className="flex items-center gap-3 rounded-[var(--radius-field)] bg-accent-soft text-accent-ink px-4 py-3" role="status">
        <span className="relative flex size-2.5" aria-hidden>
          <span className="absolute inline-flex size-full rounded-full bg-accent opacity-60 motion-safe:animate-ping" />
          <span className="relative inline-flex size-2.5 rounded-full bg-accent" />
        </span>
        منتظر واریز شما هستیم. پس از تأیید، همین صفحه عوض می‌شود و پیامک می‌گیرید.
      </div>
      {claiming ? (
        <ClaimForm token={token} onDone={onUpdate} />
      ) : (
        <button type="button" className="justify-self-start text-ink-soft underline underline-offset-4" onClick={() => setClaiming(true)}>
          پرداخت کرده‌ام ولی تأیید نشده
        </button>
      )}
    </div>
  );
}

function Expired({ order, token, onUpdate }: { order: Order; token: string; onUpdate: (o: Order) => void }) {
  return (
    <div className="grid gap-6">
      <h1 className="text-3xl font-extrabold">مهلت پرداخت تمام شد.</h1>
      <p className="text-ink-soft leading-relaxed">اگر هنوز واریز نکرده‌اید، واریز نکنید و سفارش تازه‌ای ثبت کنید. اگر واریز کرده‌اید، نگران نباشید: اعلام پرداخت کنید تا سفارش‌تان تأیید شود.</p>
      <a href="/checkout/" className="btn btn-primary justify-self-start">ثبت سفارش تازه</a>
      {order.card && <p className="text-sm text-muted">کارت این سفارش: <span className="ltr">{fa(groupCard(order.card.number))}</span>، مبلغ {toman(order.amount_rial)} تومان.</p>}
      <ClaimForm token={token} onDone={onUpdate} />
    </div>
  );
}

const STEPS: { status: Status[]; label: string; Icon: typeof CheckCircle }[] = [
  { status: ['paid'], label: 'پرداخت تأیید شد', Icon: CheckCircle },
  { status: ['preparing'], label: 'در حال آماده‌سازی', Icon: Package },
  { status: ['shipped'], label: 'ارسال شد', Icon: Truck },
  { status: ['delivered'], label: 'تحویل شد', Icon: HouseLine },
];

function Progress({ order }: { order: Order }) {
  const current = STEPS.findIndex((s) => s.status.includes(order.status));
  return (
    <ol className="grid gap-0">
      {STEPS.map((step, i) => {
        const done = i <= current;
        return (
          <li key={step.label} className="flex gap-4">
            <div className="flex flex-col items-center">
              <span className={clsx('grid size-10 place-items-center rounded-full border-2', done ? 'border-accent bg-accent text-raised' : 'border-line-strong text-muted')}>
                <step.Icon size={20} aria-hidden />
              </span>
              {i < STEPS.length - 1 && <span className={clsx('w-0.5 flex-1 min-h-6', i < current ? 'bg-accent' : 'bg-line-strong')} />}
            </div>
            <div className="pb-6 pt-2">
              <p className={clsx('font-semibold', !done && 'text-muted')}>{step.label}</p>
              {i === 0 && order.paid_at && <p className="text-sm text-muted">{when(order.paid_at)}</p>}
              {i === 2 && order.shipped_at && <p className="text-sm text-muted">{when(order.shipped_at)}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ReturnForm({ token, until, onDone }: { token: string; until: string | null; onDone: (o: Order) => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [sheba, setSheba] = useState('');
  const [holder, setHolder] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState(false);

  if (!open) {
    return (
      <button type="button" className="btn btn-ghost justify-self-start" onClick={() => setOpen(true)}>
        <ArrowUUpLeft size={18} aria-hidden /> درخواست بازگشت
      </button>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setProblem('');
    setBusy(true);
    try {
      onDone(await post<Order>(`/api/orders/${token}/return/`, { reason, sheba: latin(sheba), holder }));
    } catch (err) {
      if (isApiError(err)) {
        setErrors(err.fields ?? {});
        setProblem(message(err.error));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5 rounded-[var(--radius-surface)] border border-line bg-surface p-5 sm:p-6" noValidate>
      <p className="font-bold text-lg">درخواست بازگشت</p>
      <p className="text-ink-soft leading-relaxed -mt-2">
        {until && <>تا {until} فرصت دارید. </>}
        کیف باید استفاده‌نشده و در بسته‌بندی اصلی باشد و اثر انگشت‌ها پاک شده باشند. مبلغ کالا به این شبا برمی‌گردد.
      </p>
      <Field label="دلیل بازگشت" error={errors.reason ? message(errors.reason) : undefined}>
        {(id, d) => <textarea id={id} aria-describedby={d} aria-invalid={!!errors.reason} className="input min-h-20" value={reason} onChange={(e) => setReason(e.target.value)} />}
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="شماره شبا" error={errors.sheba ? message(errors.sheba) : undefined} help="IR و ۲۴ رقم">
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.sheba} className="input ltr" placeholder="IR" value={sheba} onChange={(e) => setSheba(e.target.value)} />}
        </Field>
        <Field label="نام صاحب حساب" error={errors.holder ? message(errors.holder) : undefined}>
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.holder} className="input" value={holder} onChange={(e) => setHolder(e.target.value)} />}
        </Field>
      </div>
      {problem && <Notice tone="error">{problem}</Notice>}
      <div className="flex gap-3">
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'در حال ثبت…' : 'ثبت درخواست'}</button>
        <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>انصراف</button>
      </div>
    </form>
  );
}

function OrderView({ token }: { token: string }) {
  const { order, setOrder, failed, reload } = useOrder(token);

  if (!order) {
    return failed ? (
      <Notice tone="error">
        {message('network')} <button type="button" className="underline" onClick={reload}>دوباره</button>
      </Notice>
    ) : (
      <div className="grid gap-4 animate-pulse" aria-busy="true" aria-label="در حال بارگذاری">
        <div className="h-10 w-2/3 rounded-full bg-line" />
        <div className="h-44 rounded-[var(--radius-surface)] bg-line" />
        <div className="h-12 w-1/2 rounded-full bg-line" />
      </div>
    );
  }

  const header = (
    <p className="text-muted mb-6">
      سفارش <span className="ltr font-semibold text-ink">{order.code}</span> · {when(order.created)}
    </p>
  );

  if (order.status === 'awaiting_payment') return <>{header}<Awaiting order={order} token={token} onUpdate={setOrder} /></>;
  if (order.status === 'expired') return <>{header}<Expired order={order} token={token} onUpdate={setOrder} /></>;
  if (order.status === 'needs_review') {
    return (
      <>
        {header}
        <div className="grid gap-5">
          <h1 className="text-3xl font-extrabold">پرداخت شما در حال بررسی است.</h1>
          <p className="text-ink-soft leading-relaxed">همکاران ما واریز را با حساب بانکی تطبیق می‌دهند. نتیجه را پیامک می‌کنیم و همین صفحه هم به‌روز می‌شود.</p>
          {order.card && <p className="text-sm text-muted">مبلغ {toman(order.amount_rial)} تومان به کارت <span className="ltr">{fa(groupCard(order.card.number))}</span></p>}
        </div>
      </>
    );
  }
  if (order.status === 'cancelled') {
    return (
      <>
        {header}
        <div className="grid gap-5">
          <h1 className="text-3xl font-extrabold">این سفارش لغو شد.</h1>
          <p className="text-ink-soft leading-relaxed">اگر مبلغی واریز کرده‌اید که برنگشته، با شماره فروشگاه که پایین صفحه آمده تماس بگیرید و کد سفارش را بگویید.</p>
          <a href="/checkout/" className="btn btn-primary justify-self-start">ثبت سفارش تازه</a>
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <div className="grid gap-8">
        <div className="grid gap-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold">{order.status === 'delivered' ? 'سفارش تحویل شد.' : 'سفارش شما ثبت و پرداخت شد.'}</h1>
          <p className="text-ink-soft">{order.product} برای {order.name}، {order.city}{order.is_gift ? ' (هدیه)' : ''}</p>
        </div>
        <Progress order={order} />
        {order.tracking && (
          <div className="grid gap-2 rounded-[var(--radius-surface)] bg-surface border border-line p-5">
            <p className="label">کد رهگیری {order.shipping}</p>
            <div className="flex flex-wrap items-center gap-3">
              <p className="ltr text-2xl font-bold">{order.tracking}</p>
              <CopyButton text={order.tracking} label="کپی" />
            </div>
            <p className="text-sm text-muted">در سایت یا اپ {order.shipping} پیگیری کنید.</p>
          </div>
        )}
        {order.return ? (
          <Notice tone="info">درخواست بازگشت: {order.return.label}</Notice>
        ) : order.can_return ? (
          <ReturnForm token={token} until={order.return_until} onDone={setOrder} />
        ) : null}
      </div>
    </>
  );
}

function Root() {
  const { token } = useMemo(() => islandData<{ token: string }>(), []);
  return <OrderView token={token} />;
}

createRoot(document.getElementById('order-root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
