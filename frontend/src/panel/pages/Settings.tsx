import { useEffect, useState, type FormEvent } from 'react';
import { Trash } from '@phosphor-icons/react';
import { isApiError, post } from '../../lib/api';
import { fa, groupCard, latin, toman } from '../../lib/format';
import { message } from '../../lib/messages';
import { Field, Notice } from '../../lib/ui';
import { useLoad } from '../session';
import { Skeleton, Title } from '../parts';

interface Store {
  store_name: string; tagline: string; phone: string; email: string; address: string; postal_code: string; hours: string;
  instagram: string; owner_mobile: string; shipping_post_rial: number; shipping_tipax_rial: number; tipax_on_delivery: boolean; post_days: string;
  tipax_days: string; payment_minutes: number; reminder_minutes: number; return_days: number; enamad_html: string;
  transfer_limit_rial: number; // the bank's cap for one card-to-card; orders above it are paid in several
  sheba: string; sheba_holder: string; sheba_bank: string; sheba_minutes: number; // the second way to pay
}
interface Product { slug: string; name: string; subtitle: string; description: string; price_rial: number; is_available: boolean; specs: [string, string][] }
/** A model in the list: the main bag first; another shows on the site once it has a price. */
interface Model { slug: string; name: string; main: boolean; on_sale: boolean }
type SettingsData = { store: Store; product: Product; products: Model[] };

/** The address of a page of the API for one model (the main bag's without ?product=). */
const forModel = (url: string, slug: string) => (slug ? `${url}?product=${encodeURIComponent(slug)}` : url);
interface Card { id: number; bank: string; number: string; holder: string; active: boolean; auto: boolean }
interface Color { id: number; name: string; swatch: string; shown: boolean; available: boolean; orders: number }

/** A toman input stored as rials. */
function TomanInput({ id, rial, onChange, describedBy }: { id: string; rial: number; onChange: (rial: number) => void; describedBy?: string }) {
  return (
    <input id={id} aria-describedby={describedBy} className="input ltr text-right" inputMode="numeric" value={fa(String(Math.floor(rial / 10)))}
      onChange={(e) => onChange(Number(latin(e.target.value).replace(/\D/g, '') || 0) * 10)} />
  );
}

