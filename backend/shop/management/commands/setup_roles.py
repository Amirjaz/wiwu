"""Creates (or brings up to date) the roles as Django groups. Safe to run on every deploy.

    python manage.py setup_roles

Give a person a role in Django admin → Users: add them to a group. Superusers can do everything."""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

STAFF = ['view_order', 'change_order', 'view_returnrequest', 'change_returnrequest']
ROLES = {
    # Orders and returns: prepare, ship, deliver, receive returns.
    'Staff': STAFF,
    # Also: approve/reject payments and cancel, record refunds, edit the store.
    'Owners': STAFF + ['approve_payment', 'refund', 'view_storesettings', 'change_storesettings'],
}


class Command(BaseCommand):
    help = 'Create or update the roles (Django groups).'

    def handle(self, *args, **options):
        for role, codenames in ROLES.items():
            permissions = [Permission.objects.get(content_type__app_label='shop', codename=c) for c in codenames]
            group, created = Group.objects.get_or_create(name=role)
            group.permissions.set(permissions)
            self.stdout.write(f'{"Created" if created else "Updated"} role "{role}" ({len(permissions)} permissions)')
