import { StrictMode, useState, type FormEvent, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom';
import clsx from 'clsx';
import { House, Receipt, ArrowUUpLeft, GearSix, DotsThreeOutline, SignOut, ArrowSquareOut } from '@phosphor-icons/react';
import { isApiError } from '../lib/api';
import { message } from '../lib/messages';
import { Field, Notice } from '../lib/ui';
import { SessionProvider, useSession } from './session';
import Today from './pages/Today';
import Orders from './pages/Orders';
import OrderPage from './pages/OrderPage';
import Returns from './pages/Returns';
import Settings from './pages/Settings';
import Texts from './pages/Texts';
import Logs from './pages/Logs';
import More from './pages/More';

function Login() {
  const { signIn } = useSession();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [problem, setProblem] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setProblem('');
    try {
      await signIn(username, password);
    } catch (err) {
      setProblem(isApiError(err) ? message(err.error) : message('unknown'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] grid place-items-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm grid gap-5 rounded-[var(--radius-surface)] bg-raised border border-line p-7">
        <h1 className="text-2xl font-extrabold">ورود به پنل فروشگاه</h1>
        <Field label="نام کاربری">
          {(id) => <input id={id} className="input ltr" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />}
        </Field>
        <Field label="گذرواژه">
          {(id) => <input id={id} type="password" className="input ltr" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        {problem && <Notice tone="error">{problem}</Notice>}
        <button type="submit" className="btn btn-primary" disabled={busy || !username || !password}>{busy ? 'در حال ورود…' : 'ورود'}</button>
      </form>
    </main>
  );
}

const NAV = [
  { to: '/', label: 'امروز', Icon: House, end: true },
  { to: '/orders', label: 'سفارش‌ها', Icon: Receipt },
  { to: '/returns', label: 'بازگشت‌ها', Icon: ArrowUUpLeft },
  { to: '/settings', label: 'فروشگاه', Icon: GearSix, manage: true },
];

function Shell({ children }: { children: ReactNode }) {
  const { user, signOut } = useSession();
  const items = NAV.filter((n) => !n.manage || user?.can.manage);
  const link = (isActive: boolean) =>
    clsx('flex items-center gap-3 rounded-full px-4 py-2.5 transition-colors', isActive ? 'bg-ink text-raised' : 'text-ink-soft hover:bg-surface');
  return (
    <div className="min-h-[100dvh] md:grid md:grid-cols-[240px_1fr]">
      <aside className="hidden md:flex md:flex-col gap-1 border-e border-line bg-surface p-4 sticky top-0 h-[100dvh]">
        <p className="px-4 py-3 text-lg font-extrabold">پنل فروشگاه</p>
        {items.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => link(isActive)}>
            <Icon size={20} aria-hidden /> {label}
          </NavLink>
        ))}
        <NavLink to="/texts" className={({ isActive }) => link(isActive)} hidden={!user?.can.manage}>متن‌ها و پرسش‌ها</NavLink>
        <NavLink to="/logs" className={({ isActive }) => link(isActive)}>گزارش‌ها</NavLink>
        <div className="mt-auto grid gap-1 text-sm">
          <a href="/" target="_blank" rel="noopener" className="flex items-center gap-2 px-4 py-2 text-ink-soft hover:text-ink"><ArrowSquareOut size={18} aria-hidden /> دیدن سایت</a>
          <button type="button" onClick={signOut} className="flex items-center gap-2 px-4 py-2 text-ink-soft hover:text-ink"><SignOut size={18} aria-hidden /> خروج ({user?.name})</button>
        </div>
      </aside>
      <main className="px-4 sm:px-6 pt-6 pb-28 md:pb-10 max-w-5xl w-full">{children}</main>
      <nav className="md:hidden fixed inset-x-0 bottom-0 z-40 border-t border-line bg-raised/95 backdrop-blur pb-[env(safe-area-inset-bottom)]" aria-label="پنل">
        <div className="grid grid-cols-5">
          {items.slice(0, 4).map(({ to, label, Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => clsx('flex flex-col items-center gap-1 py-2.5 text-xs', isActive ? 'text-ink font-bold' : 'text-muted')}>
              <Icon size={24} aria-hidden /> {label}
            </NavLink>
          ))}
          <NavLink to="/more" className={({ isActive }) => clsx('flex flex-col items-center gap-1 py-2.5 text-xs', isActive ? 'text-ink font-bold' : 'text-muted')}>
            <DotsThreeOutline size={24} aria-hidden /> بیشتر
          </NavLink>
        </div>
      </nav>
    </div>
  );
}

function App() {
  const { user, ready } = useSession();
  if (!ready) return null;
  if (!user) return <Login />;
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Today />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/orders/:id" element={<OrderPage />} />
        <Route path="/returns" element={<Returns />} />
        <Route path="/settings" element={user.can.manage ? <Settings /> : <Navigate to="/" />} />
        <Route path="/texts" element={user.can.manage ? <Texts /> : <Navigate to="/" />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/more" element={<More />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}

createRoot(document.getElementById('panel-root')!).render(
  <StrictMode>
    <BrowserRouter basename="/panel">
      <SessionProvider>
        <App />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
