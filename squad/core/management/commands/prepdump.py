from django.core.management.base import BaseCommand
from squad.core import models
import os


class Command(BaseCommand):

    def handle_subscriptions(self, collection):
        username = os.getenv('USER')
        email = '%s@localhost' % username
        for sub in collection:
            sub.email = email
            sub.save()

    def handle(self, *args, **options):
        self.handle_subscriptions(models.Subscription.objects.all())
        self.handle_subscriptions(models.AdminSubscription.objects.all())
