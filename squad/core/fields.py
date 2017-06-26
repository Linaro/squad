from django.db import models


class VersionField(models.TextField):
    """
    This class is not used, but has to stay here for migrations to work.
    """

    def db_type(self, connection):
        return super(VersionField, self).db_type(connection)
