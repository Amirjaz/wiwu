const FA = '۰۱۲۳۴۵۶۷۸۹';

export function fa(value: string | number): string {
  return String(value).replace(/[0-9]/g, (d) => FA[Number(d)]);
}

export function latin(value: string): string {
  return value.replace(/[۰-۹]/g, (d) => String(FA.indexOf(d))).replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
}

/** '۱۰٬۰۰۰٬۳۶۰' for 100003600 rials. */
export function toman(rial: number): string {
  return fa(Math.floor(rial / 10).toLocaleString('en-US')).replace(/,/g, '٬');
}

/** A shipping fee as the buyer reads it: the amount, free, or paid to the courier on delivery. */
export function shippingFee(rial: number, onDelivery = false): string {
  if (onDelivery) return 'پس‌کرایه';
  return rial ? `${toman(rial)} تومان` : 'رایگان';
}

/** The plain toman number for pasting into a bank app: '10000360'. */
export function tomanPlain(rial: number): string {
  return String(Math.floor(rial / 10));
}

export function groupCard(number: string): string {
  return number.replace(/(\d{4})(?=\d)/g, '$1 ');
}

/** 'mm:ss' in Persian digits. */
export function clock(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return fa(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`);
}

const MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];

/** '۲۲ مهر، ۱۸:۳۵' in Tehran time (the browser's Persian calendar). */
export function when(iso: string | null | undefined, withYear = false): string {
  if (!iso) return '';
  const date = new Date(iso);
  const parts = new Intl.DateTimeFormat('en-US-u-ca-persian', {
    timeZone: 'Asia/Tehran', year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(date);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  const day = `${Number(pick('day'))} ${MONTHS[Number(pick('month')) - 1]}${withYear ? ` ${pick('year').replace(/\D/g, '')}` : ''}`;
  return fa(`${day}، ${pick('hour').replace('24', '00')}:${pick('minute')}`);
}

export function cleanPhone(raw: string): string | null {
  let digits = latin(raw).replace(/\D/g, '');
  if (digits.startsWith('0098')) digits = digits.slice(4);
  else if (digits.startsWith('98') && digits.length === 12) digits = digits.slice(2);
  if (digits.length === 10 && digits.startsWith('9')) digits = `0${digits}`;
  return /^09\d{9}$/.test(digits) ? digits : null;
}
