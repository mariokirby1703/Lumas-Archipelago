# Result-screen AP HUD coordinates

The user reported item messages under Rank and no visible music panel. A live
read on 2026-10-16 confirmed result-local casts at x=50, y=176 and music y=365/382.
The PAL result coordinate controller (style class 807AB988) exposed an identity
2x3 affine matrix with translation x=267.87067, y=110, base width=640 and
viewport width=822.5692. The additional native widescreen centre adjustment
was (viewport-base)/2, yielding total horizontal origin 359.15527.

Result owner discovery now reads and validates this translation, dimensions,
class and reference chain, anchors them against scene changes, and subtracts
the horizontal origin from AP-only publication coordinates. Other scene owners
use origin zero and retain their exact existing positions. Unsupported scaled,
nonfinite, invalid-class or changing transforms fail closed.

Only the result resource changes vertical baselines: item row zero is local
0 (screen-relative 110), rows remain 40 apart, and music is local 255/272
(screen-relative 365/382). Colours, fonts, right alignment, names and timers
remain unchanged. The music popup still uses its normal finite display time;
this fix does not make it permanently visible.

Tests verify the measured transform, invalidation when it changes, unchanged
non-result payloads, compensated item/music X, and actual original-CPK overlay
coordinates with all pre-existing result casts byte-identical. A rebuilt ISO
plus updated client is needed; the same seed/save remain valid. Final visual
confirmation on that rebuilt ISO is pending.
