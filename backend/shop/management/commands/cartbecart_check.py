"""Checks the cartbecart setup: the API key and plan, the webhook's signing key and the address to give
them. With --test, also registers a small test order (not a shop order) to pay from your own card; when
it's paid, the panel's Logs → payments shows it as a test, which proves the webhook works."""
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from shop import payments
from shop.persian import rial
from shop.sms import printable


class Command(BaseCommand):
    help = 'Check the cartbecart key, plan and webhook; --test [TOMAN] registers a test order to pay.'

    def add_arguments(self, parser):
        parser.add_argument('--test', nargs='?', const=10000, type=int, metavar='TOMAN',
                            help='register a test order of this many tomans (default 10,000) to pay yourself')

    def say(self, text):
        self.stdout.write(printable(text))

    def handle(self, *args, test=None, **options):
        self.say(f'PAYMENT_PROVIDER={settings.PAYMENT_PROVIDER}'
                 + ('' if payments.enabled() else '  (checkout doesn\'t use cartbecart until this is cartbecart)'))
        try:
            config = payments.shop_config()
        except payments.CartbecartError as exc:
            hint = {401: 'the API key is wrong', 403: 'no active subscription, a plan without API (needs Pro or Max), '
                    'or the monthly quota is used up'}.get(exc.status, '')
            raise CommandError(printable(f'cartbecart refused: {exc}' + (f' ({hint})' if hint else ''))) from None
        self.say('Key works. Their settings: ' + (', '.join(f'{k}={v}' for k, v in config.items()) if isinstance(config, dict) else str(config)))

        url = f'{settings.PUBLIC_URL}/api/payments/cartbecart/'
        self.say(f'Webhook address for their dashboard → Settings → Webhook: {url}')
        if not url.startswith('https://'):
            self.say('  They only send to https on port 443 with a public domain: set PUBLIC_URL to the real site.')
        self.say('Signing key (CARTBECART_WEBHOOK_SECRET): ' + ('set' if settings.CARTBECART_WEBHOOK_SECRET else
                 'NOT SET. Make one there with «ساخت کلید امضا»; until then they send no events.'))

        if test is not None:
            if test < 1000:
                raise CommandError('cartbecart takes 1,000 tomans at least')
            code = f'TEST-{secrets.token_hex(3).upper()}'
            try:
                reg = payments.create_order(code, test * 10, f'{settings.PUBLIC_URL}/')
            except payments.CartbecartError as exc:
                hint = ' (no active default card in their dashboard?)' if exc.status == 422 else ''
                raise CommandError(printable(f'Test order refused: {exc}{hint}')) from None
            until = timezone.localtime(reg['expires_at']).strftime('%H:%M')
            self.say(f'Test order {code} ({reg["ref"]}): pay exactly {rial(reg["amount_rial"])} rials '
                     f'to {reg["card_number"]} ({reg["card_holder"]}) by {until}.')
            self.say(f'Their pay page: {reg["payment_url"]}')
