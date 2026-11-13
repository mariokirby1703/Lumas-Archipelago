# Automatic observer coverage

The goal is ordinary play producing diagnostic evidence without requesting manual
before/after snapshots for every object. This document separates implementation
from desired coverage; this is not a declaration of a complete native randomizer.

## v14 automatic city pickup observation

Scene registry at global 0x1c402d8 contains 2,048 lookup slots (native accessor
0x512dc0 bounds index by 0x7ff). v13 only followed the actor's own scene; the
registry also exposes loaded streamed tile scenes. v14 enumerates bounded owners,
validates the pickup component layout and preserves partial-coverage/error counts.
Non-level/stale owners are excluded. This does not cover unloaded map tiles.

Current live validation: 29 components, 137 objects, 20 city-persistence bindings,
all 20 uniquely matched to source tile/name; no binding conflicts. Combined
snapshot time was approximately 16 ms. Artifact: observer_v14_live.json.

Per-connection identity memory survives disappearance/unloading of a pickup
object. It retains native ID, source name, source key where unique, object position
and last-seen sample. This memory is explicitly historical, not current presence.
Conflicting bit identities and multiple source-name matches are not guessed by
distance and cannot produce an automatic AP check. Reconnect resets memory and
completion baseline; disconnect before switching save slots remains required.

New `pickup_catalogue_change` records preserve discovered identities in copied
logs. Pickup records include current before/after object observations plus cached
observations and a conflict flag. The UI reports loaded components/objects and
remembered identities. Object coordinates remain distinguished from sampled actor
coordinates; resource transforms are not silently assumed absent.

The AP client can dynamically bind an active source_pickup location to a unique
runtime tile/name match after observing a new collection bit. Native bindings no
longer have to be prelisted among the 20 initial research matches. Baseline,
duplicate, disappearance and conflict behavior are covered by pure tests. A real
server roundtrip for the dynamic path remains untested.

Context changes additionally retain actor position when the native transform
accessor matches the verified layout. `native_object_state_change` records show
individual object flag changes with before/after values, source name, player and
object position. First baselines, scene changes and unsupported/load intervals
do not become inferred actions. These records are explicitly not completion
checks. Known user-confirmed model names Sam Penn, Rob Shepherd and Häftling are
displayed alongside their internal identifiers; other model names stay native.

## Coverage boundaries

| Feature | Current implementation | Still needed |
| --- | --- | --- |
| City Super Bricks | Native city bit transition, loaded-instance identity, cached source | Independent pickup tests across templates, transformed and colliding resources |
| City activities | Named objective transitions | Distinguish prerequisite flags from reward/completion for each category |
| Characters/vehicles | Found/owned/pending/equipped separated | Full display-name localization, immediate story pickup detection, native grant/suppression |
| Quest objects | Attached definition changes | Reliable hand object and generic igizitem model identity |
| Movement/actions | Context history | Object-specific actions beyond shared contexts |
| Action fields | Loaded GizSwitch/Techno instances, selected native result, marker prediction | Additional systems, full usability and rendered state |
| Scan auras | Detective/Criminal/Audio type registry | Exact inside/outside sensor and scan completion predicates |
| Story | Campaign cursor and selected job values | Persistent mission IDs, replay-safe completion, native entrance gating |
| Red bricks/shields/hero | Catalog candidates and manual observations | Direct transient native pickup paths |
| Item receipts | Durable client receipt journal | Native application, provenance, persistence and vanilla-reward suppression |
| Native locks | Research on prerequisites | Game-thread bridge/hook and per-item/per-area enforcement |
| Cutscene skip | Hash-guarded opt-in byte writer | Actual automatic writer/skip behavior test |

Monitor remains read-only. The separate client has no general native grants or
locks. Displaying a context or candidate does not mean a check has completed.
