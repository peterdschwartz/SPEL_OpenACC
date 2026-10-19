"""
Common nutrient base types for ELM's C/N/P derived types.

The carbon, nitrogen and phosphorus state and flux types of each subgrid
level declare many of the same fields, named alike except for the element
letter (``leafc``/``leafn``/``leafp``, ``cpool_to_leafc``/``npool_to_leafn``).
`common` finds them, as the members of a base type the concrete C/N/P types
can extend.
"""
