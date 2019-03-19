from django.core.management.base import BaseCommand

from squad.core.models import Group
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'PROJECT',
            help='Target project, on the form $group/$project',
        )

    def handle(self, *args, **options):
        groupname, projectname = options['PROJECT'].split('/')

        group, _ = Group.objects.get_or_create(slug=groupname, defaults={'name': groupname})
        project, _ = group.projects.get_or_create(slug=projectname, defaults={'name': projectname})
        user, _ = User.objects.get_or_create(username='%s-%s-submitter' % (groupname, projectname))
        group.add_admin(user)

        token, _ = Token.objects.get_or_create(user=user)
        print(token.key)
