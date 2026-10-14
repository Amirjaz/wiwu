import { StrictMode, useEffect, useMemo, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { CaretLeft } from '@phosphor-icons/react';
import { islandData, isApiError, post } from '../lib/api';
import { cleanPhone, fa, latin, toman, when } from '../lib/format';
import { message } from '../lib/messages';
import { Field, Notice } from '../lib/ui';

interface Found {
  code: string;
  status: string;
  status_label: string;
  created: string;
  amount_rial: number;
  url: string;
}

function Lookup({ devSms }: { devSms: boolean }) {
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'phone' | 'code' | 'list'>('phone');
  const [orders, setOrders] = useState<Found[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const [devCode, setDevCode] = useState('');

  useEffect(() => {
    if (resendIn <= 0) return;
    const id = window.setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [resendIn]);

  async function sendCode(event?: FormEvent) {
    event?.preventDefault();
    setProblem('');
    if (!cleanPhone(phone)) {
      setProblem(message('phone'));
      return;
    }
    setBusy(true);
    try {
      const result = await post<{ wait: number; dev_code?: string }>('/api/otp/', { phone });
      setResendIn(result.wait);
      setDevCode(result.dev_code ?? '');
      setStep('code');
    } catch (err) {
      if (isApiError(err) && err.error === 'otp_wait' && err.wait) {
        setResendIn(err.wait);
        setStep('code');
      } else setProblem(isApiError(err) ? message(err.error) : message('unknown'));
    } finally {
      setBusy(false);
    }
  }

  async function check(event: FormEvent) {
    event.preventDefault();
    setProblem('');
    setBusy(true);
    try {
      const result = await post<{ orders: Found[] }>('/api/lookup/', { phone, code: latin(code) });
      setOrders(result.orders);
      setStep('list');
    } catch (err) {
      setProblem(isApiError(err) ? message(err.error) : message('unknown'));
    } finally {
      setBusy(false);
    }
  }

  if (step === 'list') {
    if (!orders.length) {
      return (
        <Notice tone="info">
          با این شماره سفارشی پیدا نشد. <a href="/checkout/" className="underline">ثبت سفارش</a>
        </Notice>
      );
    }
    return (
      <ul className="grid gap-3">
        {orders.map((o) => (
          <li key={o.code}>
            <a href={o.url} className="flex items-center justify-between gap-4 rounded-[var(--radius-field)] border border-line bg-raised p-4 hover:border-ink-soft">
              <span className="grid gap-0.5">
                <span className="font-bold">سفارش <span className="ltr">{o.code}</span></span>
                <span className="text-sm text-muted">{when(o.created, true)} · {toman(o.amount_rial)} تومان</span>
              </span>
              <span className="flex items-center gap-1 text-ink-soft">{o.status_label}<CaretLeft size={16} aria-hidden /></span>
            </a>
          </li>
        ))}
      </ul>
    );
  }

  if (step === 'code') {
    return (
      <form onSubmit={check} className="grid gap-5" noValidate>
        <Field label="کد تأیید" error={problem || undefined} help={devSms ? `محیط آزمایشی، پیامکی فرستاده نمی‌شود. کد: ${devCode || 'در ترمینال سرور'}` : `به ${fa(cleanPhone(phone) ?? '')} پیامک شد.`}>
          {(id, d) => (
            <input id={id} aria-describedby={d} aria-invalid={!!problem} autoFocus className="input ltr text-center text-2xl font-bold tracking-[0.5em] max-w-56"
              inputMode="numeric" autoComplete="one-time-code" maxLength={5} value={code}
              onChange={(e) => setCode(latin(e.target.value).replace(/\D/g, '').slice(0, 5))} />
          )}
        </Field>
        <div className="flex flex-wrap gap-3">
          <button type="submit" className="btn btn-primary" disabled={busy || code.length !== 5}>{busy ? 'در حال بررسی…' : 'دیدن سفارش‌ها'}</button>
          <button type="button" className="btn btn-ghost" disabled={busy || resendIn > 0} onClick={() => sendCode()}>
            {resendIn > 0 ? `ارسال دوباره (${fa(resendIn)})` : 'ارسال دوباره کد'}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form onSubmit={sendCode} className="grid gap-5" noValidate>
      <Field label="شماره موبایل" error={problem || undefined}>
        {(id, d) => (
          <input id={id} aria-describedby={d} aria-invalid={!!problem} className="input ltr text-right" inputMode="tel" autoComplete="tel"
            placeholder="۰۹۱۲۱۲۳۴۵۶۷" value={phone} onChange={(e) => setPhone(e.target.value)} />
        )}
      </Field>
      <button type="submit" className="btn btn-primary justify-self-start" disabled={busy}>{busy ? 'در حال ارسال…' : 'دریافت کد'}</button>
    </form>
  );
}

function Root() {
  const { dev_sms } = useMemo(() => islandData<{ dev_sms: boolean }>(), []);
  return <Lookup devSms={dev_sms} />;
}

createRoot(document.getElementById('lookup-root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
