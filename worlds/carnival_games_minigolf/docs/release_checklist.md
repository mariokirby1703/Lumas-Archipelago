# Release evidence still required

0.3.14 is a development build, not a live-validated public release.

The earlier RAM dumps were uploaded to a separate ChatGPT conversation and are unavailable in this workspace.
No Dolphin process was running during this validation. Do not manufacture regression fixtures from assumptions.

- Capture World Select, Level Select and the real Pro Shop (same profile/world): MEM1, MEM2,
  `/minigolfdebug`, visible screen, manager object pointers/VTables, selected theme/tab.
  Find a unique live screen/controller identity before replacing candidate state 3.
- Win Devil's Brew - Spiders: capture before play, win transition, result display and return to course.
  Determine whether `CSpidersSubLogic` (0x804FB868) creates `CMGResultsPopup` or uses another completion flag.
- Live-test the five main minigames not covered by previous reports; check both Win and Perfect.
- Deliver a 500-coin bundle in the menu, transition, save, restart Dolphin and reconnect. Check that
  the balance survives and the receipt is not duplicated. Repeat around a load/writeback transition.
- Verify that AP shop pieces and menu Par indicators do not persist after a normal save/reload,
  including saves triggered by purchases, currency and world locks. No dirty write alone is insufficient proof.
- Extract small address/byte JSON fixtures from these captures for Ghoul Hunter Perfect, G-Nome Project
  Perfect, Troll Bridge Par, Fairytella four-purchase shop and Prehistoria shop. Include capture provenance.
- After live fixes, rerun automated tests, generation, protocol and package smoke tests; update validation.md.
  Publish a release only after the remaining detection/save assumptions are resolved.

Multiplayer remains unsupported pending separate player-ownership research. Do not re-enable golfers 2?4
based solely on pointer-shaped values in manager slots.
