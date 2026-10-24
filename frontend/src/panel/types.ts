export interface User {
  username: string;
  name: string;
  can: { approve: boolean; refund: boolean; manage: boolean };
}

export type Status = 'awaiting_payment' | 'needs_review' | 'paid' | 'preparing' | 'shipped' | 'delivered' | 'expired' | 'cancelled';

export interface OrderRow {
  id: number;
  code: string;
  status: Status;
  status_label: string;
  name: string;
  phone: string;
  city: string;
  amount_rial: number;
  shipping: string;
  is_gift: boolean;
  color: string; // the colour as ordered; empty for products without colours
  created: string;
  paid_at: string | null;
  claimed: boolean;
}

export interface ReturnRow {
  id: number;
  order_id: number;
  code: string;
  name: string;
  status: 'requested' | 'received' | 'refunded' | 'rejected';
  status_label: string;
  reason: string;
  sheba: string;
  holder: string;
  reference: string;
  created: string;
  amount_rial: number;
}

export interface OrderDetail extends OrderRow {
  token: string;
  province: string;
  address: string;
  postal_code: string;
  product: string;
  price_rial: number;
  shipping_rial: number;
  shipping_on_delivery: boolean;
  offset_rial: number;
  pay_in_rial: boolean;
  provider_ref: string; // cartbecart's CBC-… code
  card: { bank: string; number: string; holder: string };
  // Paid in several card-to-card transfers (over the bank's cap); empty for one.
  transfers: { position: number; amount_rial: number; offset_rial: number; card: { bank: string; number: string };
    provider_ref: string; status: string; status_label: string; paid_at: string | null }[];
  expires: string;
  paid_via: string;
  confirmed_by: string | null;
  claim: { reference: string; last4: string; time: string; note: string; file: boolean; at: string | null };
  tracking: string;
  staff_note: string;
  shipped_at: string | null;
  delivered_at: string | null;
  history: { action: string; detail: string; at: string; user: string | null }[];
  sms: { kind: string; text: string; status: string; error: string; at: string }[];
  payments: { source: string; amount_rial: number | null; outcome: string; at: string }[];
  returns: ReturnRow[];
}

export const STATUS_TONE: Record<Status, string> = {
  awaiting_payment: 'bg-surface text-ink-soft border border-line',
  needs_review: 'bg-warn-soft text-warn',
  paid: 'bg-accent-soft text-accent-ink',
  preparing: 'bg-accent-soft text-accent-ink',
  shipped: 'bg-ink text-raised',
  delivered: 'bg-surface text-ink-soft border border-line',
  expired: 'bg-surface text-muted border border-line',
  cancelled: 'bg-danger-soft text-danger',
};

export const ACTIONS: Record<string, string> = {
  placed: 'سفارش ثبت شد',
  expired: 'مهلت پرداخت تمام شد',
  paid: 'پرداخت تأیید شد',
  transfer_paid: 'یکی از واریزها رسید',
  needs_review: 'نیاز به بررسی پرداخت',
  payment_rejected: 'پرداخت رد شد',
  second_deposit: 'واریز تکراری',
  preparing: 'آماده‌سازی',
  shipped: 'ارسال شد',
  delivered: 'تحویل شد',
  cancelled: 'لغو شد',
  note: 'یادداشت',
  return_requested: 'درخواست بازگشت',
  return_received: 'کالای برگشتی رسید',
  refunded: 'بازپرداخت شد',
  return_rejected: 'بازگشت رد شد',
  price: 'تغییر قیمت',
  settings: 'تغییر تنظیمات',
  cards: 'تغییر کارت‌ها',
  texts: 'تغییر متن‌ها',
};
