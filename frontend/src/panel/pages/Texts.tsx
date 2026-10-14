import { useState } from 'react';
import { isApiError, post } from '../../lib/api';
import { message } from '../../lib/messages';
import { Field, Notice } from '../../lib/ui';
import { useLoad } from '../session';
import { Skeleton, Title } from '../parts';

interface PageItem { id: number; slug: string; title: string; body: string }
interface Faq { id?: number; question: string; answer: string; published: boolean }
interface Texts { pages: PageItem[]; faqs: Faq[] }

const MARKUP_HELP = 'یک خط خالی بین پاراگراف‌ها، ## برای تیتر، - برای فهرست، **متن** برای پررنگ.';

function PageEditor({ page, onSaved }: { page: PageItem; onSaved: (t: Texts) => void }) {
  const [title, setTitle] = useState(page.title);
  const [body, setBody] = useState(page.body);
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const dirty = title !== page.title || body !== page.body;
  return (
    <details className="rounded-[var(--radius-field)] border border-line bg-raised">
      <summary className="cursor-pointer p-4 font-semibold">{page.title}</summary>
      <div className="grid gap-4 px-4 pb-4">
        <a href={`/p/${page.slug}/`} target="_blank" rel="noopener" className="text-sm text-ink-soft underline w-fit">دیدن صفحه در سایت</a>
        <Field label="عنوان">{(id) => <input id={id} className="input" value={title} onChange={(e) => { setTitle(e.target.value); setState('idle'); }} />}</Field>
        <Field label="متن" help={MARKUP_HELP}>{(id, d) => <textarea id={id} aria-describedby={d} className="input min-h-72 leading-relaxed" value={body} onChange={(e) => { setBody(e.target.value); setState('idle'); }} />}</Field>
        <div className="flex items-center gap-3">
          <button type="button" className="btn btn-primary btn-sm" disabled={!dirty || state === 'saving'}
            onClick={async () => {
              setState('saving');
              try {
                onSaved(await post<Texts>('/api/panel/texts/', { kind: 'page', id: page.id, title, body }));
                setState('saved');
              } catch {
                setState('error');
              }
            }}>ذخیره</button>
          <span className="text-sm text-muted" aria-live="polite">{state === 'saved' ? 'ذخیره شد' : state === 'error' ? message('unknown') : ''}</span>
        </div>
      </div>
    </details>
  );
}

function FaqEditor({ faq, onSaved, onCancel }: { faq: Faq; onSaved: (t: Texts) => void; onCancel?: () => void }) {
  const [draft, setDraft] = useState(faq);
  const [problem, setProblem] = useState('');
  async function save(extra: Record<string, unknown> = {}) {
    setProblem('');
    try {
      onSaved(await post<Texts>('/api/panel/texts/', { kind: 'faq', ...draft, ...extra }));
    } catch (e) {
      setProblem(isApiError(e) ? message(e.fields?.question ?? e.error) : message('unknown'));
    }
  }
  return (
    <div className="grid gap-3 rounded-[var(--radius-field)] border border-line bg-raised p-4">
      <Field label="پرسش">{(id) => <input id={id} className="input" value={draft.question} onChange={(e) => setDraft({ ...draft, question: e.target.value })} />}</Field>
      <Field label="پاسخ" help={MARKUP_HELP}>{(id, d) => <textarea id={id} aria-describedby={d} className="input min-h-28 leading-relaxed" value={draft.answer} onChange={(e) => setDraft({ ...draft, answer: e.target.value })} />}</Field>
      <label className="flex items-center gap-2"><input type="checkbox" className="size-4 accent-[var(--color-ink)]" checked={draft.published} onChange={(e) => setDraft({ ...draft, published: e.target.checked })} /> نمایش در سایت</label>
      {problem && <Notice tone="error">{problem}</Notice>}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => save()}>ذخیره</button>
        {onCancel && <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>انصراف</button>}
        {faq.id && <button type="button" className="btn btn-ghost btn-sm text-danger" onClick={() => window.confirm('این پرسش حذف شود؟') && save({ delete: true })}>حذف</button>}
      </div>
    </div>
  );
}

export default function TextsPage() {
  const { data, setData, error } = useLoad<Texts>('/api/panel/texts/');
  const [adding, setAdding] = useState(false);
  if (error) return <Notice tone="error">{message(error.error)}</Notice>;
  if (!data) return <Skeleton />;
  return (
    <>
      <Title>متن‌ها و پرسش‌ها</Title>
      <section className="grid gap-3 mb-10">
        <h2 className="text-lg font-bold">صفحه‌ها</h2>
        <p className="text-ink-soft -mt-1">متن‌هایی که در [کروشه] هستند منتظر تصمیم شما هستند؛ پیش از درخواست اینماد کاملشان کنید.</p>
        {data.pages.map((page) => <PageEditor key={page.id} page={page} onSaved={setData} />)}
      </section>
      <section className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-bold">پرسش‌های متداول</h2>
          {!adding && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAdding(true)}>پرسش تازه</button>}
        </div>
        {adding && <FaqEditor faq={{ question: '', answer: '', published: true }} onSaved={(t) => { setData(t); setAdding(false); }} onCancel={() => setAdding(false)} />}
        {data.faqs.map((faq) => <FaqEditor key={faq.id} faq={faq} onSaved={setData} />)}
      </section>
    </>
  );
}
