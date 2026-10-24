import io
import json
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import orders, persian
from .management.commands.seed_store import _luhn_complete
from .models import (AuditLog, Card, Order, OtpCode, PaymentEvent, Product, ReturnRequest, Sheba, SmsLog,
                     StoreSettings)
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
        # The store as these tests assume it: black only (seed_store also adds brown; ColorTests
        # add the colours they need).
        self.product.colors.exclude(name='مشکی').delete()

    def place(self, **changes):
        return orders.place(self.product, {**ADDRESS, **changes})

    def otp(self, phone='09121234567'):
        """Asks for an SMS code through the API; returns it."""
        with mock.patch('shop.orders.secrets.randbelow', return_value=12345):
            response = self.client.post('/api/otp/', {'phone': phone}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return '22345'


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
        self.assertEqual(order.shipping_rial, 0)
        self.assertTrue(order.shipping_on_delivery)  # the buyer pays Tipax on delivery
        self.product.price_rial = 1
        self.product.save()
        order.refresh_from_db()
        self.assertEqual(order.unit_price_rial, 141_000_000)
        self.assertEqual(order.card_number, Card.objects.first().number)
        self.assertTrue(order.is_gift)

    def test_shipping_free_by_post_and_tipax_on_delivery(self):
        post = self.place()
        self.assertEqual((post.shipping_rial, post.shipping_on_delivery), (0, False))
        self.assertEqual(post.amount_rial, self.product.price_rial + post.offset_rial)
        # A Tipax fee the store charges itself, once it stops being paid on delivery.
        self.store.tipax_on_delivery, self.store.shipping_tipax_rial = False, 900_000
        self.store.save()
        tipax = self.place(shipping='tipax')
        self.assertEqual((tipax.shipping_rial, tipax.shipping_on_delivery), (900_000, False))

    def test_seeding_again_keeps_free_shipping(self):
        call_command('seed_store', stdout=io.StringIO())  # runs on every deploy
        store = StoreSettings.load()
        self.assertEqual((store.shipping_post_rial, store.shipping_tipax_rial, store.tipax_on_delivery), (0, 0, True))

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


@override_settings(SMS_BACKEND='kavenegar', KAVENEGAR_API_KEY='KEY', KAVENEGAR_SENDER='2000660110',
                   KAVENEGAR_TEMPLATES=[])
class KavenegarTests(Base):
    """Kavenegar's API is faked: each test sees what would have been posted to it."""

    def fake_api(self, *answers):
        """Patches urlopen to answer with these bodies (dicts, or HTTPError for a refusal) in turn."""
        import urllib.error
        from urllib.parse import parse_qs
        self.calls = []
        answers = list(answers) or [{'return': {'status': 200, 'message': 'تایید شد'}, 'entries': []}]

        def urlopen(request, timeout):
            self.calls.append((request.full_url, {k: v[0] for k, v in parse_qs(request.data.decode()).items()}))
            answer = answers.pop(0) if len(answers) > 1 else answers[0]
            if isinstance(answer, urllib.error.HTTPError):
                raise answer
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(answer).encode()
            return response
        return mock.patch('shop.sms.urllib.request.urlopen', side_effect=urlopen)

    def test_plain_text_from_the_sender_line(self):
        with self.fake_api(), mock.patch('shop.orders.secrets.randbelow', return_value=12345):
            orders.send_otp('09121234567', None)
        url, params = self.calls[0]
        self.assertEqual(url, 'https://api.kavenegar.com/v1/KEY/sms/send.json')
        self.assertEqual(params['receptor'], '09121234567')
        self.assertEqual(params['sender'], '2000660110')
        self.assertIn('22345', params['message'])
        self.assertEqual(SmsLog.objects.get(kind='otp').status, 'sent')

    @override_settings(KAVENEGAR_SENDER='')
    def test_no_sender_uses_the_default_line(self):
        from . import sms
        with self.fake_api():
            sms.send('owner_review', '09350000000', code='A1')
        self.assertNotIn('sender', self.calls[0][1])

    @override_settings(KAVENEGAR_TEMPLATES=['otp'])
    def test_listed_kinds_use_their_template(self):
        from . import sms
        with self.fake_api():
            sms.send('otp', '09121234567', code='12345')
            sms.send('paid', '09121234567', code='A1B2', link='https://x.ir/o/1')
        (otp_url, otp), (paid_url, paid) = self.calls
        self.assertEqual(otp_url, 'https://api.kavenegar.com/v1/KEY/verify/lookup.json')
        self.assertEqual(otp, {'receptor': '09121234567', 'template': 'ps-otp', 'token': '12345'})
        self.assertTrue(paid_url.endswith('/sms/send.json'))

    @override_settings(KAVENEGAR_TEMPLATES=['all'])
    def test_all_templates(self):
        from . import sms
        with self.fake_api():
            sms.send('shipped', '09121234567', code='A1', tracking='T 9', link='https://x.ir/o/1', carrier='پست پیشتاز')
        url, params = self.calls[0]
        self.assertTrue(url.endswith('/verify/lookup.json'))
        self.assertEqual(params['template'], 'ps-shipped')
        self.assertEqual(params['token2'], 'T‌9')  # no spaces in token..token3
        self.assertEqual(params['token10'], 'پست پیشتاز')

    def test_refusal_is_logged_with_kavenegars_reason(self):
        import urllib.error
        body = json.dumps({'return': {'status': 418, 'message': 'اعتبار حساب شما کافی نیست'}, 'entries': None})
        refusal = urllib.error.HTTPError('https://api.kavenegar.com/', 418, 'x', {}, io.BytesIO(body.encode()))
        with self.fake_api(refusal), self.assertRaises(OrderError) as ctx:
            orders.send_otp('09121234567', None)
        self.assertEqual(ctx.exception.code, 'sms_failed')
        entry = SmsLog.objects.get(kind='otp')
        self.assertEqual(entry.status, 'failed')
        self.assertIn('418', entry.error)
        self.assertIn('اعتبار', entry.error)
        self.assertNotIn('KEY', entry.error)

    def test_sms_check(self):
        info = {'return': {'status': 200, 'message': 'تایید شد'},
                'entries': {'remaincredit': 1250000, 'expiredate': 1798761600, 'type': 'master'}}
        sent = {'return': {'status': 200, 'message': 'تایید شد'}, 'entries': []}
        out = io.StringIO()
        with self.fake_api(info, sent):
            call_command('sms_check', '۰۹۱۲۱۲۳۴۵۶۷', stdout=out)
        self.assertIn('125,000 toman', out.getvalue())
        self.assertIn('Test code sent to 09121234567', out.getvalue())
        self.assertEqual([url.rsplit('/v1/KEY/')[1] for url, _ in self.calls], ['account/info.json', 'sms/send.json'])

    @override_settings(KAVENEGAR_TEMPLATES=['otpp'])
    def test_sms_check_catches_a_misspelt_kind(self):
        from django.core.management.base import CommandError
        with self.fake_api(), self.assertRaises(CommandError):
            call_command('sms_check', stdout=io.StringIO())
        self.assertEqual(self.calls, [])


class PaymentTests(Base):
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


class SplitTests(Base):
    """Over the bank's cap for one card-to-card (15M toman by default) an order is paid in several transfers."""

    def test_split_amounts(self):
        split, cap = orders.split_amounts, 150_000_000
        self.assertEqual(split(141_000_000, cap), [141_000_000])  # the Alpha: one transfer
        self.assertEqual(split(165_000_000, cap), [115_000_000, 50_000_000])  # 16.5M: 11.5M + 5M (Amir)
        self.assertEqual(split(150_000_000, cap), [100_000_000, 50_000_000])  # the offset would take it over
        self.assertEqual(split(220_000_000, cap), [120_000_000, 50_000_000, 50_000_000])
        self.assertEqual(split(165_000_000, 0), [165_000_000])  # splitting off

    def test_order_over_the_cap_has_round_transfers_with_their_own_amounts(self):
        self.product.price_rial = 165_000_000
        self.product.save()
        order = self.place()
        first, second = order.transfers.all()
        self.assertEqual((first.amount_rial - first.offset_rial, second.amount_rial - second.offset_rial), (115_000_000, 50_000_000))
        self.assertNotEqual(first.offset_rial, 0)
        self.assertEqual(order.amount_rial, first.amount_rial + second.amount_rial)
        self.assertEqual(first.card_number, order.card_number)
        self.assertFalse(order.pay_in_rial)  # the shop's own amounts are whole tomans
        self.assertIn(f'{persian.toman(first.amount_rial)} تومان و {persian.toman(second.amount_rial)} تومان',
                      SmsLog.objects.get(kind='order_created').text)
        # Another order can't be given an amount either of these has.
        self.assertTrue({first.amount_rial, second.amount_rial} <= orders._amounts_in_use())

    def test_under_the_cap_or_with_splitting_off_one_transfer(self):
        self.assertFalse(self.place().transfers.exists())  # 14.1M
        self.product.price_rial = 165_000_000
        self.product.save()
        self.store.transfer_limit_rial = 0
        self.store.save()
        self.assertFalse(self.place().transfers.exists())

    def test_staff_approval_marks_every_transfer_paid(self):
        self.product.price_rial = 165_000_000
        self.product.save()
        order = self.place()
        self.assertTrue(orders.mark_paid(order, 'manual'))
        self.assertEqual(set(order.transfers.values_list('status', flat=True)), {'paid'})

    def test_checkout_tells_the_buyer(self):
        self.product.price_rial = 165_000_000
        self.product.save()
        page = self.client.get('/checkout/').content.decode()
        data = json.loads(re.search(r'<script id="island-data" type="application/json">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(data['models'][0]['transfers']['post'], [115_000_000, 50_000_000])


class ShebaTests(Base):
    """Sheba as a second way to pay (Amir, 2026-10-24): chosen on the order page, checked by staff."""

    def setUp(self):
        super().setUp()
        Sheba.objects.all().delete()  # migration 0011's
        self.sheba = Sheba.objects.create(number=valid_sheba(), holder='محمدسالار کبیری', bank='بانک ملت')

    def choose(self, order):
        return self.client.post(f'/api/orders/{order.token}/sheba/', {}, content_type='application/json').json()

    def sign_in_owner(self):
        owner = User.objects.create_user('owner', password='pw-123456!')
        owner.groups.add(Group.objects.get(name='Owners'))
        self.client.post('/api/panel/login/', {'username': 'owner', 'password': 'pw-123456!'}, content_type='application/json')

    def test_offered_only_when_the_shop_has_a_sheba(self):
        order = self.place()
        data = self.client.get(f'/api/orders/{order.token}/').json()
        self.assertEqual((data['payment_method'], data['sheba_offered'], data['sheba']), ('card', True, None))
        self.sheba.active = False
        self.sheba.save()
        self.assertFalse(self.client.get(f'/api/orders/{order.token}/').json()['sheba_offered'])
        self.assertEqual(self.choose(order)['error'], 'sheba_closed')

    def test_choosing_it_waits_longer_and_shows_the_shop_sheba(self):
        order = self.place()
        data = self.choose(order)
        self.assertEqual(data['payment_method'], 'sheba')
        self.assertEqual(data['sheba'], {'number': valid_sheba(), 'holder': 'محمدسالار کبیری', 'bank': 'بانک ملت'})
        self.assertEqual(data['shebas'], [data['sheba']])
        order.refresh_from_db()
        self.assertAlmostEqual((order.expires_at - timezone.now()).total_seconds(), 180 * 60, delta=60)
        self.assertTrue(AuditLog.objects.filter(order=order, action='sheba_chosen').exists())
        self.assertEqual(self.choose(order)['payment_method'], 'sheba')  # again: no change
        self.assertEqual(AuditLog.objects.filter(order=order, action='sheba_chosen').count(), 1)

    def test_not_after_the_window(self):
        order = self.place()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.choose(order)['error'], 'sheba_closed')

    def test_no_card_reminder_for_a_sheba_order(self):
        order = self.place()
        self.choose(order)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(orders.tick()['reminded'], 0)

    def test_staff_see_it_and_its_reference(self):
        card, sheba = self.place(), self.place()
        self.choose(sheba)
        orders.claim(sheba, {'reference': '۹۸۷۶۵۴', 'last4': '', 'time': '', 'note': ''})
        Order.objects.filter(pk=card.pk).update(provider_ref='CBC-AB12')
        owner = User.objects.create_user('owner', password='pw-123456!')
        owner.groups.add(Group.objects.get(name='Owners'))
        self.client.post('/api/panel/login/', {'username': 'owner', 'password': 'pw-123456!'}, content_type='application/json')
        rows = {r['code']: r for r in self.client.get('/api/panel/orders/?queue=all').json()['orders']}
        self.assertEqual((rows[sheba.code]['payment_method'], rows[sheba.code]['payment_codes']), ('sheba', ['۹۸۷۶۵۴']))
        self.assertEqual((rows[card.code]['payment_label'], rows[card.code]['payment_codes']), ('کارت‌به‌کارت', ['CBC-AB12']))
        self.assertEqual([r['code'] for r in self.client.get('/api/panel/orders/?q=CBC-AB12').json()['orders']], [card.code])
        # With cartbecart confirming cards, an unconfirmed Sheba order still needs staff.
        other = self.place()
        self.choose(other)
        with override_settings(PAYMENT_PROVIDER='cartbecart'):
            action = [r['code'] for r in self.client.get('/api/panel/orders/?queue=action').json()['orders']]
        self.assertIn(other.code, action)
        self.assertNotIn(card.code, action)

    def test_every_active_sheba_is_offered_the_orders_own_first(self):
        other = Sheba.objects.create(number=valid_sheba('0570022711517635897001'), holder='حسام منصوری',
                                     bank='بانک پاسارگاد', position=1)
        Sheba.objects.create(number=valid_sheba('0610000007001005596838'), holder='—', active=False, position=2)
        order = self.place()
        data = self.choose(order)
        self.assertEqual([s['number'] for s in data['shebas']], [self.sheba.number, other.number])
        # A Sheba moved first later doesn't change the order's own.
        Sheba.objects.filter(pk=other.pk).update(position=0)
        self.sheba.position = 5
        self.sheba.save()
        data = self.client.get(f'/api/orders/{order.token}/').json()
        self.assertEqual([s['number'] for s in data['shebas']], [self.sheba.number, other.number])

    def test_the_panel_shebas_are_checked(self):
        self.sign_in_owner()
        save = lambda body: self.client.post('/api/panel/shebas/', body, content_type='application/json').json()
        self.assertEqual(save({'number': 'IR12345', 'holder': ''})['fields'], {'number': 'sheba', 'holder': 'required'})
        number = valid_sheba('0570022711517635897001')
        rows = save({'number': number[2:], 'holder': 'حسام منصوری', 'bank': 'بانک پاسارگاد'})['shebas']
        self.assertEqual([(r['number'], r['position']) for r in rows], [(valid_sheba(), 0), (number, 1)])  # IR added
        self.assertEqual(len(save({'id': rows[1]['id'], 'delete': True})['shebas']), 1)


class ShebaMigrationTests(TransactionTestCase):
    """0011: Amir's two Shebas replace the store settings' one (his own, dropped)."""

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([('shop', target)])
        return executor.loader.project_state([('shop', target)]).apps

    def test_replaces_the_one_sheba(self):
        apps = self.migrate('0010_sheba')
        apps.get_model('shop', 'StoreSettings').objects.update_or_create(
            pk=1, defaults={'sheba': valid_sheba(), 'sheba_holder': 'مریم', 'sheba_bank': 'بانک ملت'})
        apps = self.migrate('0011_shebas')
        rows = list(apps.get_model('shop', 'Sheba').objects.values_list('number', 'holder', 'bank'))
        self.assertEqual(rows, [('IR970570022711517635897001', 'حسام منصوری', 'بانک پاسارگاد'),
                                ('IR220610000007001005596838', 'محمدسالار کبیری', 'بانک شهر')])


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

    def test_forwarder_alert_once(self):
        for _ in range(2):
            order = self.place()
            Order.objects.filter(pk=order.pk).update(status=Order.Status.EXPIRED)
        with override_settings(PAYMENT_PROVIDER='cartbecart'):
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



@override_settings(PAYMENT_PROVIDER='cartbecart', CARTBECART_API_URL='https://api.cartbecart.com',
                   CARTBECART_API_KEY='cb_test', CARTBECART_WEBHOOK_SECRET='whsec_test')
class CartbecartTests(Base):
    """cartbecart's API is faked with the answers its docs show; webhooks are signed the way theirs are."""
    CARD = '6037991234567893'

    def fake_api(self, *, status='pending', error=None, unique_extra=437, statuses=None):
        """Patches urlopen: create order, the public pay page, an order's status and shop-config. Each order
        registered in one call gets its own token and code (kJ8s-2Qa, kJ8s-2Qa2, …); statuses: token → status."""
        from urllib.parse import urlparse
        self.calls = []
        expires = (timezone.now() + timedelta(minutes=30)).isoformat()

        def urlopen(request, timeout):
            body = json.loads(request.data) if request.data else None
            path = urlparse(request.full_url).path
            self.calls.append({'method': request.get_method(), 'path': path, 'key': request.get_header('X-api-key'), 'body': body})
            if error is not None:
                raise error
            if path == '/api/v1/public/orders':
                n = sum(1 for c in self.calls if c['path'] == path)
                suffix = '' if n == 1 else str(n)
                answer = {'order_id': '3f2a9c1e', 'order_code': f'CBC-X7KQ{suffix}', 'payment_token': f'kJ8s-2Qa{suffix}',
                          'payment_url': f'https://cartbecart.com/pay/kJ8s-2Qa{suffix}',
                          'unique_amount': body['amount'] + unique_extra + n - 1, 'expires_at': expires}
            elif path.startswith('/api/v1/pay/'):
                answer = {'order_code': 'CBC-X7KQ', 'card_number': self.CARD, 'card_owner': 'سارا محمدی',
                          'status': 'pending', 'expires_at': expires}
            elif path.startswith('/api/v1/public/orders/'):
                answer = {'status': (statuses or {}).get(path.rsplit('/', 1)[1], status)}
            else:
                answer = {'grace_minutes': 60}
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(answer).encode()
            return response
        return mock.patch('shop.payments.urllib.request.urlopen', side_effect=urlopen)

    def refusal(self, status, detail):
        import urllib.error
        return urllib.error.HTTPError('https://api.cartbecart.com/', status, 'x', {},
                                      io.BytesIO(json.dumps({'detail': detail}).encode()))

    def send(self, body, secret='whsec_test', timestamp=None):
        import hashlib
        import hmac
        import time
        body = body.encode() if isinstance(body, str) else body
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        signature = 'sha256=' + hmac.new(secret.encode(), f'{timestamp}.'.encode() + body, hashlib.sha256).hexdigest()
        return self.client.post('/api/payments/cartbecart/', body, content_type='application/json',
                                HTTP_X_CBC_TIMESTAMP=timestamp, HTTP_X_CBC_SIGNATURE=signature)

    def event(self, order, kind, event_id='e1', reason=None, **changes):
        return json.dumps({
            'event': kind, 'event_id': event_id, 'occurred_at': timezone.now().isoformat(), 'reason': reason,
            'is_final': kind != 'order.needs_review',
            'order': {'order_code': order.provider_ref, 'merchant_order_id': order.code, 'status': kind.split('.')[1],
                      'base_amount': order.amount_rial - order.offset_rial, 'unique_amount': order.amount_rial,
                      'paid_at': None, 'expires_at': order.expires_at.isoformat(), 'created_at': order.created_at.isoformat(),
                      **changes},
        })

    def placed(self):
        with self.fake_api():
            return self.place()

    def test_checkout_registers_the_order_and_shows_their_card_and_amount(self):
        with self.fake_api():
            order = self.place()
        create, page = self.calls
        base = self.product.price_rial + order.shipping_rial
        self.assertEqual((create['method'], create['path'], create['key']), ('POST', '/api/v1/public/orders', 'cb_test'))
        self.assertEqual(create['body'], {'amount': base, 'callback_url': orders.link(order), 'merchant_order_id': order.code,
                                          'customer_name': ADDRESS['name'], 'customer_phone': ADDRESS['phone']})
        self.assertEqual((page['path'], page['key']), ('/api/v1/pay/kJ8s-2Qa', None))  # their public endpoint, no key
        self.assertEqual((order.amount_rial, order.offset_rial), (base + 437, 437))
        self.assertEqual((order.card_number, order.card_holder, order.card_bank), (self.CARD, 'سارا محمدی', 'بانک ملی'))
        self.assertEqual((order.provider_token, order.provider_ref), ('kJ8s-2Qa', 'CBC-X7KQ'))
        self.assertAlmostEqual((order.expires_at - timezone.now()).total_seconds(), 1800, delta=60)
        text = SmsLog.objects.get(kind='order_created').text
        self.assertIn(f'{persian.rial(order.amount_rial)} ریال', text)
        self.assertIn('۳۰ دقیقه', text)
        data = self.client.get(f'/api/orders/{order.token}/').json()
        self.assertEqual((data['pay_in_rial'], data['amount_rial'], data['card']['number']), (True, base + 437, self.CARD))

    def test_a_card_in_the_panel_lends_its_bank_name(self):
        Card.objects.create(bank='بانک آزمایش', number=self.CARD, holder='سارا محمدی')
        self.assertEqual(self.placed().card_bank, 'بانک آزمایش')

    def test_refusal_keeps_the_sms_code_and_tells_the_owner_once(self):
        code = self.otp()
        with self.fake_api(error=self.refusal(422, 'کارت پیش‌فرض فعالی وجود ندارد')):
            for _ in range(2):
                response = self.client.post('/api/orders/', {**ADDRESS, 'code': code}, content_type='application/json')
                self.assertEqual(response.json()['error'], 'payment_down')
        self.assertFalse(Order.objects.exists())
        self.assertEqual(SmsLog.objects.filter(kind='owner_payment_down', phone='09350000000').count(), 1)
        self.assertIn('422', SmsLog.objects.get(kind='owner_payment_down').text)
        with self.fake_api():  # fixed on their side: the same code still works
            response = self.client.post('/api/orders/', {**ADDRESS, 'code': code}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_unexpected_answer_is_refused(self):
        with self.fake_api(unique_extra=5000), self.assertRaises(OrderError) as ctx:
            self.place()
        self.assertEqual(ctx.exception.code, 'payment_down')

    def test_only_their_signature_gets_in(self):
        order = self.placed()
        body = self.event(order, 'order.paid')
        self.assertEqual(self.client.post('/api/payments/cartbecart/', body, content_type='application/json').status_code, 401)
        self.assertEqual(self.send(body, secret='guess').status_code, 401)
        self.assertEqual(self.send(body, timestamp=int(timezone.now().timestamp()) - 3600).status_code, 401)  # replayed
        with override_settings(PAYMENT_PROVIDER='manual'):
            self.assertEqual(self.send(body).status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'awaiting_payment')

    def test_paid_once_however_often_they_send_it(self):
        order = self.placed()
        response = self.send(self.event(order, 'order.paid'))
        self.assertEqual((response.status_code, response.json()['outcome']), (200, 'matched'))
        order.refresh_from_db()
        self.assertEqual((order.status, order.paid_via), ('paid', 'auto'))
        self.assertEqual(self.send(self.event(order, 'order.paid')).json()['outcome'], 'repeat')
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.assertEqual(SmsLog.objects.filter(kind='paid').count(), 1)
        self.assertTrue(SmsLog.objects.filter(kind='owner_new_order').exists())

    def test_paid_in_their_grace_hour_after_our_countdown(self):
        order = self.placed()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=20))
        self.assertEqual(self.client.get(f'/api/orders/{order.token}/').json()['status'], 'expired')
        self.assertEqual(self.send(self.event(order, 'order.paid')).json()['outcome'], 'matched')
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_needs_review_then_rejected_in_their_dashboard(self):
        order = self.placed()
        self.assertEqual(self.send(self.event(order, 'order.needs_review')).json()['outcome'], 'review')
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')
        self.assertTrue(SmsLog.objects.filter(kind='owner_review').exists())
        response = self.send(self.event(order, 'order.expired', 'e2', reason='rejected_by_merchant'))
        self.assertEqual(response.json()['outcome'], 'rejected')
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertTrue(SmsLog.objects.filter(kind='payment_not_found').exists())

    def test_timeout_and_cancel(self):
        order = self.placed()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=95))
        self.assertEqual(self.send(self.event(order, 'order.expired', reason='timeout')).json()['outcome'], 'expired')
        other = self.placed()
        self.assertEqual(self.send(self.event(other, 'order.cancelled', 'e2')).json()['outcome'], 'cancelled')
        other.refresh_from_db()
        self.assertEqual(other.status, 'cancelled')

    def test_events_for_other_orders(self):
        order = self.placed()
        test = json.loads(self.event(order, 'order.paid', 'e1'))
        test['order']['merchant_order_id'] = 'TEST-1A2B3C'
        self.assertEqual(self.send(json.dumps(test)).json()['outcome'], 'test')
        self.assertEqual(self.send(self.event(order, 'order.paid', 'e2', unique_amount=order.amount_rial + 1)).json()['outcome'],
                         'mismatch')
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')
        self.assertEqual(self.send(b'not json').json()['outcome'], 'unparsed')

    def test_status_check_catches_a_missed_webhook(self):
        order = self.placed()
        with self.fake_api(status='paid'):
            self.assertEqual(orders.sync_cartbecart(), 1)
            self.assertEqual(orders.sync_cartbecart(), 0)  # not asked again within SYNC_EVERY
        self.assertEqual([(c['path'], c['key']) for c in self.calls], [('/api/v1/public/orders/kJ8s-2Qa', 'cb_test')])
        order.refresh_from_db()
        self.assertEqual((order.status, order.paid_via), ('paid', 'auto'))

    def test_status_check_of_an_order_already_in_review_adds_nothing(self):
        from django.core.cache import cache
        order = self.placed()
        Order.objects.filter(pk=order.pk).update(status=Order.Status.REVIEW)
        before = AuditLog.objects.count()
        with self.fake_api(status='needs_review'):
            for _ in range(3):
                cache.clear()  # as if SYNC_EVERY had passed
                self.assertEqual(orders.sync_cartbecart(), 0)
        self.assertEqual(AuditLog.objects.count(), before)

    def test_paid_by_card_after_opening_the_sheba_tab_counts_as_card(self):
        order = self.placed()  # migration 0011's Shebas are there
        orders.choose_sheba(order)
        self.assertEqual(self.send(self.event(order, 'order.paid')).json()['outcome'], 'matched')
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment_method), ('paid', 'card'))

    def test_every_active_card_is_offered_the_order_own_first(self):
        Card.objects.create(bank='بانک سامان', number='6219861477558679', holder='بهراد بختیاری', auto=True)
        Card.objects.create(bank='بانک تجارت', number='5859831000001836', holder='امیرمحمد جزایری', active=False)
        order = self.placed()
        cards = self.client.get(f'/api/orders/{order.token}/').json()['cards']
        self.assertEqual(cards[0], {'bank': 'بانک ملی', 'number': self.CARD, 'holder': 'سارا محمدی', 'instant': True})
        Card.objects.create(bank='بانک شهر', number='5047061136794142', holder='محمدسالار کبیری')
        cards = self.client.get(f'/api/orders/{order.token}/').json()['cards']
        # Its bank SMS reach cartbecart, or not (checked by staff); not the inactive one, nor seed_store's sample.
        self.assertEqual({c['number']: c['instant'] for c in cards[1:]},
                         {'6219861477558679': True, '5047061136794142': False})

    # ── Over the bank's cap: paid in several transfers ──

    def split_placed(self):
        """A 16.5M-toman order (the two-zipper bag's price): 11.5M + 5M with the 15M cap."""
        self.product.price_rial = 165_000_000
        self.product.save()
        with self.fake_api():
            return self.place()

    def transfer_event(self, transfer, kind, event_id='t1', reason=None, **changes):
        return json.dumps({
            'event': kind, 'event_id': event_id, 'occurred_at': timezone.now().isoformat(), 'reason': reason,
            'is_final': kind != 'order.needs_review',
            'order': {'order_code': transfer.provider_ref, 'merchant_order_id': transfer.merchant_code,
                      'status': kind.split('.')[1], 'base_amount': transfer.amount_rial - transfer.offset_rial,
                      'unique_amount': transfer.amount_rial, 'paid_at': None, 'expires_at': transfer.expires_at.isoformat(),
                      'created_at': timezone.now().isoformat(), **changes},
        })

    def test_over_the_cap_each_transfer_is_registered(self):
        order = self.split_placed()
        creates = [c for c in self.calls if c['path'] == '/api/v1/public/orders']
        self.assertEqual([(c['body']['merchant_order_id'], c['body']['amount']) for c in creates],
                         [(f'{order.code}-1', 115_000_000), (f'{order.code}-2', 50_000_000)])
        first, second = order.transfers.all()
        self.assertEqual((first.amount_rial, first.offset_rial, first.provider_token, first.provider_ref),
                         (115_000_437, 437, 'kJ8s-2Qa', 'CBC-X7KQ'))
        self.assertEqual((second.amount_rial, second.provider_token, second.provider_ref), (50_000_438, 'kJ8s-2Qa2', 'CBC-X7KQ2'))
        self.assertEqual((order.amount_rial, order.offset_rial, order.provider_token), (165_000_875, 875, ''))
        self.assertEqual(second.card_number, self.CARD)
        text = SmsLog.objects.get(kind='order_created').text
        self.assertIn(f'{persian.rial(115_000_437)} ریال و {persian.rial(50_000_438)} ریال (در ۲ واریز جدا)', text)
        data = self.client.get(f'/api/orders/{order.token}/').json()
        self.assertTrue(data['pay_in_rial'])
        self.assertEqual([(t['amount_rial'], t['paid'], t['card']['number']) for t in data['transfers']],
                         [(115_000_437, False, self.CARD), (50_000_438, False, self.CARD)])

    def test_paid_once_every_transfer_has_arrived(self):
        order = self.split_placed()
        first, second = order.transfers.all()
        self.assertEqual(self.send(self.transfer_event(first, 'order.paid', 't1')).json()['outcome'], 'part')
        order.refresh_from_db()
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertFalse(SmsLog.objects.filter(kind='paid').exists())
        self.assertEqual([t['paid'] for t in self.client.get(f'/api/orders/{order.token}/').json()['transfers']], [True, False])
        self.assertEqual(self.send(self.transfer_event(first, 'order.paid', 't1')).json()['outcome'], 'repeat')
        self.assertEqual(self.send(self.transfer_event(second, 'order.paid', 't2')).json()['outcome'], 'matched')
        order.refresh_from_db()
        self.assertEqual((order.status, order.paid_via), ('paid', 'auto'))
        self.assertEqual(SmsLog.objects.filter(kind='paid').count(), 1)

    def test_some_transfers_when_the_window_ends_go_to_review_and_the_rest_still_pays(self):
        order = self.split_placed()
        first, second = order.transfers.all()
        self.send(self.transfer_event(first, 'order.paid', 't1'))
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(f'/api/orders/{order.token}/').json()['status'], 'needs_review')
        self.assertTrue(SmsLog.objects.filter(kind='owner_review').exists())
        self.assertEqual(self.send(self.transfer_event(second, 'order.paid', 't2')).json()['outcome'], 'matched')
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_one_arriving_alone_after_the_window_goes_to_review(self):
        order = self.split_placed()
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now() - timedelta(minutes=20))
        self.assertEqual(self.send(self.transfer_event(order.transfers.last(), 'order.paid')).json()['outcome'], 'part')
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')

    def test_a_transfer_refused_after_another_arrived_goes_to_review(self):
        order = self.split_placed()
        first, second = order.transfers.all()
        self.send(self.transfer_event(first, 'order.paid', 't1'))
        outcome = self.send(self.transfer_event(second, 'order.expired', 't2', reason='rejected_by_merchant')).json()['outcome']
        self.assertEqual(outcome, 'review')
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')
        self.assertFalse(SmsLog.objects.filter(kind='payment_not_found').exists())  # money came: no "not found"

    def test_a_transfer_with_another_amount_is_a_mismatch(self):
        order = self.split_placed()
        body = self.transfer_event(order.transfers.first(), 'order.paid', unique_amount=1)
        self.assertEqual(self.send(body).json()['outcome'], 'mismatch')
        order.refresh_from_db()
        self.assertEqual(order.status, 'needs_review')

    def test_status_check_asks_about_each_missing_transfer(self):
        from django.core.cache import cache
        order = self.split_placed()
        with self.fake_api(statuses={'kJ8s-2Qa': 'paid'}):
            self.assertEqual(orders.sync_cartbecart(), 1)
        self.assertEqual([c['path'] for c in self.calls], ['/api/v1/public/orders/kJ8s-2Qa', '/api/v1/public/orders/kJ8s-2Qa2'])
        cache.clear()  # as if SYNC_EVERY had passed
        with self.fake_api(status='paid'):
            self.assertEqual(orders.sync_cartbecart(), 1)
        self.assertEqual([c['path'] for c in self.calls], ['/api/v1/public/orders/kJ8s-2Qa2'])  # the one still missing
        order.refresh_from_db()
        self.assertEqual((order.status, order.paid_via), ('paid', 'auto'))
        self.assertEqual(PaymentEvent.objects.filter(order=order).count(), 2)

    def test_home_shows_the_sample_in_rials(self):
        from django.core.cache import cache
        cache.clear()
        page = self.client.get('/').content.decode()
        self.assertIn('چند ریال برای شناختن واریز', page)

    def test_cartbecart_check(self):
        out = io.StringIO()
        with self.fake_api():
            call_command('cartbecart_check', '--test', '5000', stdout=out)
        self.assertIn('grace_minutes=60', out.getvalue())
        self.assertIn('/api/payments/cartbecart/', out.getvalue())
        self.assertIn(persian.rial(50_437), out.getvalue())
        create = self.calls[1]
        self.assertTrue(create['body']['merchant_order_id'].startswith('TEST-'))
        self.assertEqual(create['body']['amount'], 50_000)
        # They refuse an empty customer_phone (seen live, 2026-10-24): no buyer, so none is sent.
        self.assertNotIn('customer_phone', create['body'])
        self.assertNotIn('customer_name', create['body'])


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

    def test_cards_are_offered_and_marked_automatic(self):
        self.user('Owners')
        card = Card.objects.first()
        data = self.client.post('/api/panel/cards/', {'id': card.pk, 'bank': card.bank, 'number': card.number,
                                                      'holder': card.holder, 'active': True, 'auto': True},
                                content_type='application/json').json()
        self.assertTrue(data['cards'][0]['auto'])
        Card.objects.create(bank='بانک سامان', number='6219861477558679', holder='بهراد بختیاری')
        order = self.place()
        cards = self.client.get(f'/api/orders/{order.token}/').json()['cards']
        self.assertEqual(len(cards), 2)
        self.assertEqual({c['instant'] for c in cards}, {False})  # without cartbecart staff confirm every one

    def test_transfer_cap_is_off_or_at_least_ten_million(self):
        self.user('Owners')
        save = lambda rial: self.client.post('/api/panel/settings/', {'store': {'transfer_limit_rial': rial}},
                                             content_type='application/json').json()
        self.assertEqual(save(50_000_000)['fields'], {'transfer_limit_rial': 'number'})  # 5M toman: too small
        self.assertEqual(save(0)['store']['transfer_limit_rial'], 0)
        self.assertEqual(save(120_000_000)['store']['transfer_limit_rial'], 120_000_000)

    def test_order_with_transfers_in_the_panel(self):
        self.product.price_rial = 165_000_000
        self.product.save()
        order = self.place()
        self.user('Owners')
        data = self.client.get(f'/api/panel/orders/{order.pk}/').json()
        self.assertEqual([t['position'] for t in data['transfers']], [1, 2])


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'test-default'},
    'pages': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'test-pages'},
})
class PageCacheTests(Base):
    """The home page comes from the cache until something it shows is saved."""

    def setUp(self):
        super().setUp()
        from django.core.cache import caches
        caches['pages'].clear()

    def test_cached_until_the_product_is_saved(self):
        product = self.product
        self.client.get('/')
        Product.objects.filter(pk=product.pk).update(name='نام بی‌خبر')  # no save signal: still cached
        self.assertNotIn('نام بی‌خبر', self.client.get('/').content.decode())
        product.name = 'نام تازه'
        product.save()  # a save empties the cache
        self.assertIn('نام تازه', self.client.get('/').content.decode())


