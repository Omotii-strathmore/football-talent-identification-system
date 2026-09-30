"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()


def _migrate_on_start():
    """Bring the database up to date when the live server starts.

    Render's free plan has no shell, and a missed migration makes pages crash with
    "Internal Server Error". Applying pending migrations at start-up means every
    deploy updates the database by itself. Set MIGRATE_ON_START=False to turn this off.
    """
    if os.environ.get('MIGRATE_ON_START', 'True') != 'True':
        return
    from django.conf import settings
    from django.core.management import call_command

    if settings.DEBUG:
        return
    try:
        call_command('migrate', interactive=False, verbosity=1)
    except Exception:
        logging.getLogger(__name__).exception('Automatic migration on start-up failed')


_migrate_on_start()
