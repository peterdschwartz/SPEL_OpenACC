from spel.transforms.nutrient.common import (
    Family,
    Variant,
    family_name,
    find_collisions,
    masks,
    match_fields,
    near_misses,
)


def comps(names, bounds="begp:endp", rank=1):
    return {n: Variant(n, "real", rank, bounds, "pointer", i) for i, n in enumerate(names)}


def family(c, n, p):
    components = {"c": comps(c), "n": comps(n), "p": comps(p)}
    fam = Family("vegetation_nutrient_flux", {"c": "tc", "n": "tn", "p": "tp"})
    fam.fields = match_fields(components)
    return fam, components


def bases(fam, elements):
    return {f.base: {e: v.name for e, v in f.variants.items()} for f in fam.by_elements(elements)}


def test_family_name():
    assert family_name("vegetation_carbon_flux") == ("vegetation_nutrient_flux", "c")
    assert family_name("phosphorusstate_type") == ("nutrientstate_type", "p")
    assert family_name("bounds_type") is None


def test_masks_replace_subsets_of_the_letter():
    assert masks("cpoolc", "c") == ["cpoolc", "#poolc", "cpool#", "#pool#"]
    assert masks("gpp", "c") == ["gpp"]


def test_matches_element_letters_only():
    fam, _ = family(
        ["deadcrootc", "cpool_to_leafc", "gpp", "species"],
        ["deadcrootn", "npool_to_leafn", "species", "sminn_to_npool"],
        ["deadcrootp", "ppool_to_leafp", "sminp_to_ppool"],
    )
    assert bases(fam, "cnp") == {
        "deadcroot": {"c": "deadcrootc", "n": "deadcrootn", "p": "deadcrootp"},
        "pool_to_leaf": {"c": "cpool_to_leafc", "n": "npool_to_leafn", "p": "ppool_to_leafp"},
    }
    assert bases(fam, "cn") == {"species": {"c": "species", "n": "species"}}
    assert bases(fam, "np") == {"smin_to_pool": {"n": "sminn_to_npool", "p": "sminp_to_ppool"}}
    assert bases(fam, "c") == {"gpp": {"c": "gpp"}}


def test_allocation_bounds_dont_block_the_base_declaration():
    fam, _ = family(["leafc"], ["leafn"], ["leafp"])
    (f,) = fam.fields
    assert f.consistent and not f.alloc_differs
    f.variants["p"].bounds = "(:)"  # allocation not found
    assert not f.alloc_differs
    f.variants["p"].bounds = "begp:endp,1:nlevdecomp_full"
    assert f.consistent and f.alloc_differs
    f.variants["p"].rank = 2
    assert not f.consistent


def test_collision_with_existing_component():
    fam, components = family(["totc", "tot"], ["totn"], ["totp"])
    assert find_collisions(fam, components) == {"tot": ["component of tc"]}


def test_near_miss_inserted_token():
    fam, _ = family([], ["actual_immob_vr"], ["actual_immob_p_vr"])
    assert near_misses(fam) == [("n:actual_immob_vr", "p:actual_immob_p_vr")]


def test_base_names_table():
    fam, _ = family(["begcb", "ctrunc"], ["begnb", "ntrunc"], ["begpb", "ptrunc"])
    assert {f.base for f in fam.common} == {"balance_beg", "trunc_sink"}
