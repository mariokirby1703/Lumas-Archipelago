# Sonic Colours (Wii) Archipelago

PAL SNCP8P Rev0, slot schema 7, Archipelago 0.6.7+.

The production installation path generates an official **.apsoniccolours**
player patch. Opening it through Archipelago builds a separate AP ISO from
the player's verified original ISO and starts the client. HUD and seed music
are transformed locally in a single archive build. Native hooks are initialized
DOL code; AP Gecko codes and Riivolution are not required.

**The migration is implemented; the complete gameplay validation matrix is
still being finished.** See [the verification report](docs/native_patch_migration.md)
before treating every mechanic as live verified. Existing experimental limits
have not been removed or disguised by the installer.

- [Player setup](docs/setup_en.md)
- [Architecture, hooks and verification](docs/native_patch_migration.md)
- [Release build and distribution](docs/release_patch.md)
- [Default YAML](examples/SonicColours.yaml)

Existing item/location IDs, New Game bootstrap, immediate checks, journals,
Wisp/World/Chaos Emerald ownership, progressive movement, Game Land, 1-Up
Sanity, item effects and the native AP item HUD are retained.

Distribute only the APWorld, player containers and original patcher code/data.
Do not publish generated ISOs, CPKs, full DOLs, font textures or dumps.
Old .apsonic JSON files are explicitly recognized as legacy seed metadata.
Historical native research and Gecko exports remain development utilities.

The options are grouped into Progression, Checks, Game Land, Traps and
Miscellaneous. White Boost Wisp Lock, Ability Locks and Wisp Discovery Checks
default to On; Chaos Emerald Checks default to Off. Disabling Game Land Checks
also removes Assist Change and Progressive Game Land Speed from the item pool.
The item HUD is always enabled. Wisp Capsule Sanity remains available through
`wisp_capsules: true` in YAML but is hidden from generated templates and the
options creator. Existing `sequential` and `open_acts` YAML values still work.

Score Reset Trap clears the current Act's score, without changing saved ranks
or high scores. Its weight defaults to Low. Swim Everywhere Trap has been
removed. Death Link still requires native delivery and live verification;
generating a seed with Death Link enabled remains unsupported.
