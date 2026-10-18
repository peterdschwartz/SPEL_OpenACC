import textwrap

from spel.scripts import interfaces


def test_interface_procedures_are_from_that_interface_only(tmp_path, monkeypatch):
    # subgridAveMod: `call c2g(...)` resolved to p2g_1d_gpu (same argument types)
    # when every interface of the module contributed its procedures
    src = tmp_path / "main" / "subgridAveMod.F90"  # grep -r prints file names
    src.parent.mkdir()
    src.write_text(textwrap.dedent("""\
        module subgridAveMod
          interface p2g
             module procedure p2g_1d
             module procedure p2g_1d_gpu
          end interface
          interface c2g
             module procedure c2g_1d
             module procedure c2g_1d_gpu
          end interface
          interface c2g_extra
             module procedure c2g_extra_1d
          end interface
        end module subgridAveMod
        """))
    monkeypatch.setattr(interfaces, "ELM_SRC", f"{tmp_path}/")
    monkeypatch.setattr(interfaces, "_interface_procs_cache", {})
    assert interfaces.get_interface_procedures("c2g") == [
        "subgridavemod::c2g_1d",
        "subgridavemod::c2g_1d_gpu",
    ]
