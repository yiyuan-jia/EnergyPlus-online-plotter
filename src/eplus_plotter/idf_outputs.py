"""Parse ``Output:Variable`` objects out of an IDF.

These are the variables the model already declares for reporting; the plotter streams exactly
those. An object looks like::

    Output:Variable,
      *,                          !- Key Value  ('*' or a specific key; blank means '*')
      Zone Mean Air Temperature,  !- Variable Name
      Timestep;                   !- Reporting Frequency

The reporting frequency is irrelevant to live reads (the API yields the current value every
zone timestep regardless), so only ``(name, key)`` is kept.
"""

from __future__ import annotations

from .sample import VariableSpec


def _strip_comments(idf_text: str) -> str:
    return "\n".join(line.split("!", 1)[0] for line in idf_text.splitlines())


def parse_output_variables(idf_text: str) -> list[VariableSpec]:
    specs: list[VariableSpec] = []
    for statement in _strip_comments(idf_text).split(";"):
        fields = [f.strip() for f in statement.split(",")]
        if len(fields) < 3 or fields[0].lower() != "output:variable":
            continue
        key, name = fields[1], fields[2]
        if not name:
            continue
        specs.append(VariableSpec(name, key or "*"))  # blank key value means all keys
    return specs
