import unittest
from analyze_subroutines import Subroutine
import re 
import os

class SubroutineTests(unittest.TestCase):
    """
    Tests to exercise the Subroutine class methods.
    NOTE: Hardcoding answers may be difficult if E3SM version
          is changed. 
          Storing copy of files, may not allow testing of E3SM's directory structure.
          Sol'n:  store the commit hash the tests were validated against?
    """
    def test_SoilTemperature(self):
        import os
        sname = 'SoilTemperature'
        # Initilize Subroutine
        s = Subroutine(sname,calltree=['elm_drv']) 
        correct_filepath = "E3SM/components/elm/src/biogeophys/SoilTemperatureMod.F90"
        regex_fp = re.compile(f"({correct_filepath})$")
        self.assertRegex(s.filepath,regex_fp)

if __name__ == '__main__':
    unittest.main() 
