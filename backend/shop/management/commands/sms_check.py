"""Checks the SMS setup: the Kavenegar key, its credit and which messages go how (sends nothing).
With a mobile number, also texts it a test code the way checkout does, and logs it like any SMS."""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop import jalali, persian, sms
from shop.models import SmsLog


class Command(BaseCommand):
    help = 'Check the Kavenegar key, credit and setup; with a mobile number, send it a test code.'

    def add_arguments(self, parser):
        parser.add_argument('phone', nargs='?', help='a mobile number to text a test code (12345) to')

    def say(self, text):
        self.stdout.write(sms.printable(text))

    def handle(self, *args, phone=None, **options):
        number = None
        if phone:
            number = persian.phone(phone)
            if not number:
                raise CommandError(f'{phone!r} is not an Iranian mobile number')

        self.say(f'SMS_BACKEND={settings.SMS_BACKEND}')
        if settings.SMS_BACKEND == 'kavenegar':
            self.kavenegar_setup()
        elif settings.SMS_BACKEND == 'console':
            self.say('SMS are printed here and logged, not sent.')

        if number:
            ok = sms.send('otp', number, code='12345')
            entry = SmsLog.objects.filter(phone=number, kind='otp').first()
            if not ok:
                raise CommandError(sms.printable(f'Test SMS to {number} failed: {entry.error}'))
            self.say(f'Test code sent to {number} ({entry.status}).')

    def kavenegar_setup(self):
        unknown = [k for k in settings.KAVENEGAR_TEMPLATES if k != 'all' and k not in sms.MESSAGES]
        if unknown:
            raise CommandError(f'KAVENEGAR_TEMPLATES has unknown kinds: {", ".join(unknown)}. '
                               f'They are: {", ".join(sms.MESSAGES)}')
        try:
            info = sms.kavenegar('account/info') or {}
        except Exception as exc:  # noqa: BLE001 — shown as is
            raise CommandError(sms.printable(f'Kavenegar: {exc}')) from None
        credit = int(info.get('remaincredit') or 0)
        line = f'Key works. Credit: {credit:,} rial ({credit // 10:,} toman)'
        if info.get('expiredate'):
            until = datetime.datetime.fromtimestamp(int(info['expiredate']), datetime.timezone.utc).date()
            line += f', account until {jalali.iso(until)} ({until})'
        self.say(line + '.')

        templates = [k for k in sms.MESSAGES if sms.uses_template(k)]
        plain = [k for k in sms.MESSAGES if not sms.uses_template(k)]
        if plain:
            self.say(f'Plain text from {settings.KAVENEGAR_SENDER or "the default line"}: {", ".join(plain)}')
        if templates:
            self.say('Templates (must be approved in the Kavenegar panel): '
                     + ', '.join(f'{k} → {sms.template_name(k)}' for k in templates))
