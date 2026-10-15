# Sonic Colours (Wii) setup

Supported source: an uncompressed original **PAL SNCP8P Revision 0 ISO**.
Use Archipelago 0.6.7+ and 64-bit Dolphin with Dolphin Memory Engine support.
See [the migration verification report](native_patch_migration.md) for tests
actually performed and outstanding gameplay verification.

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
