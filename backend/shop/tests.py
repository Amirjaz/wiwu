import io
import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from . import orders, persian
from .management.commands.seed_store import _luhn_complete
from .models import AuditLog, Card, Order, OtpCode, PaymentEvent, Product, ReturnRequest, SmsLog, StoreSettings
from .orders import OrderError


def valid_sheba(bban='017000000000123456789012'[:22]):
    """IR + check digits + a 22-digit BBAN (ISO 13616)."""
    check = 98 - int(bban + '182700') % 97
    return f'IR{check:02d}{bban}'


ADDRESS = {
    'phone': '09121234567', 'name': 'سارا رضایی', 'province': 'تهران', 'city': 'تهران',
    'address': 'خیابان ولیعصر، کوچه یکم، پلاک ۱۰', 'postal_code': '1919191919', 'shipping': 'post', 'is_gift': False,
}


class Base(TestCase):
    def setUp(self):
        call_command('seed_store', stdout=io.StringIO())
        call_command('setup_roles', stdout=io.StringIO())
        self.store = StoreSettings.load()
        self.store.owner_mobile = '09350000000'
        self.store.save()
        self.product = Product.objects.get(slug='alpha')

    def place(self, **changes):
        return orders.place(self.product, {**ADDRESS, **changes})


class PersianInputTests(TestCase):
    def test_phone_forms(self):
        for raw in ('09121234567', '۰۹۱۲۱۲۳۴۵۶۷', '+989121234567', '00989121234567', '9121234567', '0912 123 4567'):
            self.assertEqual(persian.phone(raw), '09121234567', raw)
        for raw in ('0912123456', '02112345678', '+441234567890', ''):
            self.assertIsNone(persian.phone(raw), raw)

    def test_postal_code(self):
        self.assertEqual(persian.postal_code('۱۹۱۹۱-۹۱۹۱۹'), '1919191919')
        self.assertIsNone(persian.postal_code('0123456789'))
        self.assertIsNone(persian.postal_code('12345'))

    def test_sheba_checksum(self):
        good = valid_sheba()
        self.assertEqual(persian.sheba(good.lower().replace('ir', 'IR ')), good)
        self.assertEqual(persian.sheba(good[2:]), good)  # without IR
        broken = good[:-1] + ('0' if good[-1] != '0' else '1')
        self.assertIsNone(persian.sheba(broken))

    def test_card_luhn(self):
        good = _luhn_complete('603799000000001')
        self.assertEqual(persian.card_number('-'.join([good[:4], good[4:8], good[8:12], good[12:]])), good)
        self.assertIsNone(persian.card_number(good[:-1] + str((int(good[-1]) + 1) % 10)))

    def test_toman(self):
        self.assertEqual(persian.toman(100_003_600), '۱۰٬۰۰۰٬۳۶۰')

    def test_arabic_letters(self):
        self.assertEqual(persian.clean_text('علي  كريمي'), 'علی کریمی')


class PlaceOrderTests(Base):
    def test_amount_is_price_shipping_and_unique_offset(self):
        a, b = self.place(), self.place()
        base = self.product.price_rial + self.store.shipping_post_rial
        for order in (a, b):
            self.assertEqual(order.amount_rial, base + order.offset_rial)
            self.assertTrue(10 <= order.offset_rial <= 9990 and order.offset_rial % 10 == 0)
        self.assertNotEqual(a.amount_rial, b.amount_rial)

    def test_amount_avoids_recently_expired_orders(self):
        old = self.place()
        Order.objects.filter(pk=old.pk).update(status=Order.Status.EXPIRED)
        offered = {}
        with mock.patch('shop.orders.random.choice', side_effect=lambda free: offered.setdefault('free', free)[0]):
            orders.choose_amount(self.product.price_rial + self.store.shipping_post_rial)
        self.assertNotIn(old.offset_rial, offered['free'])
        self.assertEqual(len(offered['free']), orders.OFFSET_MAX_TOMAN - 1)

    def test_busy_when_every_offset_is_taken(self):
        base = self.product.price_rial
        with mock.patch('shop.orders._amounts_in_use', return_value={base + t * 10 for t in range(1, 1000)}):
            with self.assertRaises(OrderError) as ctx:
                orders.choose_amount(base)
        self.assertEqual(ctx.exception.code, 'busy')

    def test_price_and_card_are_copied(self):
        order = self.place(shipping='tipax', is_gift=True)
        self.assertEqual(order.shipping_rial, self.store.shipping_tipax_rial)
        self.product.price_rial = 1
        self.product.save()
        order.refresh_from_db()
        self.assertEqual(order.unit_price_rial, 100_000_000)
        self.assertEqual(order.card_number, Card.objects.first().number)
        self.assertTrue(order.is_gift)

    def test_cards_rotate(self):
        Card.objects.create(bank='ملت', number='6104337000000006', holder='صاحب فروشگاه')
        used = {self.place().card_number for _ in range(4)}
        self.assertEqual(len(used), 2)

    def test_unavailable(self):
        self.product.is_available = False
        self.product.save()
        with self.assertRaises(OrderError):
            self.place()

    def test_created_sms_has_link_and_persian_amount(self):
        order = self.place()
        text = SmsLog.objects.get(kind='order_created').text
        self.assertIn(f'/o/{order.token}/', text)
        self.assertIn(persian.toman(order.amount_rial), text)


