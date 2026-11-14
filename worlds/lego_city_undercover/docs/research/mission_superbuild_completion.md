# Mission Super Build direct completion

The user built the mine gondola. Objective Mine_CableCar (hash 286030908,
scanner bit 313) stayed false before and after. The current seed already contains
location 1374214294, so the missing component was native detection.

Native manager global RVA 0x17ec978 selects the scene component, vtable
0xc30608; list head +0xe0, next +0x28, object vtable 0xc300f8 and owner +0x48.
The state setter 0x73140 stores the state at +0x1e2. Its state-5 branch sets
completion flag 4 at +0x1e4. The live gondola object #cg_641_CableCar_SB read
state 5 / flags 4. Its exact mission/name is bound to Mine_CableCar in
superbuild_bindings.json. This association has one live validation; generated
names across builds and other mission Super Builds still require validation.

The read-only dry run selected exactly location 1374214294 despite the false
scanner bit, without server messages or native writes. The client now logs
completed SuperBuildGizmo objects, including unmapped ones. Only explicit
mission/name bindings produce automatic checks. State 3/4, flags alone, scene
entry, gold brick changes and resource expenditure do not count as completion.
This reader covers the currently loaded player scene, not persistent backfill
of every past mission after unloading its objects.
