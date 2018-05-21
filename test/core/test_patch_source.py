from django.test import TestCase
from squad.core.models import PatchSource
from squad.core.plugins import Plugin


class TestPatchSource(TestCase):

    def test_get_implementation(self):
        patch_source = PatchSource(implementation='example')
        self.assertIsInstance(patch_source.get_implementation(), Plugin)