class OtpTests(Base):
    def test_gap_limit_and_tries(self):
        orders.send_otp('09121234567', '1.2.3.4')
        with self.assertRaises(OrderError) as ctx:
            orders.send_otp('09121234567', '1.2.3.4')
        self.assertEqual(ctx.exception.code, 'otp_wait')
        for _ in range(orders.OTP_MAX_TRIES):
            with self.assertRaises(OrderError):
                orders.check_otp('09121234567', '00000')
        with self.assertRaises(OrderError) as ctx:
            orders.check_otp('09121234567', '00000')
        self.assertEqual(ctx.exception.code, 'otp_tries')

    def test_code_works_once(self):
        with mock.patch('shop.orders.secrets.randbelow', return_value=12345):
            orders.send_otp('09121234567', None)
        orders.check_otp('09121234567', '22345')
        with self.assertRaises(OrderError):
            orders.check_otp('09121234567', '22345')

    def test_hourly_limit(self):
        for i in range(orders.OTP_PER_HOUR):
            OtpCode.objects.create(phone='09121234567', code_hash='x')
            OtpCode.objects.filter(phone='09121234567').update(created_at=timezone.now() - timedelta(minutes=5 + i))
        with self.assertRaises(OrderError) as ctx:
            orders.send_otp('09121234567', None)
        self.assertEqual(ctx.exception.code, 'otp_limit')


