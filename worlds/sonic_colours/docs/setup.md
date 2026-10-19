# Sonic Colours (Wii) setup

Supported source: an uncompressed original **PAL SNCP8P Revision 0 ISO**.
Use Archipelago 0.6.7+ and 64-bit Dolphin with Dolphin Memory Engine support.
See [features, options and verification limits](sonic_colours.md) for the
current scope. This guide describes the native ISO workflow, not the retired
manual Gecko/Riivolution installation.

## Install and generate

1. Install sonic_colours.apworld in Archipelago's custom_worlds directory and
   restart the Launcher. Avoid duplicate installations/source checkouts.
2. Generate your multiworld. Each Sonic player receives a small
   **.apsoniccolours** player patch, not a game archive.
3. Choose **Open Patch** in the Archipelago Launcher and select the patch.
   The Sonic Colours Client entry recognizes it too. Its first Windows launch
   registers a per-user association for subsequent double clicks, without
   replacing another application's association.
4. Select Dolphin.exe once, then your original PAL ISO once. Both paths are
   remembered. Cancelling Dolphin selection skips emulator launch while still
   allowing patch creation and opening the client. Archipelago saves the ISO path in
   sonic_colours_options.iso_file.
5. A cancellable progress window covers source validation, Wii DATA partition
   extraction, native hooks, combined HUD/music build and image verification.
6. Dolphin starts the resulting ISO automatically when no instance is running.
   The opened client uses the patch's player name and connects to its server
   address when present. A patch downloaded from a hosted room can contain that
   room address; a local generation cannot know a room that does not yet exist.
   In that case, enter its address in the client.

On Windows, an already open Dolphin receives a normal close request and is
restarted with the generated ISO after it exits. Confirm Dolphin's own stop/exit
dialog if one appears. Cancelling that dialog leaves the existing game alone;
after 60 seconds the launcher reports that startup could not continue. It never
force-kills Dolphin or launches a second instance. Multiple open instances
produce an explicit error. On other platforms, close Dolphin before opening
the patch. This restart uses no undocumented existing-instance boot IPC.

The output is beside the patch, with its base name and .iso extension. Keep
its .iso.sonic.json sidecar: it records input/output checksums and seed/build
identity. Matching outputs are validated and reused. Different existing files
are refused; choose another output name rather than overwriting them.

Your original ISO is never modified. Generated ISO/CPK/DOL files contain your
own game data and must not be redistributed. The patch and APWorld contain
only code, metadata and transformations. No original atlas, whole executable
or original archive is shipped.

## Tools and optional automatic start

Windows downloads Wiimms ISO Tools 3.05a from the official server and verifies
its pinned SHA256. WIT is GPL software; licenses are included in its local
distribution and source is available at https://wit.wiimm.de/.
An existing wit on PATH or sonic_colours_options.wit_path can be used instead.
Other platforms require a platform-compatible WIT installation; automatic
tool download is Windows-only.

Allow about three times the input ISO size plus 2 GiB of free space. Temporary
files are cleaned on failure/cancellation. The verified final image is
published atomically on the output filesystem.

Automatic Dolphin start defaults to on for new settings. An installation with
no Dolphin path also receives the first-run chooser; selecting the executable
enables automatic startup. After setup, explicit auto_start: false settings
remain respected. Set auto_start under
sonic_colours_options, or pass --start-dolphin --dolphin PATH.
Use --no-start-dolphin to skip startup for this invocation. --patch-only builds
without selecting/starting Dolphin unless --start-dolphin is also supplied.
The patcher does not change unrelated Dolphin settings. Use the game's
English UI for the tested font resources.

## Native hooks and legacy setups

The new image needs **no AP Gecko codes, Riivolution or experimental DME code
injection**. Do not run old AP codes over it. The client checks its native
signature, hook targets, exact payloads and normalized original PAL hashes.
Incompatible or overwritten installations are rejected.

