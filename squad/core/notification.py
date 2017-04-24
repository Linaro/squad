from django.db import models


from squad.core.models import ProjectStatus
from squad.core.comparison import TestComparison


class Notification(object):
    """
    Represents a notification about a project status change, that may or may
    not need to be sent.
    """

    def __init__(self, status):
        self.status = status

    @property
    def build(self):
        return self.status.build

    @property
    def previous_build(self):
        if self.status.previous:
            return self.status.previous.build

    __comparison__ = None

    @property
    def comparison(self):
        if self.__comparison__ is None:
            self.__comparison__ = TestComparison.compare_builds(
                self.previous_build,
                self.build,
            )
        return self.__comparison__

    @property
    def diff(self):
        return self.comparison.diff

    @property
    def must_be_sent(self):
        needed = self.build and self.previous_build and self.diff
        return bool(needed)
