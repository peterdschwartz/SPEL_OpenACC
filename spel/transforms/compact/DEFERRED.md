# Deferred fields

Fields the inventory blocks for reasons that are false positives or need a
decision. Port them after the fields it reports as `compact` /
`compact+maps`.

## ch4_prod's lake call (CH4Mod.F90)

`ch4` calls `ch4_prod` twice: with `filter_soilc` and `lake = .false.`, then
with `filter_lakec`, `lake = .true.` and a patch filter `dummyfilter` of length 0.
The static trace takes every branch, so the second call shows up as reads on
lake columns. In fact the reads are under `if (.not. lake)` (the lake branch
uses `lake_soilc`), and the patch loop has zero trips.

| Field | Inventory class | Lines in ch4_prod (1-based) |
|---|---|---|
| `col_cf%hr_vr` | `other:filter%lakec` | 1248 |
| `col_cf%lithr` | `other:filter%lakec` | 1200, 1247, 1248 |
| `col_cf%somhr` | `other:filter%lakec` | 1200, 1247, 1248 |
| `veg_cf%rr` | `local` (`dummyfilter`, `num_methp = 0`) | 1168 |

The inventory deliberately doesn't evaluate value-dependent guards like
`lake`: a false positive is preferred over a false negative. Options when
porting them:

- read through the column/patch -> compact lookup, which gives 0 outside the
  soil set (safe even if the lake branch changes), or
- restructure `ch4_prod` so the lake call doesn't reach these fields (split
  the soil and lake paths, or hoist the `lake` test out of the loop).
