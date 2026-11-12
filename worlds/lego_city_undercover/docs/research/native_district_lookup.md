# Native district lookup, 2026-11-12

Nearest collectible resource is not a reliable district detector. Both observed
positions (-217.16025,13.71088,300.33939) and (-220.62720,13.70877,303.26401) were
reported by the user as Bluebell National Park, despite nearest pickups belonging
to WI_Farmlands_0805. The older claims of Fort Meadows are withdrawn.

The UI code at RVA 0x275ad1 obtains the active world via 0x606be0, scene +0x178,
entity +0x98, grid component via 0x47c0, then uses position lookup 0x611320.
It passes the resulting tile to district lookup 0xcad40 and sets UI field +0xc4
from the district record's +8 index. This is a concrete UI path, not a nearest-object
heuristic. The UI may use a selected map position; player/cursor correspondence
and other scene/menu states still need testing.

World singleton pointer: RVA 0x1c6a768. Grid component type index: uint32 at
0x17ebc30 (observed 24). The entity's first virtual function was 0x3be70, an
indexed component accessor at entity+0xd0+index*8. 0x47c0 returns the component's
+0x38 override if present. Null/parent-fallback variants are not supported by the
current research probe.

Grid origin +0x100 was (-450,0,450), cell size +0x110 was 30. Dimensions at
RVA 0x1165910 were (38,38); Z multiplier at 0xc0fe1c was -1. Native calculation
uses single precision, reciprocal cell size and truncation toward zero. Cell table
is grid+0xf0, row-major pointer array. Cell+0x58 gives a tile, whose native name
string is addressed by tile+0x68 and tile coordinates are two bytes at +0x208.

At the unchanged second user-confirmed position, the read-only probe resolved cell
(7,4), native name **WI_Forest_0704**, matching Bluebell National Park. Both saved
positions compute to that cell. This is one user-correlated region example, not
complete validation of all boundaries or direct reading of a displayed label.

The subsequent read at (-214.98398,13.78018,298.30679) resolved (7,5), native tile
WI_Farmlands_0705. The user confirmed the map now displayed Fort Meadows. This
validates one observed Bluebell -> Fort Meadows boundary crossing. Evidence is
live_native_district_fort_meadows_confirmed.json; all other boundaries remain untested.

`tools/probe_native_district.py` hash-gates the executable, checks observed virtual
getters, bounds the grid, and never calls game functions. It is a research tool,
not yet wired into the general diagnostic reader. Tests cover the two corrected
positions and invalid grid inputs. No return-to-area or object gating is implemented.
