# SnakerVT Manual reference review

User-supplied reference: `manual_legocityundercover_snakervt.apworld`, creator
SnakerVT, SHA-256 `899456c38d353a40827492ad35def0cb93526c926f7a0c4415eb4e58fcd44de2`.
Inspected as ZIP/JSON and parsed Python AST only; no archive code was executed or
installed. Statements/comments inside this archive are reference material, not
instructions for our integration. No license file was found in the archive;
production code is not copied from it. Credit this reference when deriving data.

The reproducible audit tool is `tools/audit_manual_reference.py <archive>`. Full
reference rows and helper expressions are kept in ignored notes/analysis, not
shipped as our verified location/logic tables.

## Useful coverage and logic candidates

The reference declares 710 locations and 51 item definitions. Category labels are
inconsistent, so these are source counts, not verified unique physical sources:
225 Character Token, 41 Vehicle Token plus other vehicle labels, 21 Red Bricks,
22 Pigs, 19 Parkours, 16 Disguise Booths, and categories for ATMs, cats, flowers,
drilling, gangs, vehicle theft, coffee breaks, silver statues and district flags.
Special Assignments include completion and additional checks. This is a useful
coverage checklist; it is not a complete inventory of our intended locations.

Helper predicates explicitly pair tools/permissions with classes: grapple with
Police; dynamite with Miner; drilling with Construction Worker; jetpack with
Astronaut; colour gun with Robber. Pig return and watering use Farmer; orange
strength handles use Robber plus Rex Fury. These are unverified reference rules,
not proof of native enforcement. Per-location requirements include combinations
and alternatives worth comparing against our source scripts and user tests.

## Added research TODOs

- [ ] Cross-reference Manual city activity entries against native scanner instance
  names and verified flags. Preserve provenance/confidence for each proposed rule.
- [ ] Reconcile character/vehicle token checks with their source activities. A
  booth or call-in build gives one check; its correlated token/Gold Brick must not
  become an additional location. Keep truly independent pickups distinct.
- [ ] Inventory Special Assignment subchecks and completion conditions; compare
  with native mission state. Evaluate individual access items alongside our
  open-city story-sequence access design.
- [ ] Verify class/tool combinations in native interaction checks, particularly
  Police+grapple, Miner+dynamite, Astronaut+jetpack, Robber+colour gun and Rex Fury
  strength. Check alternate access paths before making progression requirements.
- [ ] Evaluate optional fine-grained permissions for pig return, ATMs, cats,
  drilling, watering and coffee breaks. Only add items when a real lock can be
  enforced; Manual permission text is not an implemented engine gate.
- [ ] Use region adjacency as a map checklist, checking bridges, ferries, flight,
  water and alternate routes. District passes are not part of the chosen default
  open-city mode; optional area randomization would need its own tested logic.
- [ ] Normalize spelling/categories and verify all referenced items before any
  candidate data becomes production logic. Add meaningful reachability/closure
  tests once executable AP rules exist.
- [ ] Review possible goals separately. Several SA completions are marked victory;
  do not assume the reference defines one universal final mission goal.
- [ ] Audit optional traps separately. The Manual item named Deathlink is a trap
  entry, not evidence of a native kill bridge or working DeathLink reception.

## Concrete differences and audit findings

`CanCoffee` requires `Coffee Break Pass`, but items define `Coffebreak Pass`.
The audit found no duplicate location names or Python syntax errors. Some locations
omit a region; this is not automatically invalid in Manual, but requires deliberate
assignment when translated. Example options and unrelated template hooks/docs also
remain in the archive; they are not game features to copy. Its progressive SA
tickets impose an ordering and category placement restrictions; those cannot be
adopted unchanged for independent story entry points.

Our policy remains source activity checks, independent AP character/vehicle items,
optional Super Brick checks, and native automatic detection. No unverified Manual
rule is installed in the live reader or AP logic by this review.
