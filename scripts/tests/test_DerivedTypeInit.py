import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import utilityFunctions as uf
from edit_files import get_filename_from_module, modify_file
from mod_config import E3SM_SRCROOT, scripts_dir


class DerivedTypeTests(unittest.TestCase):

    def type_bound_methods(self):
        fn = f"{scripts_dir}/tests/example_types.f90"
