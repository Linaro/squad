from django.db import models


class VersionField(models.TextField):

    def db_type(self, connection):
        if connection.vendor == 'postgresql':
            return 'debversion'
        else:
            return super(VersionField, self).db_type(connection)