class ColorTests(Base):
    """One colour on show: nobody is asked and orders get it. More: the buyer must pick a shown one in stock."""

    otp = ApiTests.otp

    def setUp(self):
        super().setUp()
        self.black = self.product.colors.get()
        self.blue = self.product.colors.create(name='سرمه‌ای', swatch='#1f2a44', shown=False)

    def test_single_colour_is_given_to_every_order(self):
        self.assertEqual(self.place().color_name, 'مشکی')
        self.assertEqual(self.client.get('/checkout/').status_code, 200)

    def test_a_second_shown_colour_must_be_picked_before_the_code_is_used(self):
        self.blue.shown = True
        self.blue.save()
        code = self.otp()
        response = self.client.post('/api/orders/', {**ADDRESS, 'code': code}, content_type='application/json')
        self.assertEqual(response.json()['error'], 'color')
        response = self.client.post('/api/orders/', {**ADDRESS, 'code': code, 'color': self.blue.pk},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)  # the code still worked
        self.assertEqual(Order.objects.get().color_name, 'سرمه‌ای')

    def test_hidden_or_sold_out_colours_cannot_be_bought(self):
        self.blue.shown = True
        self.blue.available = False
        self.blue.save()
        with self.assertRaises(OrderError) as raised:
            orders.pick_color(self.product, self.blue.pk)
        self.assertEqual(raised.exception.code, 'color_unavailable')
        self.blue.shown = False
        self.blue.save()
        with self.assertRaises(OrderError):
            orders.pick_color(self.product, self.blue.pk)

    def test_panel_adds_and_retires_colours(self):
        user = User.objects.create_user('owner', password='pw-123456!')
        user.groups.add(Group.objects.get(name='Owners'))
        self.client.post('/api/panel/login/', {'username': 'owner', 'password': 'pw-123456!'}, content_type='application/json')
        response = self.client.post('/api/panel/colors/', {'name': 'گردویی', 'swatch': '#6B4A2F'}, content_type='application/json')
        self.assertEqual([c['name'] for c in response.json()['colors']], ['مشکی', 'سرمه‌ای', 'گردویی'])
        response = self.client.post('/api/panel/colors/', {'name': 'بد', 'swatch': 'blue'}, content_type='application/json')
        self.assertEqual(response.json()['fields'], {'swatch': 'swatch'})
        orders.place(self.product, ADDRESS, color=self.black)  # a black order: deleting black only hides it
        self.client.post('/api/panel/colors/', {'id': self.black.pk, 'delete': True}, content_type='application/json')
        self.black.refresh_from_db()
        self.assertFalse(self.black.shown)


