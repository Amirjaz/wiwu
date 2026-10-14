"""Every minute (deploy/systemd/purseshop-tick.timer): payment reminders, expiry, forwarder check."""
from django.core.management.base import BaseCommand

from shop import orders


class Command(BaseCommand):
    help = 'Send payment reminders, expire unpaid orders, check the SMS forwarder.'

    def handle(self, *args, **options):
        done = orders.tick()
        if done['reminded'] or done['expired'] or done['alerted']:
            self.stdout.write(f'reminded {done["reminded"]}, expired {done["expired"]}, alerted {done["alerted"]}')
