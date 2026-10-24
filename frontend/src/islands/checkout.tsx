import { StrictMode, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import clsx from 'clsx';
import { post, islandData, isApiError } from '../lib/api';
import { cleanPhone, fa, latin, shippingFee, toman } from '../lib/format';
import { message } from '../lib/messages';
import { Field, Notice } from '../lib/ui';

interface Shipping {
  id: 'post' | 'tipax';
  name: string;
  price_rial: number;
  days: string;
  on_delivery: boolean; // paid to the courier when it arrives (پس‌کرایه)
}

interface Color {
  id: number;
  name: string;
  swatch: string;
  available: boolean;
}

interface Model {
  slug: string;
  name: string;
  short: string; // its version, «تک‌زیپ» or «دو زیپ»
  price_rial: number;
  available: boolean;
  colors: Color[]; // the colours on show; the buyer picks only when there's more than one
  transfers: Record<string, number[]>; // per way to send: more than one when the total is over the bank's cap
}

interface Data {
  store: string;
  models: Model[]; // every model on sale, the main bag first; the buyer picks one when there's more than one
  start: string; // the one asked for (?product=)
  shipping: Shipping[];
  provinces: string[];
  payment_minutes: number;
  return_days: number;
  dev_sms: boolean;
}

interface Form {
  name: string;
  phone: string;
  province: string;
  city: string;
  address: string;
  postal_code: string;
  shipping: 'post' | 'tipax';
  is_gift: boolean;
  model: string;
  color: number | null;
}

const EMPTY: Form = { name: '', phone: '', province: '', city: '', address: '', postal_code: '', shipping: 'post', is_gift: false, model: '', color: null };
const DRAFT_KEY = 'checkout-draft';

// The form survives leaving the page (switching apps, the in-app browser reloading). Best effort:
// storage can be off or full, and the form works without it.
function loadDraft(): Form {
  try {
    const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
    return saved ? { ...EMPTY, ...saved } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function saveDraft(form: Form) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
  } catch {
    /* ignore */
  }
}

// The colour picked on the product page (?color=), else the draft's, if it's still on offer.
function startingColor(form: Form, colors: Color[]): number | null {
  const wanted = Number(new URLSearchParams(window.location.search).get('color')) || form.color;
  return colors.some((c) => c.id === wanted && c.available) ? wanted : null;
}

function validate(form: Form, colors: Color[]): Record<string, string> {
  const errors: Record<string, string> = {};
  if (colors.length > 1 && !colors.some((c) => c.id === form.color && c.available)) errors.color = 'color';
  if (form.name.trim().length < 3) errors.name = 'required';
  if (!cleanPhone(form.phone)) errors.phone = 'phone';
  if (!form.province) errors.province = 'required';
  if (form.city.trim().length < 2) errors.city = 'required';
  if (form.address.trim().length < 10) errors.address = 'address';
  if (!/^\d{10}$/.test(latin(form.postal_code).replace(/\D/g, ''))) errors.postal_code = 'postal_code';
  return errors;
}

function Checkout({ data }: { data: Data }) {
  const [form, setForm] = useState<Form>(() => {
    const draft = loadDraft();
    // The model asked for (?product=, else the main bag), not the draft's: the link the buyer came by says.
    const start = data.models.find((m) => m.slug === data.start) ?? data.models[0];
    return { ...draft, model: start.slug, color: startingColor(draft, start.colors) };
  });
  const model = data.models.find((m) => m.slug === form.model) ?? data.models[0];
  const asksModel = data.models.length > 1;
  const asksColor = model.colors.length > 1;
  const color = model.colors.find((c) => c.id === form.color);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [step, setStep] = useState<'form' | 'code'>('form');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const [devCode, setDevCode] = useState('');
  const codeInput = useRef<HTMLInputElement>(null);

  const shipping = data.shipping.find((s) => s.id === form.shipping) ?? data.shipping[0];
  const total = model.price_rial + shipping.price_rial;

  useEffect(() => saveDraft(form), [form]);
  // The summary beside the form shows the picked model, its bag in the picked colour (checkout.html, one
  // photo per model and colour; its first until a colour is picked).
  useEffect(() => {
    const photos = [...document.querySelectorAll<HTMLElement>('img[data-model]')];
    const mine = photos.filter((photo) => photo.dataset.model === model.slug);
    const shown = mine.find((photo) => Number(photo.dataset.colorPhoto) === form.color) ?? mine[0];
    photos.forEach((photo) => (photo.hidden = photo !== shown));
    document.querySelectorAll<HTMLElement>('[data-model-summary]').forEach((el) => (el.hidden = el.dataset.modelSummary !== model.slug));
  }, [model.slug, form.color]);
  useEffect(() => {
    if (resendIn <= 0) return;
    const id = window.setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [resendIn]);
  useEffect(() => {
    if (step === 'code') codeInput.current?.focus();
  }, [step]);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (errors[key]) setErrors((e) => ({ ...e, [key]: '' }));
  };
  // Another model keeps the colour by its name (black stays black), if that model has it in stock.
  const pickModel = (next: Model) => {
    const same = next.colors.find((c) => c.name === color?.name && c.available);
    setForm((f) => ({ ...f, model: next.slug, color: same ? same.id : null }));
    setErrors((e) => ({ ...e, color: '' }));
  };

  async function askCode(event?: FormEvent) {
    event?.preventDefault();
    setProblem('');
    const found = validate(form, model.colors);
    setErrors(found);
    if (Object.values(found).some(Boolean)) {
      setProblem(message('fields'));
      document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      return;
    }
    setBusy(true);
    try {
      const result = await post<{ wait: number; dev_code?: string }>('/api/otp/', { phone: form.phone });
      setResendIn(result.wait);
      setDevCode(result.dev_code ?? '');
      setStep('code');
    } catch (err) {
      if (isApiError(err)) {
        if (err.error === 'otp_wait' && err.wait) {
          setResendIn(err.wait);
          setStep('code');
        } else setProblem(message(err.error));
      }
    } finally {
      setBusy(false);
    }
  }

  async function placeOrder(event: FormEvent) {
    event.preventDefault();
    setProblem('');
    if (latin(code).replace(/\D/g, '').length !== 5) {
      setProblem(message('otp_wrong'));
      return;
    }
    setBusy(true);
    try {
      const result = await post<{ url: string }>('/api/orders/', {
        ...form, product: model.slug, color: asksColor ? form.color : null, code: latin(code).replace(/\D/g, ''),
      });
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch {
        /* ignore */
      }
      window.location.assign(result.url);
    } catch (err) {
      setBusy(false);
      if (!isApiError(err)) return;
      if (err.error === 'fields' && err.fields) {
        setErrors(err.fields);
        setStep('form');
      }
      if (err.error === 'color' || err.error === 'color_unavailable') {
        setErrors({ color: err.error });
        setStep('form');
      }
      setProblem(message(err.error));
    }
  }

  const errorText = (key: keyof Form) => (errors[key] ? message(errors[key]) : undefined);

  if (!data.models.some((m) => m.available)) {
    return <Notice tone="warn">این کالا فعلاً موجود نیست. به‌زودی دوباره می‌آید.</Notice>;
  }

  if (step === 'code') {
    return (
      <form onSubmit={placeOrder} className="grid gap-6 max-w-md" noValidate>
        <p className="text-lg leading-relaxed">
          کد ۵ رقمی به <span className="ltr font-bold">{fa(cleanPhone(form.phone) ?? form.phone)}</span> پیامک شد.
        </p>
        <Field label="کد تأیید" error={problem || undefined} help={data.dev_sms ? `محیط آزمایشی، پیامکی فرستاده نمی‌شود. کد: ${devCode || 'در ترمینال سرور'}` : undefined}>
          {(id, describedBy) => (
            <input
              ref={codeInput}
              id={id}
              aria-describedby={describedBy}
              aria-invalid={!!problem}
              className="input ltr text-center text-2xl font-bold tracking-[0.5em] max-w-56"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={5}
              value={code}
              onChange={(e) => setCode(latin(e.target.value).replace(/\D/g, '').slice(0, 5))}
            />
          )}
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-primary min-h-14 px-8" disabled={busy}>
            {busy ? 'در حال ثبت…' : 'ثبت سفارش و پرداخت'}
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy || resendIn > 0} onClick={() => askCode()}>
            {resendIn > 0 ? `ارسال دوباره (${fa(resendIn)})` : 'ارسال دوباره کد'}
          </button>
        </div>
        <button type="button" className="justify-self-start text-ink-soft underline underline-offset-4" onClick={() => { setStep('form'); setProblem(''); setCode(''); }}>
          ویرایش نشانی یا شماره
        </button>
      </form>
    );
  }

  return (
    <form onSubmit={askCode} className="grid gap-8" noValidate>
      {asksModel && (
        <fieldset className="grid gap-3">
          <legend className="label mb-2">مدل</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.models.map((option) => (
              <label
                key={option.slug}
                className={clsx(
                  'flex items-start gap-3 rounded-[var(--radius-field)] border p-4 transition-colors',
                  !option.available ? 'cursor-not-allowed opacity-55 border-line' : 'cursor-pointer',
                  model.slug === option.slug ? 'border-ink bg-raised' : option.available && 'border-line-strong hover:border-ink-soft',
                )}
              >
                <input type="radio" name="model" className="mt-1.5 accent-[var(--color-ink)] size-4" disabled={!option.available}
                  checked={model.slug === option.slug} onChange={() => pickModel(option)} />
                <span className="grid gap-0.5">
                  <span className="font-semibold">{option.short}</span>
                  <span className="text-sm text-muted">{option.name}</span>
                  <span className="font-bold mt-1">{option.available ? `${toman(option.price_rial)} تومان` : 'ناموجود'}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {model.available ? null : <Notice tone="warn">این مدل فعلاً موجود نیست؛ مدل دیگر را انتخاب کنید.</Notice>}

      {asksColor && (
        <fieldset className="grid gap-3" aria-describedby={errors.color ? 'color-error' : undefined}>
          <legend className="label mb-2">رنگ</legend>
          <div className="flex flex-wrap gap-3">
            {model.colors.map((option) => (
              <label
                key={option.id}
                className={clsx(
                  'flex items-center gap-3 rounded-[var(--radius-field)] border py-2.5 ps-3 pe-4 transition-colors',
                  !option.available ? 'cursor-not-allowed opacity-55 border-line' : 'cursor-pointer',
                  form.color === option.id ? 'border-ink bg-raised' : option.available && 'border-line-strong hover:border-ink-soft',
                )}
              >
                <input type="radio" name="color" className="sr-only peer" disabled={!option.available}
                  checked={form.color === option.id} onChange={() => set('color', option.id)} />
                <span className="size-7 rounded-full ring-1 ring-ink/25 ring-offset-2 ring-offset-raised peer-checked:ring-2 peer-checked:ring-ink peer-focus-visible:ring-2 peer-focus-visible:ring-signal"
                  style={{ background: option.swatch }} aria-hidden="true" />
                <span className="font-semibold">{option.name}</span>
                {!option.available && <span className="text-sm text-muted">ناموجود</span>}
              </label>
            ))}
          </div>
          {errors.color && <p id="color-error" className="error-text">{message(errors.color)}</p>}
        </fieldset>
      )}

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="sr-only">گیرنده</legend>
        <Field label="نام و نام خانوادگی گیرنده" error={errorText('name')}>
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.name} className="input" autoComplete="name" value={form.name} onChange={(e) => set('name', e.target.value)} />}
        </Field>
        <Field label="شماره موبایل" error={errorText('phone')} help="کد تأیید و وضعیت سفارش به این شماره پیامک می‌شود.">
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.phone} className="input ltr text-right" inputMode="tel" autoComplete="tel" placeholder="۰۹۱۲۱۲۳۴۵۶۷" value={form.phone} onChange={(e) => set('phone', e.target.value)} />}
        </Field>
        <Field label="استان" error={errorText('province')}>
          {(id, d) => (
            <select id={id} aria-describedby={d} aria-invalid={!!errors.province} className="input" value={form.province} onChange={(e) => set('province', e.target.value)}>
              <option value="">انتخاب کنید</option>
              {data.provinces.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          )}
        </Field>
        <Field label="شهر" error={errorText('city')}>
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.city} className="input" autoComplete="address-level2" value={form.city} onChange={(e) => set('city', e.target.value)} />}
        </Field>
        <Field label="نشانی کامل" error={errorText('address')} className="sm:col-span-2">
          {(id, d) => <textarea id={id} aria-describedby={d} aria-invalid={!!errors.address} className="input min-h-24 leading-relaxed" autoComplete="street-address" placeholder="خیابان، کوچه، پلاک، واحد" value={form.address} onChange={(e) => set('address', e.target.value)} />}
        </Field>
        <Field label="کد پستی" error={errorText('postal_code')} help="۱۰ رقم، بدون خط تیره.">
          {(id, d) => <input id={id} aria-describedby={d} aria-invalid={!!errors.postal_code} className="input ltr text-right" inputMode="numeric" autoComplete="postal-code" maxLength={11} value={form.postal_code} onChange={(e) => set('postal_code', e.target.value)} />}
        </Field>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className="label mb-2">روش ارسال</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {data.shipping.map((option) => (
            <label
              key={option.id}
              className={clsx(
                'flex cursor-pointer items-start gap-3 rounded-[var(--radius-field)] border p-4 transition-colors',
                form.shipping === option.id ? 'border-ink bg-raised' : 'border-line-strong hover:border-ink-soft',
              )}
            >
              <input type="radio" name="shipping" className="mt-1.5 accent-[var(--color-ink)] size-4" checked={form.shipping === option.id} onChange={() => set('shipping', option.id)} />
              <span className="grid gap-0.5">
                <span className="font-semibold">{option.name}</span>
                <span className="text-sm text-muted">{option.days}</span>
                <span className="font-bold mt-1">{shippingFee(option.price_rial, option.on_delivery)}</span>
                {option.on_delivery && <span className="text-sm text-muted">هزینه را هنگام تحویل به {option.name} می‌پردازید.</span>}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex cursor-pointer items-start gap-3">
        <input type="checkbox" className="mt-1.5 size-4 accent-[var(--color-ink)]" checked={form.is_gift} onChange={(e) => set('is_gift', e.target.checked)} />
        <span className="grid gap-0.5">
          <span className="font-semibold">هدیه است</span>
          <span className="text-sm text-muted">فاکتوری که قیمت دارد داخل بسته گذاشته نمی‌شود؛ فاکتور را با پیامک برای شما می‌فرستیم.</span>
        </span>
      </label>

      <div className="grid gap-3 rounded-[var(--radius-surface)] bg-surface border border-line p-5">
        <div className="flex justify-between gap-4"><span className="text-ink-soft">{model.name}{asksColor && color ? `، ${color.name}` : ''}</span><span>{toman(model.price_rial)} تومان</span></div>
        <div className="flex justify-between gap-4"><span className="text-ink-soft">ارسال با {shipping.name}</span><span>{shippingFee(shipping.price_rial, shipping.on_delivery)}</span></div>
        <div className="flex justify-between gap-4 border-t border-line pt-3 text-lg font-bold"><span>جمع</span><span>{toman(total)} تومان</span></div>
        <p className="text-sm text-muted leading-relaxed">برای اینکه واریز شما بی‌اشتباه شناخته شود، چند تومان (کمتر از هزار تومان) به مبلغ پرداخت اضافه می‌شود.</p>
        {(model.transfers[form.shipping]?.length ?? 1) > 1 && (
          <p className="text-sm leading-relaxed">
            این مبلغ از سقف یک کارت‌به‌کارت بیشتر است؛ آن را در {fa(model.transfers[form.shipping].length)} واریز جدا می‌فرستید:{' '}
            {model.transfers[form.shipping].map((part) => toman(part)).join(' و ')} تومان، هر کدام با شناسه‌ی واریز خودش.
          </p>
        )}
      </div>

      {problem && <Notice tone="error">{problem}</Notice>}
      <button type="submit" className="btn btn-primary min-h-14 px-8 text-lg justify-self-start" disabled={busy}>
        {busy ? 'در حال ارسال کد…' : 'دریافت کد تأیید'}
      </button>
    </form>
  );
}

function Root() {
  const data = useMemo(() => islandData<Data>(), []);
  return <Checkout data={data} />;
}

createRoot(document.getElementById('checkout-root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