Schema-7 JSON .apsonic files are explicitly treated as legacy metadata and can
use the same installer. They are never interpreted as native ZIP containers.
For migration, provide the old seed's explicit AP player slot number:

```powershell
python -m worlds.sonic_colours.client.launch --migrate-seed-patch OLD.apsonic NEW.apsoniccolours --player-slot 1
```

Unsupported older schemas require regeneration. Existing schema-7 item and
location IDs and server semantics are preserved. Do not transfer journals
between seeds. Gecko/resource exporters remain development utilities only.

## Command line

```powershell
python -m worlds.sonic_colours.client.launch SEED.apsoniccolours --original-iso "Sonic Colours.iso" --patch-only --nogui
```

Optional flags include --output-iso, --wit, --connect, --name, --start-dolphin
and --dolphin. The standard Patch.create_rom_file handler is registered too.

## Playthrough and reconnect

Connect before starting New Game. Native scene/factory evidence establishes
the mandatory two Tropical Resort bootstrap Acts. Immediate Red Ring,
eligible capsule and Clear/Rank checks can precede the first save selection.
Choose a free slot normally and preserve existing saves.

The patched game runs permanent hooks; the AP client controls ownership using
validated runtime data/mailboxes. Durable journals prevent check/item replay.
A native image from another seed is rejected. A save switch or unattributed
save may defer writes; /sonicbinding, /sonicstatus and /sonicitems explain why.

The always-on HUD shows five recent messages, coloured items, black outlines,
own finds in two lines and a 60-second lifetime with a final ten-second fade.
/sonichud test is a local renderer preview, not a received AP item.


## Sheet V2 upgrade

Use a newly generated seed for the corrected Wisp pools and Sheet V2 placements.
Ability Locks Off now gives single, complete Drill/Hover/Spikes unlocks; White
Boost Wisp is absent when its lock is Off. Capsule Sanity remains a hidden YAML
option. Random Capsules only exists with Game Land Checks.

Existing schema-7 seed containers/receipts remain supported. Rebuild their ISO
with the new APWorld for native oxygen/capsule fixes; rebuilding cannot change
the old server's item placements or logic. Output upgrades preserve existing ISO
files. DeathLink and Dead Weight are selectable without the hidden developer flag,
but their full live safety matrix remains incomplete. See the overview
before enabling them in an important multiworld.

## Server address and port

A hosted-room download should contain that room's full address, including its
port. The patch's connection metadata supplies the initial client address and
player name. A locally generated patch cannot predict a future room's port.
If no complete address is embedded, the launcher asks for it; use exactly the
host and port shown by the room page (for example `example.org:38281`). An
explicit `--connect` overrides patch metadata. Never infer a new room's port
from an old client session. Password-protected rooms still require their
password. Reusing generation output does not make a new room a new seed; saved
AP ownership/journals must remain consistent with that seed and slot.

## Original-source verification

The installer checks the ISO/DATA disc ID and revision, partition integrity,
and these original-file SHA256 values:

| File | SHA256 |
| --- | --- |
| `main.dol` | `92aefe33b577493b492f8433ca68b90d25d29d2d6f9c85310a6829481281f8a9` |
| `sonic2010_0.cpk` | `58bbf2be97a2f08effb5752bd40eea8a1ba76a18349937a32351624d855651bf` |

An ISO that already contains mods is not a replacement for the verified
original source. Reopen the same player patch with the updated APWorld to
rebuild a changed native component. A matching existing image is reused; an
older verified output is kept and the upgrade gets a component-specific name.
You normally do not need a new seed for a client/native correction. A new
seed is required to change the server's item pool, options or logic placements.

## Troubleshooting

Newly generated multiworlds use a separate deterministic music shuffle for each
Sonic Colours player slot. Each player's patch, ISO and now-playing display use
that same shuffle. Older seeds keep their original shared music mapping.

