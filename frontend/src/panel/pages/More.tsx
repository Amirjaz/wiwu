import { Link } from 'react-router-dom';
import { ArrowSquareOut, ClipboardText, ListBullets, SignOut } from '@phosphor-icons/react';
import { useSession } from '../session';
import { Title } from '../parts';

export default function More() {
  const { user, signOut } = useSession();
  const item = 'flex items-center gap-3 rounded-[var(--radius-field)] border border-line bg-raised p-4 text-lg';
  return (
    <>
      <Title>بیشتر</Title>
      <div className="grid gap-2">
        {user?.can.manage && <Link to="/texts" className={item}><ClipboardText size={22} aria-hidden /> متن‌ها و پرسش‌ها</Link>}
        <Link to="/logs" className={item}><ListBullets size={22} aria-hidden /> گزارش‌ها</Link>
        <a href="/" target="_blank" rel="noopener" className={item}><ArrowSquareOut size={22} aria-hidden /> دیدن سایت</a>
        <button type="button" onClick={signOut} className={item}><SignOut size={22} aria-hidden /> خروج ({user?.name})</button>
      </div>
    </>
  );
}
