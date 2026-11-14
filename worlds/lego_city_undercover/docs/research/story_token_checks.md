# Story token detection, 2026-11-13

The user reported collecting Guy Newbery in a story mission. The permanent
character inventory did not contain that discovery. Static inspection of native
pickup function RVA 0x6a6f0 explains why: its story branch appends the signed
16-bit model ID to the object referenced by RVA 0x11754b0, at +0x52, and increments
the count at +0x5a. The eight bytes before the count accommodate four entries.
The city branch instead calls the permanent found-bit writer at RVA 0x88a2b0.

A read-only live sample contained count 1 and IDs [386, -1, -1, -1]. The native
model table resolves 386 to NPC_CitizenMale06. Its source pickup is mine_tunnel.giz
section 10125, index 94, at [47.0220, 4.8349, -3.8229], matching the player's
reported token position. Guy Newbery is the user-provided display-name mapping.
The new detector produced location ID 1499555494 in a read-only dry run. No game
writes or AP LocationChecks were issued by that validation.

The catalogue now classifies progress-counted roster names in type-122 source
pickups as character/vehicle tokens. There are 258 uniquely bound sources and 11
ambiguous sources. Unique entries use the mission queue or permanent found bit,
never ownership, purchase, or equipped character. This mapping is experimental:
one live story token validates the queue mechanism, not every source identity.
Booth/activity reward unlocks are not separately added as token checks.

Existing generated rooms cannot acquire new locations from a client update.
The client logs mission discoveries even when their locations are absent from
the connected slot. Regenerate with the updated APWorld to send token checks;
character_tokens and vehicle_tokens are enabled by default. The original native
save may be continued; permanent found flags reconcile supported past pickups.
