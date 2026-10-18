import logging
from types import SimpleNamespace

from spel.scripts.analysis_cache import nested_filter_builders
from spel.scripts.fortran_parser.symbols import Origin
from spel.scripts.record_access import ArgBinding


def bind(caller, callee, ln, argn, dummy, actual):
    return ArgBinding(
        caller=caller, callee=callee, ln=ln, argn=argn, dummy=dummy, actual=actual, origin=Origin.GLOBAL
    )


def test_lake_snow_filter_built_inside_lakehydrology():
    lake, build, age = (
        "lakehydrologymod::lakehydrology",
        "snowhydrologymod::buildsnowfilter",
        "snowsnicarmod::snowage_grain",
    )
    arg = lambda typ="integer", intent="r": SimpleNamespace(type=typ, intent=intent)  # noqa: E731
    builder = SimpleNamespace(
        id=build,
        name="buildsnowfilter",
        sub_call_desc={},
        elmtype_access_summary={"col_pp%snl": SimpleNamespace(status="r")},
        arguments={
            "bounds": arg("bounds_type"),
            "num_nolakec": arg(),
            "filter_nolakec": arg(),
            "num_snowc": arg(intent="w"),
            "filter_snowc": arg(intent="w"),
        },
    )
    inner = [  # LakeHydrology's two BuildSnowFilter calls; the last one counts
        b
        for ln in (469, 666)
        for b in (
            bind(lake, build, ln, 0, "bounds", "bounds"),
            bind(lake, build, ln, 1, "num_nolakec", "num_lakec"),
            bind(lake, build, ln, 2, "filter_nolakec", "filter_lakec"),
            bind(lake, build, ln, 3, "num_snowc", "num_shlakesnowc"),
            bind(lake, build, ln, 4, "filter_snowc", "filter_shlakesnowc"),
        )
    ]
    drv = "elm_driver::elm_drv"
    fut = SimpleNamespace(
        subroutine_dict={
            lake: SimpleNamespace(id=lake, record_access=SimpleNamespace(bindings=inner)),
            build: builder,
            "filtermod::setfilters": SimpleNamespace(
                elmtype_access_summary={"filter%lakec": SimpleNamespace(status="w")}
            ),
        },
        driver_sites=SimpleNamespace(calls={age: [SimpleNamespace(ln=952)]}),
        driver_bindings=[
            bind(drv, lake, 931, 1, "num_lakec", "filter%num_lakec"),
            bind(drv, lake, 931, 2, "filter_lakec", "filter%lakec"),
            bind(drv, lake, 931, 3, "num_shlakesnowc", "filter%num_lakesnowc"),
            bind(drv, lake, 931, 4, "filter_shlakesnowc", "filter%lakesnowc"),
        ],
    )
    used = [bind(drv, age, 952, 1, "filter_snowc", "filter%lakesnowc")]
    found = nested_filter_builders(fut, {age: None}, used, [], logging.getLogger("t"))
    assert [text for _, text in found] == [
        "call buildsnowfilter(bounds=bounds_clump, num_nolakec=filter(nc)%num_lakec, "
        "filter_nolakec=filter(nc)%lakec, num_snowc=filter(nc)%num_lakesnowc, "
        "filter_snowc=filter(nc)%lakesnowc)"
    ]