function StoreForm({ slug, main }: { slug: string; main: boolean }) {
  const { data, error } = useLoad<SettingsData>(forModel('/api/panel/settings/', slug));
  const [store, setStore] = useState<Store | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  useEffect(() => {
    if (data) {
      setStore(data.store);
      setProduct(data.product);
    }
  }, [data]);

  if (error) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!store || !product) return <Skeleton rows={6} />;

  const s = <K extends keyof Store>(k: K, v: Store[K]) => { setStore({ ...store, [k]: v }); setStatus('idle'); };
  const p = <K extends keyof Product>(k: K, v: Product[K]) => { setProduct({ ...product, [k]: v }); setStatus('idle'); };
  const err = (k: string) => (errors[k] ? message(errors[k]) : undefined);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (data && product && product.price_rial !== data.product.price_rial &&
        !window.confirm(`قیمت از ${toman(data.product.price_rial)} به ${toman(product.price_rial)} تومان تغییر کند؟ سفارش‌های ثبت‌شده با قیمت قبلی می‌مانند.`)) return;
    setStatus('saving');
    setErrors({});
    try {
      const next = await post<SettingsData>('/api/panel/settings/', { store, product });
      setStore(next.store);
      setProduct(next.product);
      setStatus('saved');
    } catch (e) {
      if (isApiError(e)) setErrors(e.fields ?? {});
      setStatus('error');
    }
  }

  return (
    <form onSubmit={save} className="grid gap-8">
      <section className="grid gap-5">
        <h2 className="text-lg font-bold">{data && data.products.length > 1 ? `کالا: ${product.name}` : 'کالا'}</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="قیمت (تومان)" error={err('price_rial')}
            help={main ? 'برای سفارش‌های تازه. پیشنهاد: قیمت + ارسال زیر ۱۰ میلیون تومان بماند.' : 'تا قیمت صفر است، این مدل در سایت نمایش داده نمی‌شود.'}>
            {(id, d) => <TomanInput id={id} describedBy={d} rial={product.price_rial} onChange={(v) => p('price_rial', v)} />}
          </Field>
          <label className="flex items-center gap-3 self-end min-h-12">
            <input type="checkbox" className="size-5 accent-[var(--color-ink)]" checked={product.is_available} onChange={(e) => p('is_available', e.target.checked)} />
            <span className="font-semibold">موجود است (فروش باز)</span>
          </label>
          <Field label="نام کالا">{(id) => <input id={id} className="input" value={product.name} onChange={(e) => p('name', e.target.value)} />}</Field>
          <Field label="توضیح کوتاه">{(id) => <input id={id} className="input" value={product.subtitle} onChange={(e) => p('subtitle', e.target.value)} />}</Field>
        </div>
        <fieldset className="grid gap-2">
          <legend className="label mb-2">مشخصات</legend>
          {product.specs.map(([label, value], i) => (
            <div key={i} className="grid grid-cols-[1fr_2fr_auto] gap-2">
              <input aria-label="عنوان" className="input" value={label} onChange={(e) => p('specs', product.specs.map((row, j) => (j === i ? [e.target.value, row[1]] : row)) as [string, string][])} />
              <input aria-label="مقدار" className="input" value={value} onChange={(e) => p('specs', product.specs.map((row, j) => (j === i ? [row[0], e.target.value] : row)) as [string, string][])} />
              <button type="button" className="btn btn-ghost btn-sm !px-3" aria-label="حذف" onClick={() => p('specs', product.specs.filter((_, j) => j !== i))}><Trash size={18} /></button>
            </div>
          ))}
          <button type="button" className="btn btn-ghost btn-sm justify-self-start" onClick={() => p('specs', [...product.specs, ['', '']])}>افزودن ردیف</button>
        </fieldset>
      </section>

      <section className="grid gap-5">
        <h2 className="text-lg font-bold">ارسال و پرداخت</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="هزینه پست پیشتاز (تومان)" error={err('shipping_post_rial')}>{(id) => <TomanInput id={id} rial={store.shipping_post_rial} onChange={(v) => s('shipping_post_rial', v)} />}</Field>
          <Field label="زمان رسیدن با پست">{(id) => <input id={id} className="input" value={store.post_days} onChange={(e) => s('post_days', e.target.value)} />}</Field>
          <div className="grid gap-2">
            {!store.tipax_on_delivery && <Field label="هزینه تیپاکس (تومان)" error={err('shipping_tipax_rial')}>{(id) => <TomanInput id={id} rial={store.shipping_tipax_rial} onChange={(v) => s('shipping_tipax_rial', v)} />}</Field>}
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={store.tipax_on_delivery} onChange={(e) => s('tipax_on_delivery', e.target.checked)} />
              هزینه تیپاکس با خریدار، هنگام تحویل (پس‌کرایه)
            </label>
          </div>
          <Field label="زمان رسیدن با تیپاکس">{(id) => <input id={id} className="input" value={store.tipax_days} onChange={(e) => s('tipax_days', e.target.value)} />}</Field>
          <Field label="مهلت پرداخت (دقیقه)" error={err('payment_minutes')}>{(id) => <input id={id} className="input ltr text-right" inputMode="numeric" value={fa(store.payment_minutes)} onChange={(e) => s('payment_minutes', Number(latin(e.target.value).replace(/\D/g, '') || 0))} />}</Field>
          <Field label="یادآوری پرداخت پس از (دقیقه)" error={err('reminder_minutes')}>{(id) => <input id={id} className="input ltr text-right" inputMode="numeric" value={fa(store.reminder_minutes)} onChange={(e) => s('reminder_minutes', Number(latin(e.target.value).replace(/\D/g, '') || 0))} />}</Field>
          <Field label="سقف هر کارت‌به‌کارت (تومان)" error={err('transfer_limit_rial')}
            help="سفارش بالاتر از این مبلغ در چند واریز پرداخت می‌شود: باقی مبلغ، بعد واریزهای ۵ میلیون تومانی. حداقل ۱۰ میلیون؛ ۰ یعنی همیشه یک واریز.">
            {(id, d) => <TomanInput id={id} describedBy={d} rial={store.transfer_limit_rial} onChange={(v) => s('transfer_limit_rial', v)} />}
          </Field>
          <Field label="شبای فروشگاه" error={err('sheba')} help="تا خالی است، پرداخت با شبا به خریدار پیشنهاد نمی‌شود. واریز شبا را همکاران بررسی و تأیید می‌کنند.">
            {(id, d) => <input id={id} aria-describedby={d} className="input ltr" placeholder="IR" value={store.sheba} onChange={(e) => s('sheba', e.target.value)} />}
          </Field>
          <Field label="نام صاحب حساب شبا">{(id) => <input id={id} className="input" value={store.sheba_holder} onChange={(e) => s('sheba_holder', e.target.value)} />}</Field>
          <Field label="بانک حساب شبا">{(id) => <input id={id} className="input" value={store.sheba_bank} onChange={(e) => s('sheba_bank', e.target.value)} />}</Field>
          <Field label="مهلت پرداخت با شبا (دقیقه)" error={err('sheba_minutes')}>{(id) => <input id={id} className="input ltr text-right" inputMode="numeric" value={fa(store.sheba_minutes)} onChange={(e) => s('sheba_minutes', Number(latin(e.target.value).replace(/\D/g, '') || 0))} />}</Field>
          <Field label="مهلت بازگشت (روز کاری)" error={err('return_days')}>{(id) => <input id={id} className="input ltr text-right" inputMode="numeric" value={fa(store.return_days)} onChange={(e) => s('return_days', Number(latin(e.target.value).replace(/\D/g, '') || 0))} />}</Field>
          <Field label="موبایل مدیر (پیامک سفارش‌ها)" error={err('owner_mobile')}>{(id) => <input id={id} className="input ltr text-right" inputMode="tel" value={store.owner_mobile} onChange={(e) => s('owner_mobile', e.target.value)} />}</Field>
        </div>
      </section>

      <section className="grid gap-5">
        <h2 className="text-lg font-bold">فروشگاه</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="نام فروشگاه">{(id) => <input id={id} className="input" value={store.store_name} onChange={(e) => s('store_name', e.target.value)} />}</Field>
          <Field label="شعار">{(id) => <input id={id} className="input" value={store.tagline} onChange={(e) => s('tagline', e.target.value)} />}</Field>
          <Field label="تلفن">{(id) => <input id={id} className="input ltr text-right" value={store.phone} onChange={(e) => s('phone', e.target.value)} />}</Field>
          <Field label="ایمیل">{(id) => <input id={id} className="input ltr" value={store.email} onChange={(e) => s('email', e.target.value)} />}</Field>
          <Field label="نشانی" className="sm:col-span-2">{(id) => <input id={id} className="input" value={store.address} onChange={(e) => s('address', e.target.value)} />}</Field>
          <Field label="کد پستی">{(id) => <input id={id} className="input ltr text-right" value={store.postal_code} onChange={(e) => s('postal_code', e.target.value)} />}</Field>
          <Field label="ساعات پاسخ‌گویی">{(id) => <input id={id} className="input" value={store.hours} onChange={(e) => s('hours', e.target.value)} />}</Field>
          <Field label="اینستاگرام (بدون @)">{(id) => <input id={id} className="input ltr" value={store.instagram} onChange={(e) => s('instagram', e.target.value)} />}</Field>
          <Field label="کد نماد اعتماد" help="کد را همان‌طور که اینماد داده بچسبانید." className="sm:col-span-2">
            {(id, d) => <textarea id={id} aria-describedby={d} className="input ltr min-h-24 font-mono text-sm" value={store.enamad_html} onChange={(e) => s('enamad_html', e.target.value)} />}
          </Field>
        </div>
      </section>

      <div className="sticky bottom-20 md:bottom-4 flex items-center gap-4 rounded-full bg-raised/95 backdrop-blur border border-line p-2 ps-4 w-fit shadow-[0_10px_30px_rgba(23,24,27,0.08)]">
        <span className="text-sm text-muted" aria-live="polite">{status === 'saved' ? 'ذخیره شد' : status === 'error' ? message('fields') : ''}</span>
        <button type="submit" className="btn btn-primary" disabled={status === 'saving'}>{status === 'saving' ? 'در حال ذخیره…' : 'ذخیره'}</button>
      </div>
    </form>
  );
}