The patcher keeps a private original-partition cache in Archipelago's user
directory under `sonic_colours_cache/original-v1`. The first build may take
slightly longer while preparing it and needs additional disk space. Later
seeds copy and hash these files instead of verifying and decrypting the whole
original Wii partition again. The original ISO is still hashed, every restored
file is checked, and the generated Wii partition is verified. HUD and music are
still built together for each seed. A corrupt cache falls back to extraction;
you can delete this disposable cache while the patcher is closed to reclaim
space or recreate it. Keep your original ISO, generated ISO receipts and client
journals. No cached game resources are distributed with the APWorld.

The window shows elapsed time, checksum progress and WIT progress. Cancellation
stops WIT promptly; an in-progress HUD-resource calculation finishes its current
step before cleanup. Existing verified seed ISOs are reused after full checksum
validation. A first build and a cached build can take different amounts of time;
the encrypted output rebuild and output verification remain necessary.

| Symptom | Check |
| --- | --- |
| No patch chooser or wrong client opens | Restart Archipelago after installing the APWorld. Remove duplicate installed copies; verify the intended world/client version. Open Patch and the Sonic client launcher both support the player patch chooser. |
| ISO builds but Dolphin does not start | Verify the stored executable path and automatic-start setting. Resolve Dolphin's own close confirmation if it was already running. Keep only one Dolphin process. |
| Client cannot attach or writes stay blocked | Use the supported PAL Rev0 game, the matching generated native ISO and exactly one Dolphin instance. Dolphin Memory Engine must be available to the Archipelago Python/client environment. Run `/sonicstatus`, `/sonicbinding` and `/sonicdebug`. |
| Incompatible native signature or modified entry | Stop emulation, repatch the original ISO using the current APWorld and the same player patch, then restart the client and new image. Disable old AP Gecko/Riivolution patches. Do not apply runtime instruction fixes. |
| Checks/items defer after a save switch | Confirm the selected save belongs to the seed/slot. Let the client observe stable native ownership. Keep the original journal; do not delete it to force receipt replay. `/sonicbinding` explains attribution. |
| HUD test works but AP messages do not | `/sonichud test` is only local preview. Check the actual server/port, selected player, connection and `/sonicitems`. An already checked location does not give another server check. |
| Missing text in a menu/results scene | Keep the scene open for discovery. This is not necessarily a lost check: compare server receipt/check state with `/sonicstatus`. Some visual scene coverage remains unverified. |
| Slow updates or a short severe stall | `/sonicdebug` includes `sync_performance`, per-phase blocking times and Dolphin I/O/process-enumeration counts. Read-only identity proofs are bounded; mutating effects retain separate authenticated checks. Record the scene and action so a stall can be reproduced. |
| `protected native entry` write blocked | Diagnostics include `latest_blocked_native_write` with the attempted operation/address and bounded caller trace. Keep this evidence; the protection deliberately prevents mutation. |
| Dolphin invalid read/crash | Keep the error state available for diagnosis. The displayed PC may belong to the crash reporter rather than the original fault. The Game Land low-memory fix has one confirmed connected passage; broader coverage is still pending. |

Do not enable MMU or repeatedly ignore an invalid-read dialog as a substitute
for diagnosing an AP hook fault. No unsupported game revision is made safe by
disabling the write checks.

## Local developer commands

`/testitems list` lists local ability overrides. Examples are `/give Double Jump`,
`/give Progressive Crouch 2`, `/remove White Boost Wisp` and `/testitems reset`.
These affect only the running client's test overlay; they do not send AP items,
change server placements or inject durable received-item receipts. Reconnect or
restart clears the overrides. Use real server delivery for end-to-end tests.

For repository verification, run the full world suite and build the APWorld.
The package's two canonical documents plus generated WebHost game-info alias
can be read directly from the ZIP. A fresh original-source build and a real
Dolphin/server playthrough are separate checks: offline tests and successful
Wii partition verification alone are not live gameplay verification.
