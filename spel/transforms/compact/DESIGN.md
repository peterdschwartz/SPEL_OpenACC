# Compact subgrid layout

Goal: subgrid fields stored on the elements a filter selects, so loops over a
filter read and write contiguous memory (and the per-step zeroing is a
contiguous fill), instead of scattered `x(filter(fp))` accesses into
`begp:endp` arrays. First target: the C/N/P flux types zeroed every step by
`SetValues` in `EcosystemDynNoLeaching1` (`CNZero`, plus the summaries
in `CNPsum`). Long term: filters give `beg:end` ranges for every field.

## Commands

```bash
spel compact inventory [--verdict blocked] [--field veg_cf%gpp] [-o inv.json]
spel compact rewrite --type vegetation_carbon_flux --dry-run [--diff] [--excluded]
spel compact rewrite --type vegetation_carbon_flux [-o CASE/SourceMods/src.elm [--replace]]
```

`inventory` (inventory.py) traces one time step from `elm_drv` and reports,
per field, how every access indexes it (index_forms.py), whether it lives
across steps (history/restart, registrations.py), and a verdict.
`rewrite` (select.py, rewrite.py) applies the layout to the fields of one
type that can take it.

## Layout (pilot, patch subgrid)

- `CompactLayoutMod` (templates/, copied to `components/elm/src/main`): a
  `compact_buffer_type` per instance. `add(compact_field(name, class=,
  unpack=), ptr)` gives the component `ptr` its own compact storage (with its
  current values) and points it there, so registering is binding: there is
  no separate bind phase. Fields are appended (`fields = [fields, f]`; copying
  a `compact_field` copies its pointers, not their targets). `compact_view(ptr)`
  / `full_view(ptr)` repoint a component, found by pointer association, and
  `write(unit,*) buf` lists the fields by zeroing class (Init logs it).
- Each field keeps its bounds `begp:endp`. Each clump uses the start of its
  own range: element `k0p + fp` holds the value of patch `filter_soilp(fp)`,
  with `k0p = begp - 1` of the clump. Offsets don't depend on the filters, so
  nothing is reallocated when filters change, and dummies declared
  `x(bounds%begp:)` stay valid. (No memory saving yet; a later step can size
  the storage by the filter counts.)
- `compact_soilp_off` is a thread-private module variable set by
  `get_clump_bounds`; every rewritten routine copies it to a local `k0p`
  once, so OpenMP/OpenACC loops see a private scalar. No routine signature
  changes.
- `Init` calls the generated `CompactInit` after its special-patch
  `SetValues` call (which zeroes the full arrays). The original allocation
  becomes the full layout copy: history captured its pointer at init and
  keeps reading it. Unit tests switch views with the generated `CompactView`
  / `FullView`.
- `SetValues` zeroes the compact fields with explicit assignments, one
  `do concurrent` per zeroing class under its guard: `x(k0p+fi)` once bound,
  `x(filter_patch(fi))` on the full copy before (the special-patch call).
  Explicit rather than through `cbuf%zero`, so SPEL's analysis sees the writes.
- The flux types' `SetValues` blocked loops (`do fi = 1, num, 32` around
  `associate (idx => filter(fi:...))`) become one `do concurrent` per block,
  for all six types (`--no-setvalues-loops` keeps them). The cost was
  nvfortran's handling of the associate name: in a benchmark (21,800 elements,
  40 pointer fields) nvfortran -fast took 138 ms with the associate, 0.13 ms
  for the same blocked vector subscript written out; gfortran -O2 0.18 ms for
  both. One loop writing all fields per iteration took 2.5 ms there (per-field
  loops 0.12 ms), but in EcosystemDynNoLeaching1 the two forms time the same.
- After the unpack point (`EcosystemDynLeaching`, in its clump loop, timer
  `compact_unpack`), the fields registered for history are copied from
  compact storage to their full copies, for the filter elements only. The
  other elements of the full copies keep what they had, as before.

## Which fields

A component of the type is rewritten when, for every instance it is zeroed
in (all instances share the code, so `c13_veg_cf`/`c14_veg_cf` go too):

- the inventory verdict is `compact` (or `unused`),
- it is not a restart variable and nothing accesses it after the unpack point,
- every access site is `x(p)` with `p = filter_soilp(fp)` in `do fp = 1, num_soilp`,
  or has no subscripts (passed on whole, or a dummy bound to an element),
- every site that touches it touches only selected fields (a generic
  routine indexes all arrays bound to a dummy the same way). Applied until
  nothing changes.

A routine whose array dummies get selected fields in some calls and full
layout arrays in others (`CarbonIsoFluxCalc`) is allowed when every call is
all-compact or all-full on those dummies: it gets an optional `compact_off`
dummy (index `kc = compact_off + fp` if present, else `p`), passed by the
compact calls.

`rewrite` lists uses of the selected components in routines the trace never
visits (a text search; it includes same-named components of other types).

## Reproducibility

The rewrite is generated: located by content, checked against the analysis
(a site whose text doesn't match stops it), and it refuses sources that
already have `CompactLayoutMod.F90`. `.spel-compact.json` records the SPEL
and E3SM commits, the fields, classes and files. After a rebase: drop the
generated commit, `spel analyze`, run `spel compact rewrite` again.

## Open items

- `CarbonIsoFluxCalc` (a Polymorphic routine, select.py) gets an optional
  `compact_off`, passed only by its calls with compact fields. Later
  cleanup, as its own commit with a `use_c13` test: replace its ~127 calls
  (CarbonIsoFlux1/2/2h/3) with one loop per phase over a table of
  (iso flux, flux, iso state, state) entries that carry their layout; that
  makes `compact_off` unnecessary. The isotope path is not exercised by the
  laptop test case.
- Unit tests: done (unit_test.py). main.F90 registers the compact instances
  after elm_init, binds and packs every clump before `compute`, and unpacks
  everything and unbinds after it, so IO and duplicate_sets keep the full
  layout. Test a rewritten routine from a scratch worktree of the analyzed
  commit with the rewrite applied (`spel analyze --srcroot WT` again after
  rewriting). Reference data may be captured from the rewritten sources too:
  the generated capture module (`instrument_elm.compact_capture_instances`)
  unpacks the clump's filter into the full layout and switches each compact
  instance to it around every capture, and back after, so the files hold what
  a build without the compact layout holds (checked bit-for-bit on the crop20
  case, 2026-10-19). OpenACC unit tests are not supported yet (the hooks stop).
- Fields with maps (`compact+maps`), restart fields, column types (rank 2/3)
  and the deferred `ch4_prod` fields (DEFERRED.md).
- GPU: device copies of `cbuf%data` and attach for the components.
