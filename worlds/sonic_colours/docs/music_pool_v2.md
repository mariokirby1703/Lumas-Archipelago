# Normal music randomization: mapping version 2

New generated slots carry `music_mapping_version: 2`. With Music Randomization
on, Reach for the Stars and Speak with Your Heart are normal donors; each is
assigned once to a randomly selected eligible music destination. The shared
donor pool contains 80 tracks. Other finite jingles/transformations remain
protected. No test command, new YAML setting, audio re-encoding or changed
music display name is required.

Original opening/credits destinations retain their exact original audio
references, so they do not inherit looping stage audio. Consequently two of the
78 ordinary donors are omitted from each new shuffle, rather than forcing a
permutation through those protected cutscene destinations. All other eligible
donors are unique, deterministic, and differ from the destination's original
audio identity. The existing native Stop/Prepare/Play EOF fallback handles the
two finite donors on their randomized channels. Both songs' audible full-song
restart was confirmed by the user on native_music_loop_v4.iso.

A missing version field means version 1. Its original seed-derived mapping is
unchanged byte for byte. Updating the APWorld or rebuilding an old patch does
not reshuffle an existing seed. Version is used consistently by the ISO's single
HUD/music CPK build, resident client writer, standalone resource manifest and
cached music-popup lookup. Unknown versions fail validation. Music off still
restores the exact original bank in both versions.

For the new normal pool, generate a new seed with the updated APWorld, download
its patch and patch the original ISO through the usual workflow. Existing V4
native code already contains the required replay hook, but the generated ISO
must still belong to the new seed. No distributed original game resources are
included. Earlier music naming, layout, font, colours and popup timings remain
unchanged.

Verification includes 100 V2 seed mappings, golden V1 mapping hashes,
beatable new generated seeds with music on/off, protected original finite leaf
bytes, canonical CSB recovery/readback, real original-CPK resource generation,
resident V2 publication, and matching popup donor identities. Scene exits,
original opening/credits completion and further UI contexts remain separate
live checks; no global production-validation flag has been enabled.
