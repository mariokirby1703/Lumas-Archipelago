# LEGO City Undercover integration research

This is an incomplete integration under development for Archipelago 0.6.8.
There is no playable APWorld, AP client executable, YAML, or verified item-grant implementation yet.

The supplied files stay at `notes/gamefiles/`. Nothing modifies those files or game saves.
Research tools implement full-file SHA-256 inventory, PE inspection, CRC-verified CC4 v2 archive indexing,
ZIPX/DFLT extraction, and reproducible candidate mapping. The Windows bridge currently provides read-only diagnostics.

The offline pipeline now also parses all 662 JobDataMap jobs with a byte-exact round-trip, indexes 745 scripts,
and inspects all 957 extracted GIZ resource headers. Twenty tests pass.
It builds `build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz`, a standalone Python research diagnostic.
This is not a playable randomizer or the requested Windows AP client executable.

See [development](docs/development.md), [progress](docs/progress.md), and
[research findings](docs/research/reverse_engineering_findings.md).
