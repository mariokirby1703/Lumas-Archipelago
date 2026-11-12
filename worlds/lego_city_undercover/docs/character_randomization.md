# Required character randomization behavior

Explicit user requirement: individual outfits/characters are received through Archipelago.
Picking up the corresponding vanilla collectible must send an AP location check and must not grant the vanilla character.
Receiving an AP character must grant it and persist it immediately, without waiting for a later natural autosave.
The received character must be fully owned/usable without an additional vanilla purchase or Stud fee.
Merely enabling the token's buy-in-shop state is not a successful AP character grant.
This document specifies required behavior, not implemented write support.

## Two independent paths

1. Native collectible acquisition: identify the specific location, suppress the original character reward before
   it becomes available, record the completed check durably and send/retry the check through AP.
2. AP item receipt: validate seed/player/save binding, record the receipt durably, grant the actual character
   through a verified engine path, commit its state and request/verify the game's supported save operation.

An AP grant must never create a vanilla location check. Native discovery and AP-granted ownership therefore
need separate event provenance. Comparing the owned-byte or pending queues alone cannot implement this:
both native and AP grants could otherwise look identical.
Equipping, purchasing, committing pending grants and reloading must not duplicate pickup checks.

## Persistence

The AP receipt journal must be persisted immediately and reconcile permanent character ownership after load/restart.
The journal supplements native save persistence; it does not satisfy the user's immediate native-save requirement by itself.
Likewise, merely setting pending grants or copying them into the in-memory ownership bank is insufficient.
The engine's character commit, save invocation and completed disk save must be verified separately.
Grant acknowledgement must accurately distinguish journaled, applied in memory and saved to the game.
If interrupted between these stages, retry/reconcile permanent unlocks idempotently.

## Required live verification

- Native pickup sends one check and leaves the original character unavailable.
- Receiving an AP character makes it available without collecting its vanilla token.
- The grant persists after an immediate clean exit/reload, without an unrelated story autosave.
- Disconnect/reconnect and replay do not grant or check twice.
- Receiving one's own character at a location sends the check and then grants only on the AP receipt path.
- Received-item restoration after load does not fabricate checks.

Current implementation only reads relevant character state. No native-reward suppression, AP item granting,
receipt journal, native save invocation or persistent grant has been implemented or claimed.

## Terminology and AP shops

Use character as the umbrella term for individual outfits/skins. Keep disguise classes and individual abilities
distinct in the data and logic. The current vanilla mechanic-token experiment is research on purchase semantics;
it is not the intended AP acquisition flow.

Explicit user requirement: repurpose suitable other in-game shops to sell AP items, with the actual item name
and recipient displayed before purchase. These shop purchases are independent AP locations/checks.
Stock/scouting metadata must come from the connected seed's server LocationInfo, including recipient identity;
do not invent item/recipient labels from the vanilla shop reward or locally assumed placement.
Paying the configured price completes that shop location once and sends/retries its check; the server then
delivers the placed item to its recipient. An item for this player follows the ordinary AP receipt/grant path.
Do not grant it separately at checkout and again on receipt.

Persist purchases and outgoing checks with seed/player/save binding, reconcile server-confirmed purchases,
and prevent repeat charges/rewards after reconnect/reload. Insufficient funds or unconfirmed stock metadata
must not silently charge the player. Native UI integration, supported shop inventory, costs and an engine-safe
purchase/save transaction still require research. No AP shop is implemented yet.
