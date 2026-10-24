import { useState, type FormEvent, type ReactNode } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowRight, Printer, Phone, Gift, Paperclip } from '@phosphor-icons/react';
import { isApiError, post } from '../../lib/api';
import { fa, groupCard, rial, shippingFee, toman, when } from '../../lib/format';
import { message } from '../../lib/messages';
import { CopyButton, Field, Notice } from '../../lib/ui';
import { useLoad, useSession } from '../session';
import { Chip, Skeleton } from '../parts';
import { ACTIONS, type OrderDetail } from '../types';

function Box({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[var(--radius-surface)] border border-line bg-raised p-5 grid gap-3 content-start">
      <h2 className="font-bold">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <span className="text-muted">{label}</span>
      <span className="font-semibold">{children}</span>
    </div>
  );
}

export default function OrderPage() {
  const { id } = useParams();
  const { user } = useSession();
  const { data: order, setData, error, reload } = useLoad<OrderDetail>(`/api/panel/orders/${id}/`);
  const [busy, setBusy] = useState('');
  const [problem, setProblem] = useState('');
  const [tracking, setTracking] = useState('');
  const [note, setNote] = useState<string | null>(null);

  async function act(action: string, extra: Record<string, string> = {}, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(action);
    setProblem('');
    try {
      setData(await post<OrderDetail>(`/api/panel/orders/${id}/action/`, { action, ...extra }));
      if (action === 'note') setNote(null);
    } catch (err) {
      if (isApiError(err)) {
        setProblem(message(err.error));
        if (err.error === 'state') reload();
      }
    } finally {
      setBusy('');
    }
  }

  if (error && !order) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!order) return <Skeleton rows={6} />;

  const can = user!.can;
  const reviewable = ['awaiting_payment', 'needs_review', 'expired'].includes(order.status);
  const shippable = ['paid', 'preparing'].includes(order.status);
  const cancellable = ['awaiting_payment', 'needs_review', 'expired', 'paid', 'preparing'].includes(order.status);
  const address = `${order.province}، ${order.city}، ${order.address}`;
  const amount = (rialAmount: number) => (order.pay_in_rial ? `${rial(rialAmount)} ریال` : `${toman(rialAmount)} تومان`);
  const split = order.transfers.length > 1;
  const looking = split ? order.transfers.map((t) => amount(t.amount_rial)).join(' و ') : amount(order.amount_rial);

  function ship(event: FormEvent) {
    event.preventDefault();
    act('ship', { tracking });
  }

  return (
    <div className="grid gap-5">
      <Link to="/orders" className="inline-flex items-center gap-1 text-ink-soft w-fit"><ArrowRight size={18} aria-hidden /> سفارش‌ها</Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl sm:text-3xl font-extrabold">سفارش <span className="ltr">{order.code}</span></h1>
        <Chip status={order.status} label={order.status_label} />
        {order.is_gift && <span className="inline-flex items-center gap-1 rounded-full bg-surface border border-line px-3 py-1 text-sm"><Gift size={16} aria-hidden /> هدیه</span>}
      </div>
      {problem && <Notice tone="error">{problem}</Notice>}

      {reviewable && (
        <Box title="پرداخت">
          {order.sheba && (
            <p className="text-ink-soft leading-relaxed">
              خریدار <strong className="text-ink">شبا</strong> را انتخاب کرده: در حساب شبای <span className="ltr font-semibold text-ink">{order.sheba.number}</span>
              {order.sheba.bank && ` (${order.sheba.bank})`} دنبال یک واریز دقیق <strong className="text-ink">{amount(order.amount_rial)}</strong> بگردید.
              اگر به کارت هم واریز کرده باشد، کارت‌به‌کارت خودکار تأییدش می‌کند.
            </p>
          )}
          <p className={order.sheba ? 'text-sm text-muted leading-relaxed' : 'text-ink-soft leading-relaxed'}>
            {order.sheba && 'یا '}در حساب کارت <span className="ltr font-semibold text-ink">{fa(groupCard(order.card.number))}</span> ({order.card.bank})
            {split
              ? <> دنبال {fa(order.transfers.length)} واریز جدا با این مبلغ‌های دقیق بگردید: <strong className="text-ink">{looking}</strong>.</>
              : <> دنبال واریز دقیق <strong className="text-ink">{looking}</strong> بگردید.</>}
          </p>
          {split && (
            <ul className="grid gap-1 text-sm">
              {order.transfers.map((t) => (
                <li key={t.position} className="flex flex-wrap gap-x-3">
                  <span>واریز {fa(t.position)}: {amount(t.amount_rial)}</span>
                  <span className={t.status === 'paid' ? 'text-accent-ink font-semibold' : 'text-muted'}>{t.status_label}{t.paid_at ? ` (${when(t.paid_at)})` : ''}</span>
                  {t.provider_ref && <span className="ltr text-muted">{t.provider_ref}</span>}
                </li>
              ))}
            </ul>
          )}
          {order.claim.at ? (
            <div className="grid gap-2 rounded-[var(--radius-field)] bg-warn-soft text-warn p-4">
              <p className="font-semibold">خریدار اعلام پرداخت کرده ({when(order.claim.at)})</p>
              {order.claim.reference && <p>شماره پیگیری: <span className="ltr font-bold">{order.claim.reference}</span></p>}
              {order.claim.last4 && <p>۴ رقم آخر کارت خریدار: <span className="ltr font-bold">{fa(order.claim.last4)}</span></p>}
              {order.claim.time && <p>زمان واریز: {order.claim.time}</p>}
              {order.claim.note && <p>توضیح: {order.claim.note}</p>}
              {order.claim.file && (
                <a href={`/api/panel/orders/${order.id}/claim-file/`} target="_blank" rel="noopener" className="inline-flex items-center gap-1 underline w-fit">
                  <Paperclip size={18} aria-hidden /> تصویر رسید
                </a>
              )}
            </div>
          ) : order.status === 'awaiting_payment' ? (
            <p className="text-sm text-muted">مهلت پرداخت تا {when(order.expires)}</p>
          ) : null}
          {can.approve ? (
            <div className="flex flex-wrap gap-3">
              <button type="button" className="btn btn-primary" disabled={!!busy}
                onClick={() => act('approve', {}, `${split ? `هر ${fa(order.transfers.length)} واریز (${looking})` : `واریز ${looking}`} را در حساب دیدید؟ سفارش پرداخت‌شده ثبت می‌شود و به خریدار پیامک می‌رود.`)}>
                {busy === 'approve' ? '…' : 'تأیید پرداخت'}
              </button>
              {order.status === 'needs_review' && (
                <button type="button" className="btn btn-ghost" disabled={!!busy}
                  onClick={() => act('reject', {}, 'واریزی پیدا نشد؟ سفارش لغو و به خریدار پیامک می‌شود.')}>رد پرداخت</button>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted">تأیید پرداخت با مدیر فروشگاه است.</p>
          )}
        </Box>
      )}

      {shippable && (
        <Box title="ارسال">
          <div className="flex flex-wrap gap-3">
            <a href={`/panel/slip/${order.id}/`} target="_blank" rel="noopener" className="btn btn-ghost"><Printer size={18} aria-hidden /> چاپ برچسب و برگه بسته</a>
            {order.status === 'paid' && <button type="button" className="btn btn-ghost" disabled={!!busy} onClick={() => act('preparing')}>شروع آماده‌سازی</button>}
          </div>
          <form onSubmit={ship} className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <Field label={`کد رهگیری ${order.shipping}`}>
              {(fid) => <input id={fid} className="input ltr" inputMode="numeric" value={tracking} onChange={(e) => setTracking(e.target.value)} />}
            </Field>
            <button type="submit" className="btn btn-primary" disabled={!!busy || tracking.trim().length < 4}>{busy === 'ship' ? '…' : 'ثبت ارسال و پیامک'}</button>
          </form>
        </Box>
      )}

      {order.status === 'shipped' && (
        <Box title="ارسال">
          <Row label="کد رهگیری"><span className="ltr">{order.tracking}</span></Row>
          <button type="button" className="btn btn-ghost justify-self-start" disabled={!!busy} onClick={() => act('deliver')}>تحویل شد</button>
        </Box>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Box title="گیرنده">
          <p className="font-semibold">{order.name}</p>
          <p className="text-ink-soft leading-relaxed">{address}</p>
          <Row label="کد پستی"><span className="ltr">{fa(order.postal_code)}</span></Row>
          <div className="flex flex-wrap gap-2">
            <a href={`tel:${order.phone}`} className="btn btn-ghost btn-sm"><Phone size={18} aria-hidden /> <span className="ltr">{fa(order.phone)}</span></a>
            <CopyButton text={`${order.name}\n${address}\nکد پستی ${order.postal_code}\n${order.phone}`} label="کپی نشانی" />
          </div>
        </Box>
        <Box title="مبلغ">
          <Row label={order.color ? `${order.product}، ${order.color}` : order.product}>{toman(order.price_rial)}</Row>
          <Row label={`ارسال (${order.shipping})`}>{shippingFee(order.shipping_rial, order.shipping_on_delivery)}</Row>
          <Row label="شناسه واریز">{order.pay_in_rial ? `${fa(order.offset_rial)} ریال` : toman(order.offset_rial)}</Row>
          <Row label={order.pay_in_rial ? 'جمع (ریال)' : 'جمع (تومان)'}><span className="text-lg">{order.pay_in_rial ? rial(order.amount_rial) : toman(order.amount_rial)}</span></Row>
          <Row label="روش پرداخت">{order.payment_label}</Row>
          {order.payment_codes.length > 0 && (
            <Row label={order.payment_method === 'sheba' ? 'شماره پیگیری شبا' : 'کد پرداخت (کارت‌به‌کارت)'}>
              <span className="ltr">{order.payment_codes.join('، ')}</span>
            </Row>
          )}
          {order.sheba && <Row label="شبا"><span className="ltr">{order.sheba.number}</span></Row>}
          <Row label="کارت">{order.card.bank} <span className="ltr">…{fa(order.card.number.slice(-4))}</span></Row>
          {split && order.transfers.map((t) => (
            <Row key={t.position} label={`واریز ${fa(t.position)}${t.provider_ref ? ` (${t.provider_ref})` : ''}`}>
              {amount(t.amount_rial)} · {t.status_label}
            </Row>
          ))}
          {order.paid_at && <Row label="پرداخت">{when(order.paid_at)}، {order.paid_via === 'auto' ? 'خودکار' : `دستی${order.confirmed_by ? ` (${order.confirmed_by})` : ''}`}</Row>}
        </Box>
      </div>

      {order.returns.length > 0 && (
        <Box title="بازگشت">
          {order.returns.map((r) => (
            <p key={r.id} className="text-ink-soft">{r.status_label}: {r.reason} <Link to="/returns" className="underline">بازگشت‌ها</Link></p>
          ))}
        </Box>
      )}

      <Box title="یادداشت داخلی">
        {note === null ? (
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="text-ink-soft whitespace-pre-line">{order.staff_note || 'یادداشتی نیست.'}</p>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNote(order.staff_note)}>ویرایش</button>
          </div>
        ) : (
          <div className="grid gap-3">
            <label htmlFor="staff-note" className="sr-only">یادداشت</label>
            <textarea id="staff-note" className="input min-h-24" value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="flex gap-2">
              <button type="button" className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => act('note', { note })}>ذخیره</button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNote(null)}>انصراف</button>
            </div>
          </div>
        )}
      </Box>

      <Box title="تاریخچه">
        <ol className="grid gap-3">
          {order.history.map((h, i) => (
            <li key={i} className="grid gap-0.5">
              <span className="font-semibold">{ACTIONS[h.action] ?? h.action}{h.user ? ` · ${h.user}` : ''}</span>
              <span className="text-sm text-muted">{when(h.at)}{h.detail ? ` · ${h.detail}` : ''}</span>
            </li>
          ))}
        </ol>
        {order.sms.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-ink-soft">پیامک‌ها ({fa(order.sms.length)})</summary>
            <ul className="mt-3 grid gap-2 text-sm">
              {order.sms.map((m, i) => (
                <li key={i} className="rounded-[var(--radius-field)] bg-surface p-3">
                  <p>{m.text}</p>
                  <p className="text-muted">{when(m.at)} · {m.status === 'failed' ? `ناموفق: ${m.error}` : m.status === 'console' ? 'آزمایشی' : 'ارسال شد'}</p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </Box>

      {can.approve && cancellable && (
        <button type="button" className="justify-self-start text-danger underline underline-offset-4" disabled={!!busy}
          onClick={() => act('cancel', {}, 'سفارش لغو شود؟ اگر پولی واریز شده، باید جداگانه برگردانده شود.')}>
          لغو سفارش
        </button>
      )}
    </div>
  );
}