function Cards() {
  const { data, setData, error } = useLoad<{ cards: Card[] }>('/api/panel/cards/');
  const [draft, setDraft] = useState({ bank: '', number: '', holder: '' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState('');

  async function save(body: Record<string, unknown>) {
    setProblem('');
    setErrors({});
    try {
      setData(await post<{ cards: Card[] }>('/api/panel/cards/', body));
      return true;
    } catch (e) {
      if (isApiError(e)) {
        setErrors(e.fields ?? {});
        setProblem(message(e.error));
      }
      return false;
    }
  }

  return (
    <section className="grid gap-4">
      <h2 className="text-lg font-bold">کارت‌های مقصد</h2>
      <p className="text-ink-soft leading-relaxed -mt-2">
        خریدار در صفحه پرداخت همه‌ی کارت‌های فعال را می‌بیند و به هر کدام خواست واریز می‌کند؛ کارت خود سفارش (پیش‌فرض کارت‌به‌کارت) اول می‌آید.
        کارت‌به‌کارت فقط واریز به کارت پیش‌فرض خودش را خودکار تأیید می‌کند؛ واریز به کارت‌های دیگر را «نیاز به بررسی» می‌کند (آزمایش ۲ آبان با کارت بلو) و با تأیید شما در داشبوردش، سفارش خودکار پرداخت‌شده می‌شود.
        «تأیید خودکار» را فقط برای کارتی بزنید که دیده‌اید خودکار تأیید می‌شود.
      </p>
      {error && <Notice tone="error">{message(error.error)}</Notice>}
      <ul className="grid gap-2">
        {data?.cards.map((card) => (
          <li key={card.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-field)] border border-line bg-raised p-4">
            <span className="grid gap-0.5">
              <span className="font-semibold">{card.bank} · {card.holder}</span>
              <span className="ltr text-ink-soft">{fa(groupCard(card.number))}</span>
            </span>
            <span className="flex items-center gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={card.active} onChange={(e) => save({ ...card, active: e.target.checked })} /> فعال
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={card.auto} onChange={(e) => save({ ...card, auto: e.target.checked })} /> تأیید خودکار
              </label>
              <button type="button" className="btn btn-ghost btn-sm !px-3" aria-label="حذف کارت"
                onClick={() => window.confirm('کارت حذف شود؟ (اگر سفارشی به آن خورده، فقط غیرفعال می‌شود.)') && save({ id: card.id, delete: true })}>
                <Trash size={18} />
              </button>
            </span>
          </li>
        ))}
      </ul>
      <form className="grid gap-3 sm:grid-cols-[1fr_1.4fr_1fr_auto] sm:items-end rounded-[var(--radius-field)] border border-dashed border-line-strong p-4"
        onSubmit={async (e) => { e.preventDefault(); if (await save({ ...draft, active: true })) setDraft({ bank: '', number: '', holder: '' }); }}>
        <Field label="بانک" error={errors.bank ? message(errors.bank) : undefined}>{(id) => <input id={id} className="input" value={draft.bank} onChange={(e) => setDraft({ ...draft, bank: e.target.value })} />}</Field>
        <Field label="شماره کارت" error={errors.number ? message(errors.number) : undefined}>{(id) => <input id={id} className="input ltr" inputMode="numeric" value={draft.number} onChange={(e) => setDraft({ ...draft, number: e.target.value })} />}</Field>
        <Field label="نام صاحب کارت" error={errors.holder ? message(errors.holder) : undefined}>{(id) => <input id={id} className="input" value={draft.holder} onChange={(e) => setDraft({ ...draft, holder: e.target.value })} />}</Field>
        <button type="submit" className="btn btn-primary">افزودن</button>
      </form>
      {problem && !Object.keys(errors).length && <Notice tone="error">{problem}</Notice>}
    </section>
  );
}

/** A model's colours. The site asks buyers for a colour only while more than one is shown. */
function Colors({ slug }: { slug: string }) {
  const url = forModel('/api/panel/colors/', slug);
  const { data, setData, error } = useLoad<{ colors: Color[] }>(url);
  const [draft, setDraft] = useState({ name: '', swatch: '#17181b' });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [problem, setProblem] = useState('');

  async function save(body: Record<string, unknown>) {
    setProblem('');
    setErrors({});
    try {
      setData(await post<{ colors: Color[] }>(url, body));
      return true;
    } catch (e) {
      if (isApiError(e)) {
        setErrors(e.fields ?? {});
        setProblem(message(e.error));
      }
      return false;
    }
  }

  const shown = data?.colors.filter((c) => c.shown).length ?? 0;
  return (
    <section className="grid gap-4">
      <h2 className="text-lg font-bold">رنگ‌ها</h2>
      <p className="text-ink-soft leading-relaxed -mt-2">
        {shown > 1
          ? 'چند رنگ نمایش داده می‌شود: خریدار در صفحه‌ی کالا و هنگام خرید رنگ را انتخاب می‌کند.'
          : 'فقط یک رنگ نمایش داده می‌شود، پس از خریدار رنگ پرسیده نمی‌شود. رنگ تازه را تا عکس‌هایش نرسیده پنهان نگه دارید.'}
      </p>
      {error && <Notice tone="error">{message(error.error)}</Notice>}
      <ul className="grid gap-2">
        {data?.colors.map((color) => (
          <li key={color.id} className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-field)] border border-line bg-raised p-4">
            <span className="flex items-center gap-3">
              <span className="size-7 rounded-full ring-1 ring-ink/20" style={{ background: color.swatch }} aria-hidden="true" />
              <span className="grid gap-0.5">
                <span className="font-semibold">{color.name}</span>
                <span className="text-sm text-muted">{color.orders ? `${fa(color.orders)} سفارش` : 'بدون سفارش'}</span>
              </span>
            </span>
            <span className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={color.shown} onChange={(e) => save({ ...color, shown: e.target.checked })} /> نمایش در سایت
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={color.available} onChange={(e) => save({ ...color, available: e.target.checked })} /> موجود
              </label>
              <button type="button" className="btn btn-ghost btn-sm !px-3" aria-label={`حذف رنگ ${color.name}`}
                onClick={() => window.confirm('رنگ حذف شود؟ (اگر سفارشی با این رنگ هست، فقط از سایت پنهان می‌شود.)') && save({ id: color.id, delete: true })}>
                <Trash size={18} />
              </button>
            </span>
          </li>
        ))}
      </ul>
      <form className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end rounded-[var(--radius-field)] border border-dashed border-line-strong p-4"
        onSubmit={async (e) => { e.preventDefault(); if (await save({ ...draft, shown: false, available: true })) setDraft({ name: '', swatch: '#17181b' }); }}>
        <Field label="نام رنگ" error={errors.name ? message(errors.name) : undefined} help="رنگ تازه پنهان افزوده می‌شود؛ وقتی عکس‌هایش آماده شد «نمایش در سایت» را بزنید.">
          {(id, d) => <input id={id} aria-describedby={d} className="input" placeholder="مثلاً سرمه‌ای" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />}
        </Field>
        <Field label="رنگ" error={errors.swatch ? message(errors.swatch) : undefined}>
          {(id, d) => <input id={id} aria-describedby={d} type="color" className="input !p-1 h-12 w-20" value={draft.swatch} onChange={(e) => setDraft({ ...draft, swatch: e.target.value })} />}
        </Field>
        <button type="submit" className="btn btn-primary">افزودن</button>
      </form>
      {problem && !Object.keys(errors).length && <Notice tone="error">{problem}</Notice>}
    </section>
  );
}

