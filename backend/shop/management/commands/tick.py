"""Every minute (deploy/systemd/purseshop-tick.timer): payment reminders, expiry, forwarder check, and with
cartbecart a status check of open orders in case a webhook didn't arrive."""
from django.core.management.base import BaseCommand

from shop import orders, payments


class Command(BaseCommand):
    help = 'Send payment reminders, expire unpaid orders, check the SMS forwarder and cartbecart.'

    def handle(self, *args, **options):
        done = orders.tick()
        if done['reminded'] or done['expired'] or done['alerted']:
            self.stdout.write(f'reminded {done["reminded"]}, expired {done["expired"]}, alerted {done["alerted"]}')
        if payments.enabled():
            changed = orders.sync_cartbecart()
            if changed:
                self.stdout.write(f'cartbecart: {changed} orders changed by status check')