class StartingColoursTests(TestCase):
    def test_a_new_store_sells_black_and_brown_with_photos(self):
        call_command('seed_store', stdout=io.StringIO())
        product = Product.objects.get(slug='alpha')
        self.assertEqual([(c.name, c.photo) for c in product.colors.all()], [
            ('مشکی', 'images/colors/black.webp'), ('قهوه‌ای', 'images/colors/brown.webp')])
        self.assertIn('ویوو', product.name)
        page = self.client.get('/checkout/').content.decode()
        self.assertEqual(page.count('data-color-photo='), 4)  # each model's bag in each colour
        home = self.client.get('/').content.decode()
        self.assertEqual(home.count('data-color-picker'), 1)  # in the hero (the 3D bag's went with it)
        self.assertIn('"brand": {"@type": "Brand", "name": "WiWU"}', home)


class SecondModelTests(Base):
    """The two-zipper bag (seed_store's phantom-pro, 16,500,000 toman): off the site while it has no price, else its
    own section, its pictures, checkout and orders; edited in the panel beside the Alpha."""

    otp = ApiTests.otp

    def setUp(self):
        super().setUp()
        self.phantom = Product.objects.get(slug='phantom-pro')

    def priced(self):
        self.phantom.price_rial = 150_000_000
        self.phantom.save()

    def test_it_starts_at_its_price(self):
        self.assertEqual(self.phantom.price_rial, 165_000_000)
        self.assertEqual([c.name for c in self.phantom.colors.all()], ['مشکی', 'قهوه‌ای'])

    def test_the_parts_section_pictures_every_bag_instead_of_the_3d(self):
        home = self.client.get('/').content.decode()
        self.assertNotIn('bag3d', home)
        self.assertNotIn('data-bag-stage', home)
        black = self.product.colors.get()  # (Base keeps only the Alpha's black)
        parts = home[home.index('id="parts"'):home.index('id="try"')]
        self.assertIn(f'href="/checkout/?color={black.pk}"', parts)
        for colour in self.phantom.colors.all():
            self.assertIn(f'href="/checkout/?product=phantom-pro&amp;color={colour.pk}"', parts)
        self.assertEqual(parts.count('<img '), 3)
        self.assertIn('۱۶٬۵۰۰٬۰۰۰', parts)

    def test_the_closing_cards_and_the_hero_show_both_versions_of_each_colour(self):
        self.product.colors.create(name='قهوه‌ای', swatch='#463930', photo='images/colors/brown.webp', position=1)
        home = self.client.get('/').content.decode()
        closing = home[home.index('id="colors"'):]
        self.assertIn('images/colors/duo-black.webp', closing)
        self.assertIn('images/colors/duo-brown.webp', closing)
        self.assertIn('تک‌زیپ <span class="font-semibold text-ink-soft">۱۴٬۱۰۰٬۰۰۰</span>', closing)
        self.assertIn('دو زیپ <span class="font-semibold text-ink-soft">۱۶٬۵۰۰٬۰۰۰</span>', closing)
        hero = home[:home.index('id="parts"')]
        self.assertIn('bag-black-duo', hero)
        self.assertIn('bag-brown-duo', hero)

    def test_without_a_price_it_is_nowhere_on_the_site(self):
        self.phantom.price_rial = 0
        self.phantom.save()
        home = self.client.get('/').content.decode()
        self.assertNotIn('id="phantom-pro"', home)
        self.assertNotIn('phantom-black', home)
        checkout = self.client.get('/checkout/?product=phantom-pro').content.decode()
        self.assertIn('کیف دستی ویوو آلفا', checkout)
        self.assertNotIn('فانتوم', checkout)
        code = self.otp()
        response = self.client.post('/api/orders/', {**ADDRESS, 'code': code, 'product': 'phantom-pro'},
                                    content_type='application/json')
        self.assertEqual(response.json()['error'], 'unavailable')

    def test_with_a_price_it_has_a_section_a_checkout_and_orders(self):
        self.priced()
        brown = self.phantom.colors.get(name='قهوه‌ای')
        home = self.client.get('/').content.decode()
        self.assertIn('id="phantom-pro"', home)
        self.assertIn('۱۵٬۰۰۰٬۰۰۰', home)
        self.assertIn(f'?product=phantom-pro&amp;color={brown.pk}', home)
        checkout = self.client.get('/checkout/?product=phantom-pro').content.decode()
        # Both models in the summary, the one asked for showing; the form starts from it and offers both.
        self.assertIn('<div data-model-summary="phantom-pro" class=', checkout)
        self.assertIn('<div data-model-summary="alpha" hidden', checkout)
        island = json.loads(re.search(r'id="island-data"[^>]*>(.*?)</script>', checkout, re.S).group(1))
        self.assertEqual((island['start'], [m['short'] for m in island['models']]), ('phantom-pro', ['تک‌زیپ', 'دو زیپ']))
        self.assertEqual([c['name'] for c in island['models'][1]['colors']], ['مشکی', 'قهوه‌ای'])
        code = self.otp()
        response = self.client.post('/api/orders/', {**ADDRESS, 'code': code, 'product': 'phantom-pro', 'color': brown.pk},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get()
        self.assertEqual((order.product, order.unit_price_rial, order.color_name), (self.phantom, 150_000_000, 'قهوه‌ای'))

    def test_the_panel_edits_either_model(self):
        user = User.objects.create_user('owner', password='pw-123456!')
        user.groups.add(Group.objects.get(name='Owners'))
        self.client.post('/api/panel/login/', {'username': 'owner', 'password': 'pw-123456!'}, content_type='application/json')
        data = self.client.get('/api/panel/settings/?product=phantom-pro').json()
        self.assertEqual([p['slug'] for p in data['products']], ['alpha', 'phantom-pro'])
        self.assertEqual(data['product']['slug'], 'phantom-pro')
        colours = self.client.get('/api/panel/colors/?product=phantom-pro').json()['colors']
        self.assertEqual([c['name'] for c in colours], ['مشکی', 'قهوه‌ای'])
        # No price yet is fine for it, never for the Alpha.
        response = self.client.post('/api/panel/settings/', {'product': {**data['product'], 'subtitle': 'دو زیپ'}},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.post('/api/panel/settings/', {'product': {'slug': 'alpha', 'price_rial': 0}},
                                    content_type='application/json')
        self.assertEqual(response.json()['fields'], {'price_rial': 'number'})
        response = self.client.post('/api/panel/settings/', {'product': {'slug': 'phantom-pro', 'price_rial': 150_000_000}},
                                    content_type='application/json')
        self.assertTrue(response.json()['products'][1]['on_sale'])
        self.phantom.refresh_from_db()
        self.assertEqual((self.phantom.price_rial, self.phantom.subtitle), (150_000_000, 'دو زیپ'))
        self.assertEqual(self.product.price_rial, Product.objects.get(slug='alpha').price_rial)  # the Alpha untouched


class AssetVersionTests(TestCase):
    def test_production_addresses_carry_the_files_content_hash(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from .templatetags import vite
        with tempfile.TemporaryDirectory() as build:
            (Path(build) / '.vite').mkdir()
            (Path(build) / 'images').mkdir()
            (Path(build) / 'images' / 'front.webp').write_bytes(b'new photo')
            vite._versions.clear()
            with override_settings(VITE_DEV_SERVER='', VITE_ASSETS_URL='/', VITE_MANIFEST=Path(build) / '.vite' / 'manifest.json'):
                expected = hashlib.md5(b'new photo').hexdigest()[:8]
                self.assertEqual(vite.asset('images/front.webp'), f'/images/front.webp?v={expected}')
                self.assertEqual(vite.asset('images/missing.webp'), '/images/missing.webp')
            vite._versions.clear()
            with override_settings(VITE_DEV_SERVER='http://127.0.0.1:5180'):
                self.assertEqual(vite.asset('images/front.webp'), 'http://127.0.0.1:5180/images/front.webp')
