import shutil
import textwrap

import pytest

from spel.scripts import edit_files


@pytest.mark.skipif(shutil.which("gfortran") is None, reason="needs gfortran -cpp")
def test_module_declarations_follow_the_preprocessor(tmp_path, monkeypatch):
    # SnowSnicarMod: ss_alb_bc1 is 2-D with MODAL_AER (SPEL's macros) and 1-D otherwise
    src = tmp_path / "SnicarLikeMod.F90"
    src.write_text(textwrap.dedent("""\
        module SnicarLikeMod
          implicit none
        #ifdef MODAL_AER
          real(r8) :: ss_alb_bc1 (numrad_snw, idx_bc_nclrds_max)
        #else
          real(r8) :: ss_alb_bc1 (numrad_snw)
        #endif
          real(r8) :: other (numrad_snw)
        contains
          subroutine noop()
          end subroutine noop
        end module SnicarLikeMod
        """))
    monkeypatch.setattr(edit_files, "spel_output_dir", tmp_path)
    _, mod_dict = edit_files.get_used_mods(str(src), [], True, {})
    gvars = mod_dict["snicarlikemod"].global_vars
    assert gvars["ss_alb_bc1"].dim == 2
    assert gvars["other"].dim == 1
