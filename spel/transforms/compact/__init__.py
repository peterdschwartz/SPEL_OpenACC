"""
Compact subgrid layout for ELM derived-type fields.

Fields stored on the elements a filter selects (indexed 1..num_filter) instead
of the whole clump (begp:endp). `inventory` reports, for every field of the
target types, how the time step uses it and whether it can be compacted.
"""
