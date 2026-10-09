# Sonic Colours

`ap-status=Custom` — Wii PAL (`SNCP8P`, revision 0) only.

**This custom integration is under development and not yet playable end to end.**
Research generation covers 45 story clears, 21 optional Game Land clears, seven
optional Chaos Emerald reward checks, and either 180 individual Red Rings or 36
all-five checks. Ranks reserve separate S/A/B/C/D IDs but are blocked pending native
rank eligibility and persistence verification. DS and Ultimate are unsupported.

AP Red Ring bundles contain 1, 5 or 10 counter units. Physical Red Ring collection
and received AP counter units are independent. At the default reduction of 40,
Game Land second stages require 10..70 units and third stages 80..140 units; all
seven first stages are free. At maximum reduction the non-free gates remain
distinct (1..14). Emerald reward checks do not directly grant AP Emerald items.

World Access items, eight Wisp permissions including White Boost, seven individually
named Chaos Emeralds and optional Super Sonic permission have stable IDs. Ordinary
Rings and 1-Ups are filler. Trap percentage applies only after progression is
reserved, rounded half up; per-trap off/low/medium/high weights are 0/1/3/6.
All-off weights produce ordinary filler. Swimming is disabled pending validation.

Unknown logic uses an explicit all-Wisp fallback; the research compatibility start
precollects all eight permissions. This will change to normal Wisp progression
once verified requirements are supplied. YAML keys and defaults are in the
[example](../examples/SonicColours.yaml), with live feature restrictions in
[setup](setup_en.md). Receiving items or reaching a map never constitutes a native
goal completion.