/** Which model the colours and the product fields below are for, once there's more than one. */
function ModelPicker({ models, slug, onPick }: { models: Model[]; slug: string; onPick: (slug: string) => void }) {
  return (
    <div role="radiogroup" aria-label="کالا" className="flex flex-wrap gap-2">
      {models.map((model) => {
        const on = model.slug === slug || (!slug && model.main);
        return (
          <button key={model.slug} type="button" role="radio" aria-checked={on} onClick={() => onPick(model.main ? '' : model.slug)}
            className={`btn btn-sm text-start ${on ? 'btn-primary' : 'btn-ghost border border-line'}`}>
            {model.name}{!model.on_sale && <span className={`ms-2 text-xs ${on ? 'text-raised/70' : 'text-muted'}`}>(بدون قیمت، در سایت نیست)</span>}
          </button>
        );
      })}
    </div>
  );
}

export default function Settings() {
  const { data } = useLoad<SettingsData>('/api/panel/settings/');
  const [slug, setSlug] = useState('');
  const models = data?.products ?? [];
  const main = !slug || !!models.find((model) => model.slug === slug)?.main;
  return (
    <>
      <Title>فروشگاه</Title>
      <div className="grid gap-12">
        {models.length > 1 && <ModelPicker models={models} slug={slug} onPick={setSlug} />}
        <Colors key={`colors-${slug}`} slug={slug} />
        <Cards />
        <StoreForm key={`form-${slug}`} slug={slug} main={main} />
      </div>
    </>
  );
}
