from django.test import TestCase

from .models import SubroutineActiveGlobalVars


class YourModelTests(TestCase):
    def setUp(self):
        # Set up data for the whole TestCase
        SubroutineActiveGlobalVars

    def test_your_model(self):
        # Fetch the object you created in setUp
        obj = SubroutineActiveGlobalVars.objects.get(field1="value1")
        self.assertEqual(obj.field2, "value2")