class PaymentTests(Base):
    def test_deposit_matches_and_notifies(self):
        order = self.place()
        event = orders.deposit(order.amount_rial, 'cartbecart', {}, 'ref-1')
        order.refresh_from_db()
        self.assertEqual((event.outcome, order.status, order.paid_via), ('matched', 'paid', 'auto'))
        self.assertEqual(set(SmsLog.objects.values_list('kind', flat=True)), {'order_created', 'paid', 'owner_new_order'})

    def test_same_deposit_twice(self):
        order = self.place()
        orders.deposit(order.amount_rial, 'cartbecart', {}, 'ref-1')
        self.assertEqual(orders.deposit(order.amount_rial, 'cartbecart', {}, 'ref-1').outcome, 'repeat')
        self.assertEqual(orders.deposit(order.amount_rial, 'cartbecart', {}, 'ref-2').outcome, 'second')

    def test_late_money_goes_to_review(self):
        order = self.place()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        event = orders.deposit(order.amount_rial, 'cartbecart', {}, 'r')
        order.refresh_from_db()
        self.assertEqual((event.outcome, order.status), ('late', 'needs_review'))
        self.assertTrue(SmsLog.objects.filter(kind='owner_review').exists())

    def test_unmatched_and_wrong_amount(self):
        order = self.place()
        self.assertEqual(orders.deposit(order.amount_rial + 10, 'cartbecart', {}, 'x').outcome, 'unmatched')
        order.refresh_from_db()
        self.assertEqual(order.status, 'awaiting_payment')

    def test_toman_amounts_are_converted(self):
        from . import payments
        with mock.patch.dict('os.environ', {'CARTBECART_AMOUNT_UNIT': 'toman'}):
            self.assertEqual(payments.parse({'amount': '10,000,360'})[0], 100_003_600)
        self.assertEqual(payments.parse({'data': {'amount': 100_003_600, 'id': 7}}), (100_003_600, '7'))
        self.assertEqual(payments.parse({'nothing': 1})[0], None)

    def test_claim_then_approve(self):
        order = self.place()
        orders.claim(order, {'reference': '123456', 'last4': '1234', 'time': 'الان', 'note': ''})
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')
        owner = User.objects.create_user('owner', password='x')
        owner.groups.add(Group.objects.get(name='Owners'))
        self.assertTrue(orders.mark_paid(order, 'manual', owner))
        order.refresh_from_db()
        self.assertEqual((order.status, order.paid_via, order.confirmed_by), ('paid', 'manual', owner))
        with self.assertRaises(OrderError):
            orders.claim(order, {'reference': '1', 'last4': '', 'time': '', 'note': ''})

    def test_reject(self):
        order = self.place()
        orders.claim(order, {'reference': '1', 'last4': '', 'time': '', 'note': ''})
        self.assertTrue(orders.reject_payment(order, None, 'not found'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertTrue(SmsLog.objects.filter(kind='payment_not_found').exists())


class TickTests(Base):
    def test_reminder_then_expiry(self):
        order = self.place()
        start = order.created_at
        self.assertEqual(orders.tick(start + timedelta(minutes=5))['reminded'], 0)
        Order.objects.filter(pk=order.pk).update(created_at=start - timedelta(minutes=16))
        self.assertEqual(orders.tick()['reminded'], 1)
        self.assertEqual(orders.tick()['reminded'], 0)  # only once
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(orders.tick()['expired'], 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'expired')

    @override_settings(PAYMENT_PROVIDER='cartbecart')
    def test_forwarder_alert_once(self):
        for _ in range(2):
            order = self.place()
            Order.objects.filter(pk=order.pk).update(status=Order.Status.EXPIRED)
        self.assertTrue(orders.tick()['alerted'])
        self.assertFalse(orders.tick()['alerted'])


class ReturnTests(Base):
    def delivered(self, when):
        order = self.place()
        Order.objects.filter(pk=order.pk).update(status=Order.Status.DELIVERED, delivered_at=when)
        order.refresh_from_db()
        return order

    def test_deadline_skips_fridays(self):
        saturday = timezone.make_aware(timezone.datetime(2026, 10, 10, 12))  # a Saturday
        order = self.delivered(saturday)
        # 7 working days: Sun..Thu (5), skip Fri 16, Sat 17, Sun 18 → 18 Oct.
        self.assertEqual(orders.return_deadline(order).isoformat(), '2026-10-18')

    def test_request_refund_flow(self):
        order = self.delivered(timezone.now())
        ret = orders.request_return(order, {'reason': 'اندازه مناسب نبود', 'sheba': valid_sheba(), 'holder': 'سارا رضایی'})
        with self.assertRaises(OrderError):
            orders.request_return(order, {'reason': 'دوباره', 'sheba': valid_sheba(), 'holder': 'سارا'})
        self.assertTrue(orders.return_received(ret, None))
        self.assertTrue(orders.refund(ret, None, '998877'))
        ret.refresh_from_db()
        self.assertEqual((ret.status, ret.refund_reference), ('refunded', '998877'))

    def test_closed_after_deadline(self):
        order = self.delivered(timezone.now() - timedelta(days=20))
        with self.assertRaises(OrderError) as ctx:
            orders.request_return(order, {'reason': 'x' * 10, 'sheba': valid_sheba(), 'holder': 'سارا'})
        self.assertEqual(ctx.exception.code, 'return_closed')


class ApiTests(Base):
    def otp(self, phone='09121234567'):
        with mock.patch('shop.orders.secrets.randbelow', return_value=12345):
            response = self.client.post('/api/otp/', {'phone': phone}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return '22345'

    def test_buyer_flow(self):
        code = self.otp()
        response = self.client.post('/api/orders/', {**ADDRESS, 'phone': '۰۹۱۲۱۲۳۴۵۶۷', 'code': code},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()['token']
        self.assertEqual(self.client.get(f'/o/{token}/').status_code, 200)
        data = self.client.get(f'/api/orders/{token}/').json()
        self.assertEqual(data['status'], 'awaiting_payment')
        self.assertEqual(len(data['card']['number']), 16)

        screenshot = SimpleUploadedFile('r.png', b'\x89PNG fake', content_type='image/png')
        response = self.client.post(f'/api/orders/{token}/claim/', {'reference': '123456', 'file': screenshot})
        self.assertEqual(response.json()['status'], 'needs_review')

    def test_field_errors(self):
        response = self.client.post('/api/orders/', {'phone': '123'}, content_type='application/json')
        self.assertEqual(response.json()['error'], 'fields')
        self.assertIn('postal_code', response.json()['fields'])

    def test_wrong_code(self):
        self.otp()
        response = self.client.post('/api/orders/', {**ADDRESS, 'code': '11111'}, content_type='application/json')
        self.assertEqual(response.json()['error'], 'otp_wrong')
        self.assertFalse(Order.objects.exists())

    def test_lookup(self):
        order = self.place()
        code = self.otp()
        response = self.client.post('/api/lookup/', {'phone': '09121234567', 'code': code}, content_type='application/json')
        self.assertEqual(response.json()['orders'][0]['code'], order.code)

    def test_pages_render(self):
        for url in ('/', '/checkout/', '/orders/', '/p/terms/', '/robots.txt', '/sitemap.xml', '/panel/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    @override_settings(PAYMENT_PROVIDER='cartbecart', CARTBECART_WEBHOOK_SECRET='s3cret')
    def test_webhook(self):
        order = self.place()
        body = json.dumps({'amount': order.amount_rial, 'id': 'abc'})
        self.assertEqual(self.client.post('/api/payments/cartbecart/wrong/', body, content_type='application/json').status_code, 404)
        response = self.client.post('/api/payments/cartbecart/s3cret/', body, content_type='application/json')
        self.assertEqual(response.json()['outcome'], 'matched')
        response = self.client.post('/api/payments/cartbecart/s3cret/', '{"hello": 1}', content_type='application/json')
        self.assertEqual(response.json()['outcome'], 'unparsed')
        self.assertEqual(PaymentEvent.objects.count(), 2)


class PanelTests(Base):
    def user(self, role):
        user = User.objects.create_user(role.lower(), password='pw-123456!')
        user.groups.add(Group.objects.get(name=role))
        self.client.post('/api/panel/login/', {'username': user.username, 'password': 'pw-123456!'},
                         content_type='application/json')
        return user

    def test_staff_cannot_approve_or_edit(self):
        order = self.place()
        self.user('Staff')
        response = self.client.post(f'/api/panel/orders/{order.pk}/action/', {'action': 'approve'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/api/panel/settings/').status_code, 403)
        self.assertEqual(self.client.get('/api/panel/orders/?queue=awaiting').json()['total'], 1)

    def test_owner_approves_ships_and_slip_hides_gift_price(self):
        order = self.place(is_gift=True)
        self.user('Owners')
        post = lambda action, **kw: self.client.post(f'/api/panel/orders/{order.pk}/action/', {'action': action, **kw},
                                                     content_type='application/json')
        self.assertEqual(post('approve').json()['status'], 'paid')
        self.assertEqual(post('approve').json()['error'], 'state')
        self.assertEqual(post('ship', tracking='۱۲۳۴۵۶۷۸۹').json()['tracking'], '123456789')
        slip = self.client.get(f'/panel/slip/{order.pk}/').content.decode()
        self.assertNotIn(persian.toman(order.unit_price_rial), slip)

    def test_signed_out(self):
        self.assertEqual(self.client.get('/api/panel/summary/').status_code, 401)

    def test_price_change_is_audited(self):
        self.user('Owners')
        response = self.client.post('/api/panel/settings/', {'product': {'price_rial': '۹۸۰۰۰۰۰۰'}},
                                    content_type='application/json')
        self.assertEqual(response.json()['product']['price_rial'], 98_000_000)
        self.assertTrue(AuditLog.objects.filter(action='price').exists())
