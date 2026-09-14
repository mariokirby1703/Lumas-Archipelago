# Carnival Games MiniGolf (Wii) — Archipelago MASTER NOTES FOR CODEX

**Consolidated through:** 2026-09-11  
**Purpose:** implementation handoff for the Archipelago world, external Dolphin client, memory layer, options, region logic, locations, items, goals, and QA.  
**Status:** core reverse engineering is substantially complete. Remaining work is mostly implementation and validation.

> **Critical:** never hardcode example heap/save addresses such as `0x8094E908` as permanent. Resolve the manager/root every session and use the relative offsets in this document.

## Tested executable / revision fingerprint

- `main.dol` size: `5549536` bytes
- SHA-256: `0aad886672197ff23c2c85beafc4ead58541e75c975593b55558b8fb7d18f251`
- observed DOL entry: `0x8000403C`
- Wii/PPC multi-byte values are **big-endian**
- all static code/VTable addresses below are revision-specific

---

# 1. What is solved

Confirmed/found systems:

- stable manager/root resolver
- 9 per-world normal Coin counts
- 27 Barker Coin per-hole flags + Barker total
- 27 Par Club Piece flags = the 27 Par-or-better checks
- 88 persistent prize/unlock states with exact English names
- 63 normal world-Coin shop purchases
- 7 Barker Shop purchases
- 9 World Map Secrets
- 9 Par Club completion rewards/Clubs
- live strokes, live par, and in-goal state
- normal-hole identity mapping and all 27 hole names
- minigame live controller, score/target, Win, Perfect
- minigame identity VTable map (Mine Shaft Madness live-confirmed, other 8 static-mapped)
- persistent 9-byte world lock array
- live manual world lock/unlock test passed
- vanilla unlock write and world-lock save serialization
- random/selectable starting world is technically supported

---

# 2. Stable runtime resolver

```python
manager = read_u32_be(0x805DDD80)
session = read_u32_be(manager + 0x114)
player_index = read_u32_be(session + 0x2EC)
root = read_u32_be(manager + 0x190 + player_index * 4)
sub = root + 0x1DC
```

Per local player:

```python
player_root[p] = read_u32_be(manager + 0x190 + p * 4)
player_count = read_u32_be(manager + 0x12C)
```

Confirmed example dump:

```text
manager = 0x805F5400
root    = 0x8094E72C
sub     = 0x8094E908
```

The same root happened to survive the supplied full restart, but the client must still resolve dynamically.

---

# 3. Persistent MiniGolf state layout

Relative to `sub = root + 0x1DC`:

```text
sub + 0x00 .. +0x57   88 x u8  prize/unlock states
sub + 0x58 .. +0x68    9 x u16 per-world normal Coin counts
sub + 0x69              1 byte  padding/unknown
sub + 0x6A .. +0x84   27 x u8  Barker Coin per-hole collected flags
sub + 0x85              1 x u8  Barker Coin total
sub + 0x86 .. +0xA0   27 x u8  Par Club Piece flags
sub + 0xA1              1 x u8  dirty/changed flag
```

Root-relative equivalents:

```text
root + 0x1DC .. +0x233   88 prize/unlock states
root + 0x234 .. +0x244    9 world Coin counts
root + 0x246 .. +0x260   27 Barker flags
root + 0x261              Barker total
root + 0x262 .. +0x27C   27 Par Club Pieces
root + 0x27D              dirty flag
```

Example absolute addresses from the confirmed dump:

```text
Prize states     0x8094E908 .. 0x8094E95F
World Coins      0x8094E960 .. 0x8094E970
Barker flags     0x8094E972 .. 0x8094E98C
Barker total     0x8094E98D
Par pieces       0x8094E98E .. 0x8094E9A8
Dirty            0x8094E9A9
```

---

# 4. World order

| Index | World |
| --- | --- |
| 0 | Rah's Revenge |
| 1 | Spook-o-Rama |
| 2 | Amazeon |
| 3 | King's Court |
| 4 | Wild West |
| 5 | Prehistoria |
| 6 | Barn Yard |
| 7 | Pirate's Delight |
| 8 | Fairytella |

---

# 5. All 27 normal holes

| Hole ID | World | Slot | Hole name |
| --- | --- | --- | --- |
| 0 | Rah's Revenge | A | Sky City |
| 1 | Rah's Revenge | B | Egyptian Way |
| 2 | Rah's Revenge | C | That Sphinx |
| 3 | Spook-o-Rama | A | Old Toothy |
| 4 | Spook-o-Rama | B | Devil's Brew |
| 5 | Spook-o-Rama | C | Windy Lane |
| 6 | Amazeon | A | Going Tribal |
| 7 | Amazeon | B | Big Mouth Juju |
| 8 | Amazeon | C | Rickety Ride |
| 9 | King's Court | A | Crooked Walk |
| 10 | King's Court | B | Knight's Gauntlet |
| 11 | King's Court | C | Castle Siege |
| 12 | Wild West | A | Old #7 |
| 13 | Wild West | B | Dynamite |
| 14 | Wild West | C | Gunslinger |
| 15 | Prehistoria | A | Pterodactyl's Roost |
| 16 | Prehistoria | B | Dino-Mite |
| 17 | Prehistoria | C | Magma Madness |
| 18 | Barn Yard | A | Hog Heaven |
| 19 | Barn Yard | B | Egghead |
| 20 | Barn Yard | C | Old McDoogle |
| 21 | Pirate's Delight | A | Skull Isle |
| 22 | Pirate's Delight | B | Pirate's Crossing |
| 23 | Pirate's Delight | C | Deck Hand |
| 24 | Fairytella | A | Downhill Slide |
| 25 | Fairytella | B | Troll Bridge |
| 26 | Fairytella | C | Flower Power |


## Location-design rule

There is currently **no agreed separate generic Hole Complete location**. Normal-hole check families are:

- Par Club Piece = par-or-better check
- optional Hole-in-One
- optional Barker Coin collectible
- goal evaluation

Do not create a duplicate `- Par` location beside `- Par Club Piece`.

---

# 6. Normal world Coin counts

```python
coins = read_u16_be(sub + 0x58 + world_index * 2)
```

Confirmed as Coin Counts. A previously suspicious value `21012` was manually written by the user while testing and is not a natural game value.


| World | Example address |
| --- | --- |
| Rah's Revenge | `0x8094E960` |
| Spook-o-Rama | `0x8094E962` |
| Amazeon | `0x8094E964` |
| King's Court | `0x8094E966` |
| Wild West | `0x8094E968` |
| Prehistoria | `0x8094E96A` |
| Barn Yard | `0x8094E96C` |
| Pirate's Delight | `0x8094E96E` |
| Fairytella | `0x8094E970` |


Relevant code:

- `0x800D6134` normal world Coin / Barker total getter
- `0x800D61A8` normal world Coin modifier + dirty

---

# 7. Barker Coins

## 7.1 Per-hole Barker flags

```python
barker_collected = read_u8(sub + 0x6A + hole_id)  # hole_id 0..26
```

Use the 27-hole table above for names.

Relevant code: `0x800D622C` sets the per-hole flag, increments Barker total, and marks state dirty.

## 7.2 Barker total

```python
barker_total = read_u8(sub + 0x85)
```

Example `0x8094E98D` in the confirmed dump.

## 7.3 Two different AP Barker modes

### Spendable mode

Used when Barker Coins are not a goal/progression counter. Each AP-received Barker Coin is granted **once**:

```python
game_barker_total += 1
```

Track processed receive index/count so reconnect does not duplicate grants. Coins may be spent in Barker Shop.

### AP-owned counter/progression mode

Used when:

- Goal = Barker Coin Hunt, or
- Barker Coins gate the final/Goal World

Then:

```python
desired_barker_total = received_AP_Barker_Coin_item_count
```

The client may reassert the total. It is not spendable progression currency.

**Barker Shop Checks must be forced OFF in this mode.** Otherwise spending + re-sync can create free/repeat shop purchases or destroy the goal counter.

---

# 8. Par Club Pieces = Par checks

The 27 bytes are the Par-or-better locations:

```python
piece = read_u8(sub + 0x86 + hole_id)
```

Recommended names:

```text
Sky City - Par Club Piece
...
Flower Power - Par Club Piece
```

Relevant code:

- `0x800D626C` counts a 3-piece world group
- `0x800D62E4` writes a Par Club Piece and dirty flag

---

# 9. Live golf detection

## Current strokes

```python
strokes = read_u32_be(root + 0x2DC)
```

## In-goal

```python
hole_state = read_u32_be(root + 0x19C)
in_goal = read_u8(hole_state + 0x127)
goal_edge = previous_in_goal == 0 and in_goal == 1
```

## Current par

```python
hole_def = read_u32_be(manager + 0x10C)
par = read_u32_be(hole_def + 0x0C)
```

The game's own Par Club logic is `strokes <= par`.

## Normal-hole context ID

```python
course_context = read_u32_be(session + 0x2F0)
```

For normal golf this matched IDs `0..26`; Deck Hand was observed as 23.

**Do not use this as a generic minigame ID.** The earlier 27..35 minigame-ID hypothesis was disproven.

## HIO

```python
if goal_edge and 0 <= hole_id < 27 and strokes == 1:
    send_hio_location(hole_id)
```

## Par Club Piece

```python
if goal_edge and 0 <= hole_id < 27 and strokes <= par:
    send_par_piece_location(hole_id)
```

Persistent Par Club flags remain the reconnect-safe source of truth.

---

# 10. 88 prize/unlock state bytes

```python
state = read_u8(sub + prize_id)  # prize_id 0..87
active = state == 1
```

The game checks **exactly `== 1`**.

New activation detection:

```python
if previous_state != 1 and current_state == 1:
    send_location(...)
```

Do not require `0 -> 1`:

- Fairytella Secret live-observed `0 -> 1`
- Pirate's Delight Secret live-observed `2 -> 1`

Breakdown:

```text
63 normal world-Coin shop purchases
 7 Barker Shop purchases
 9 World Map Secrets
 9 Par Club completion rewards / Clubs
88 total
```

Relevant code:

- `0x800D60A8` initializes/resets state region
- `0x800D6AFC` ownership test (`==1`)
- `0x800D6B2C` acquisition-type lookup
- `0x800D6B44`, `0x800D6B78` price/requirement helpers
- `0x800D6BC0` generic acquire/purchase
- `0x800D71A8..0x800D71B0` set owned=1 and dirty=1

---

# 11. Runtime prize-definition table

Base `0x80547184`, 88 parallel entries:

```text
+0x000 : 88 x u32 category/metadata
+0x160 : 88 x u32 acquisition/type
+0x2C0 : 88 x u16 price/requirement
+0x370 : 88 x u8  theme/world
+0x3C8 : 88 x u8  aux/subcategory
+0x420 : 88 x u32 string ptr array 1
+0x580 : 88 x u32 string ptr array 2
+0x6E0 : 88 x u32 string ptr array 3
+0x840 : 88 x u32 localization/prize-key ptr
```

Types:

```text
0/1/2 = normal per-world Coin purchase
3     = Barker Coin purchase
4     = World Map Secret
5     = Par Club completion reward / Club
```

---

# 12. Exact mapping of all 88 prize/unlock entries


| ID | Display name | World/source | Category | Acquire type | Price/req. | Flag | Example addr | Internal key |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | G-Nome Outfit | Fairytella | Skin/Outfit | World Coins (SM) | 300 | `sub+0x00` | `0x8094E908` | prize_select_fairy |
| 1 | Candy Striped Ball | Fairytella | Golf Ball | World Coins (MD) | 50 | `sub+0x01` | `0x8094E909` | prize_select_fairy |
| 2 | Human G-Nome | Fairytella | Toy/Character | World Coins (LG) | 205 | `sub+0x02` | `0x8094E90A` | prize_gnome |
| 3 | Delicious Cupcake | Fairytella | Toy/Character | World Coins (SM) | 75 | `sub+0x03` | `0x8094E90B` | prize_cupcake |
| 4 | G-Nome Hat | Fairytella | Joint/Accessory | World Coins (MD) | 233 | `sub+0x04` | `0x8094E90C` | prize_gnome_hat |
| 5 | G-Nome Shoes | Fairytella | Joint/Accessory | World Coins (LG) | 175 | `sub+0x05` | `0x8094E90D` | prize_gnome_shoes |
| 6 | Falling Star Club | Fairytella | Club | Par Club Reward | 0 | `sub+0x06` | `0x8094E90E` | prize_select_fairy |
| 7 | G-Nome Necklace | Fairytella | Joint/Accessory | World Coins (SM) | 299 | `sub+0x07` | `0x8094E90F` | prize_gnome_necklace |
| 8 | Prehistoric Outfit | Prehistoria | Skin/Outfit | World Coins (SM) | 425 | `sub+0x08` | `0x8094E910` | prize_select_dino |
| 9 | Lava Ball | Prehistoria | Golf Ball | World Coins (MD) | 50 | `sub+0x09` | `0x8094E911` | prize_select_dino |
| 10 | Leaping Lizard | Prehistoria | Toy/Character | World Coins (LG) | 75 | `sub+0x0A` | `0x8094E912` | prize_dino_tri |
| 11 | Wacko | Prehistoria | Toy/Character | World Coins (SM) | 50 | `sub+0x0B` | `0x8094E913` | prize_wacco |
| 12 | Raptor Mask | Prehistoria | Joint/Accessory | World Coins (MD) | 250 | `sub+0x0C` | `0x8094E914` | prize_raptor_mask |
| 13 | Dino Tail | Prehistoria | Joint/Accessory | World Coins (LG) | 100 | `sub+0x0D` | `0x8094E915` | prize_dino_tail |
| 14 | Tooth Club | Prehistoria | Club | Par Club Reward | 0 | `sub+0x0E` | `0x8094E916` | prize_select_dino |
| 15 | Bonehead | Prehistoria | Joint/Accessory | World Coins (SM) | 387 | `sub+0x0F` | `0x8094E917` | prize_bonehead |
| 16 | Overalls | Barn Yard | Skin/Outfit | World Coins (SM) | 200 | `sub+0x10` | `0x8094E918` | prize_select_farm |
| 17 | Egg Ball | Barn Yard | Golf Ball | World Coins (MD) | 40 | `sub+0x11` | `0x8094E919` | prize_select_farm |
| 18 | Gizzard | Barn Yard | Toy/Character | World Coins (LG) | 60 | `sub+0x12` | `0x8094E91A` | prize_chicken |
| 19 | Pitchfork of Celebration | Barn Yard | Toy/Character | World Coins (SM) | 187 | `sub+0x13` | `0x8094E91B` | prize_pitchfork |
| 20 | Moo Mask | Barn Yard | Joint/Accessory | World Coins (MD) | 450 | `sub+0x14` | `0x8094E91C` | prize_moo_mask |
| 21 | Curly Cue | Barn Yard | Joint/Accessory | World Coins (LG) | 150 | `sub+0x15` | `0x8094E91D` | prize_curly |
| 22 | Hay Club | Barn Yard | Club | Par Club Reward | 0 | `sub+0x16` | `0x8094E91E` | prize_select_farm |
| 23 | Bullhorn | Barn Yard | Joint/Accessory | World Coins (SM) | 250 | `sub+0x17` | `0x8094E91F` | prize_bullhorn |
| 24 | Pirate Outfit | Pirate's Delight | Skin/Outfit | World Coins (SM) | 275 | `sub+0x18` | `0x8094E920` | prize_select_pirate |
| 25 | Cannon Ball | Pirate's Delight | Golf Ball | World Coins (MD) | 80 | `sub+0x19` | `0x8094E921` | prize_select_pirate |
| 26 | Dem Bones | Pirate's Delight | Toy/Character | World Coins (LG) | 125 | `sub+0x1A` | `0x8094E922` | prize_dem_bones |
| 27 | Pirates Booty | Pirate's Delight | Toy/Character | World Coins (SM) | 50 | `sub+0x1B` | `0x8094E923` | prize_chest |
| 28 | Der Be Pirate | Pirate's Delight | Joint/Accessory | World Coins (MD) | 390 | `sub+0x1C` | `0x8094E924` | prize_derby_pirate |
| 29 | Jolly Roger Cap | Pirate's Delight | Joint/Accessory | World Coins (LG) | 227 | `sub+0x1D` | `0x8094E925` | prize_jolly_cap |
| 30 | Anchor Club | Pirate's Delight | Club | Par Club Reward | 0 | `sub+0x1E` | `0x8094E926` | prize_select_pirate |
| 31 | Swashbuckla | Pirate's Delight | Joint/Accessory | World Coins (SM) | 190 | `sub+0x1F` | `0x8094E927` | prize_sword |
| 32 | Medieval Outfit | King's Court | Skin/Outfit | World Coins (SM) | 342 | `sub+0x20` | `0x8094E928` | prize_select_castle |
| 33 | Mace Ball | King's Court | Golf Ball | World Coins (MD) | 45 | `sub+0x21` | `0x8094E929` | prize_select_castle |
| 34 | The Cat Jester | King's Court | Toy/Character | World Coins (LG) | 150 | `sub+0x22` | `0x8094E92A` | prize_cat_jester |
| 35 | Dag-gone Dra-gone | King's Court | Toy/Character | World Coins (SM) | 125 | `sub+0x23` | `0x8094E92B` | prize_dragon |
| 36 | Royal Crown | King's Court | Joint/Accessory | World Coins (MD) | 325 | `sub+0x24` | `0x8094E92C` | prize_royal_crown |
| 37 | Mr. Shield | King's Court | Joint/Accessory | World Coins (LG) | 200 | `sub+0x25` | `0x8094E92D` | prize_shield |
| 38 | Knight Club | King's Court | Club | Par Club Reward | 0 | `sub+0x26` | `0x8094E92E` | prize_select_castle |
| 39 | Boots-O-Armor | King's Court | Joint/Accessory | World Coins (SM) | 150 | `sub+0x27` | `0x8094E92F` | prize_armor_boots |
| 40 | Sheriff Outfit | Wild West | Skin/Outfit | World Coins (SM) | 197 | `sub+0x28` | `0x8094E930` | prize_select_ww |
| 41 | Tumbleweed Ball | Wild West | Golf Ball | World Coins (MD) | 75 | `sub+0x29` | `0x8094E931` | prize_select_ww |
| 42 | Cowbot | Wild West | Toy/Character | World Coins (LG) | 250 | `sub+0x2A` | `0x8094E932` | prize_cowbot |
| 43 | Chuck Wagon | Wild West | Toy/Character | World Coins (SM) | 90 | `sub+0x2B` | `0x8094E933` | prize_wagon |
| 44 | Bandito Scarf | Wild West | Joint/Accessory | World Coins (MD) | 175 | `sub+0x2C` | `0x8094E934` | prize_bandito_mask |
| 45 | Jingle Jangle Boots | Wild West | Joint/Accessory | World Coins (LG) | 150 | `sub+0x2D` | `0x8094E935` | prize_jingle_boots |
| 46 | Choo Choo Club | Wild West | Club | Par Club Reward | 0 | `sub+0x2E` | `0x8094E936` | prize_select_ww |
| 47 | 20 Gallon Hat | Wild West | Joint/Accessory | World Coins (SM) | 400 | `sub+0x2F` | `0x8094E937` | prize_20_hat |
| 48 | Egyptian Outfit | Rah's Revenge | Skin/Outfit | World Coins (SM) | 211 | `sub+0x30` | `0x8094E938` | prize_select_egypt |
| 49 | Eye of Rah Ball | Rah's Revenge | Golf Ball | World Coins (MD) | 50 | `sub+0x31` | `0x8094E939` | prize_select_egypt |
| 50 | Mummy Don't Dance | Rah's Revenge | Toy/Character | World Coins (LG) | 120 | `sub+0x32` | `0x8094E93A` | prize_mummy |
| 51 | Tut's Tomb | Rah's Revenge | Toy/Character | World Coins (SM) | 90 | `sub+0x33` | `0x8094E93B` | prize_pyramid |
| 52 | Pharaoh's Hat | Rah's Revenge | Joint/Accessory | World Coins (MD) | 489 | `sub+0x34` | `0x8094E93C` | prize_egypt_hat |
| 53 | Magic Bo Staff | Rah's Revenge | Joint/Accessory | World Coins (LG) | 143 | `sub+0x35` | `0x8094E93D` | prize_bo_staff |
| 54 | Scepter Club | Rah's Revenge | Club | Par Club Reward | 0 | `sub+0x36` | `0x8094E93E` | prize_select_egypt |
| 55 | Ramses Mask | Rah's Revenge | Joint/Accessory | World Coins (SM) | 234 | `sub+0x37` | `0x8094E93F` | prize_egypt_mask |
| 56 | Skeleton Outfit | Spook-o-Rama | Skin/Outfit | World Coins (SM) | 345 | `sub+0x38` | `0x8094E940` | prize_select_spooky |
| 57 | Eye Ball | Spook-o-Rama | Golf Ball | World Coins (MD) | 90 | `sub+0x39` | `0x8094E941` | prize_select_spooky |
| 58 | Jack being Nimble | Spook-o-Rama | Toy/Character | World Coins (LG) | 150 | `sub+0x3A` | `0x8094E942` | prize_jack |
| 59 | Baseball Bat | Spook-o-Rama | Toy/Character | World Coins (SM) | 23 | `sub+0x3B` | `0x8094E943` | prize_bat |
| 60 | Dr. Boneface | Spook-o-Rama | Joint/Accessory | World Coins (MD) | 524 | `sub+0x3C` | `0x8094E944` | prize_boneface |
| 61 | Phalange Feet | Spook-o-Rama | Joint/Accessory | World Coins (LG) | 80 | `sub+0x3D` | `0x8094E945` | prize_flangie_feet |
| 62 | Halloween Club | Spook-o-Rama | Club | Par Club Reward | 0 | `sub+0x3E` | `0x8094E946` | prize_select_spooky |
| 63 | Bad Hair Day | Spook-o-Rama | Joint/Accessory | World Coins (SM) | 125 | `sub+0x3F` | `0x8094E947` | prize_hair |
| 64 | Safari Outfit | Amazeon | Skin/Outfit | World Coins (SM) | 300 | `sub+0x40` | `0x8094E948` | prize_select_amazon |
| 65 | Jub Jub Ball | Amazeon | Golf Ball | World Coins (MD) | 25 | `sub+0x41` | `0x8094E949` | prize_select_amazon |
| 66 | Intel-a-gator | Amazeon | Toy/Character | World Coins (LG) | 75 | `sub+0x42` | `0x8094E94A` | prize_gator |
| 67 | Der Sausage Monkey | Amazeon | Toy/Character | World Coins (SM) | 110 | `sub+0x43` | `0x8094E94B` | prize_der_monkey |
| 68 | Adventure Cap | Amazeon | Joint/Accessory | World Coins (MD) | 100 | `sub+0x44` | `0x8094E94C` | prize_adv_hat |
| 69 | Jungle Foot | Amazeon | Joint/Accessory | World Coins (LG) | 475 | `sub+0x45` | `0x8094E94D` | prize_jungle_foot |
| 70 | Voodoo Club | Amazeon | Club | Par Club Reward | 0 | `sub+0x46` | `0x8094E94E` | prize_select_amazon |
| 71 | Tiki Mask | Amazeon | Joint/Accessory | World Coins (SM) | 252 | `sub+0x47` | `0x8094E94F` | prize_tiki_face |
| 72 | Barker Outfit | Barker Shop | Skin/Outfit | Barker Coins | 4 | `sub+0x48` | `0x8094E950` | prize_select_barker |
| 73 | Barker Ball | Barker Shop | Golf Ball | Barker Coins | 4 | `sub+0x49` | `0x8094E951` | prize_select_barker |
| 74 | Derby Hat | Barker Shop | Joint/Accessory | Barker Coins | 4 | `sub+0x4A` | `0x8094E952` | prize_select_barker |
| 75 | Barker Mustache | Barker Shop | Joint/Accessory | Barker Coins | 4 | `sub+0x4B` | `0x8094E953` | prize_select_barker |
| 76 | Barker Bowtie | Barker Shop | Joint/Accessory | Barker Coins | 4 | `sub+0x4C` | `0x8094E954` | prize_select_barker |
| 77 | Barker Shoes | Barker Shop | Joint/Accessory | Barker Coins | 3 | `sub+0x4D` | `0x8094E955` | prize_select_barker |
| 78 | Cane Club | Barker Shop | Club | Barker Coins | 4 | `sub+0x4E` | `0x8094E956` | prize_select_barker |
| 79 | Samurai Face | Wild West | Joint/Accessory | World Map Secret | 50 | `sub+0x4F` | `0x8094E957` | prize_sam_face |
| 80 | Florence Mask | Rah's Revenge | Joint/Accessory | World Map Secret | 50 | `sub+0x50` | `0x8094E958` | prize_florence |
| 81 | Cupid Wings | Barn Yard | Joint/Accessory | World Map Secret | 50 | `sub+0x51` | `0x8094E959` | prize_cupid_wings |
| 82 | Dragon Wings | Spook-o-Rama | Joint/Accessory | World Map Secret | 50 | `sub+0x52` | `0x8094E95A` | prize_dragon_wings |
| 83 | Monkey-On-My-Back | Amazeon | Joint/Accessory | World Map Secret | 50 | `sub+0x53` | `0x8094E95B` | prize_back_monkey |
| 84 | Lion Paws | Prehistoria | Joint/Accessory | World Map Secret | 50 | `sub+0x54` | `0x8094E95C` | prize_roar_paws |
| 85 | Rainbow Shoes | King's Court | Joint/Accessory | World Map Secret | 50 | `sub+0x55` | `0x8094E95D` | prize_rainbow_shoes |
| 86 | Sunday Shoes | Fairytella | Joint/Accessory | World Map Secret | 50 | `sub+0x56` | `0x8094E95E` | prize_sundae_shoes |
| 87 | Sharkster Shoes | Pirate's Delight | Joint/Accessory | World Map Secret | 50 | `sub+0x57` | `0x8094E95F` | prize_shark_shoes |

---

# 13. Normal Pro Shop logic


YAML option:

```text
Shop Checks: Off / On
Default: On
```

Agreed logic for each world's 7 normal world-Coin purchases, sorted cheapest -> most expensive:

```text
0/3 Par Club Pieces -> cheapest 2 in logic
1/3                  -> cheapest 4 in logic
2/3                  -> cheapest 6 in logic
3/3                  -> all 7 in logic
3/3                  -> that world's Club/Par reward also in logic
```

This deliberately keeps expensive shop checks **out of logic** until enough progress in that world.

## Exact per-world purchase order and logic tier


### Rah's Revenge

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Eye of Rah Ball | 50 | Golf Ball | 49 | `sub+0x31` | 0/3 pieces |
| 2 | Tut's Tomb | 90 | Toy/Character | 51 | `sub+0x33` | 0/3 pieces |
| 3 | Mummy Don't Dance | 120 | Toy/Character | 50 | `sub+0x32` | >=1/3 pieces |
| 4 | Magic Bo Staff | 143 | Joint/Accessory | 53 | `sub+0x35` | >=1/3 pieces |
| 5 | Egyptian Outfit | 211 | Skin/Outfit | 48 | `sub+0x30` | >=2/3 pieces |
| 6 | Ramses Mask | 234 | Joint/Accessory | 55 | `sub+0x37` | >=2/3 pieces |
| 7 | Pharaoh's Hat | 489 | Joint/Accessory | 52 | `sub+0x34` | 3/3 pieces |

Club/Par reward at **3/3**: **Scepter Club** (ID 54, `sub+0x36`).


### Spook-o-Rama

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Baseball Bat | 23 | Toy/Character | 59 | `sub+0x3B` | 0/3 pieces |
| 2 | Phalange Feet | 80 | Joint/Accessory | 61 | `sub+0x3D` | 0/3 pieces |
| 3 | Eye Ball | 90 | Golf Ball | 57 | `sub+0x39` | >=1/3 pieces |
| 4 | Bad Hair Day | 125 | Joint/Accessory | 63 | `sub+0x3F` | >=1/3 pieces |
| 5 | Jack being Nimble | 150 | Toy/Character | 58 | `sub+0x3A` | >=2/3 pieces |
| 6 | Skeleton Outfit | 345 | Skin/Outfit | 56 | `sub+0x38` | >=2/3 pieces |
| 7 | Dr. Boneface | 524 | Joint/Accessory | 60 | `sub+0x3C` | 3/3 pieces |

Club/Par reward at **3/3**: **Halloween Club** (ID 62, `sub+0x3E`).


### Amazeon

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Jub Jub Ball | 25 | Golf Ball | 65 | `sub+0x41` | 0/3 pieces |
| 2 | Intel-a-gator | 75 | Toy/Character | 66 | `sub+0x42` | 0/3 pieces |
| 3 | Adventure Cap | 100 | Joint/Accessory | 68 | `sub+0x44` | >=1/3 pieces |
| 4 | Der Sausage Monkey | 110 | Toy/Character | 67 | `sub+0x43` | >=1/3 pieces |
| 5 | Tiki Mask | 252 | Joint/Accessory | 71 | `sub+0x47` | >=2/3 pieces |
| 6 | Safari Outfit | 300 | Skin/Outfit | 64 | `sub+0x40` | >=2/3 pieces |
| 7 | Jungle Foot | 475 | Joint/Accessory | 69 | `sub+0x45` | 3/3 pieces |

Club/Par reward at **3/3**: **Voodoo Club** (ID 70, `sub+0x46`).


### King's Court

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Mace Ball | 45 | Golf Ball | 33 | `sub+0x21` | 0/3 pieces |
| 2 | Dag-gone Dra-gone | 125 | Toy/Character | 35 | `sub+0x23` | 0/3 pieces |
| 3 | The Cat Jester | 150 | Toy/Character | 34 | `sub+0x22` | >=1/3 pieces |
| 4 | Boots-O-Armor | 150 | Joint/Accessory | 39 | `sub+0x27` | >=1/3 pieces |
| 5 | Mr. Shield | 200 | Joint/Accessory | 37 | `sub+0x25` | >=2/3 pieces |
| 6 | Royal Crown | 325 | Joint/Accessory | 36 | `sub+0x24` | >=2/3 pieces |
| 7 | Medieval Outfit | 342 | Skin/Outfit | 32 | `sub+0x20` | 3/3 pieces |

Club/Par reward at **3/3**: **Knight Club** (ID 38, `sub+0x26`).


### Wild West

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Tumbleweed Ball | 75 | Golf Ball | 41 | `sub+0x29` | 0/3 pieces |
| 2 | Chuck Wagon | 90 | Toy/Character | 43 | `sub+0x2B` | 0/3 pieces |
| 3 | Jingle Jangle Boots | 150 | Joint/Accessory | 45 | `sub+0x2D` | >=1/3 pieces |
| 4 | Bandito Scarf | 175 | Joint/Accessory | 44 | `sub+0x2C` | >=1/3 pieces |
| 5 | Sheriff Outfit | 197 | Skin/Outfit | 40 | `sub+0x28` | >=2/3 pieces |
| 6 | Cowbot | 250 | Toy/Character | 42 | `sub+0x2A` | >=2/3 pieces |
| 7 | 20 Gallon Hat | 400 | Joint/Accessory | 47 | `sub+0x2F` | 3/3 pieces |

Club/Par reward at **3/3**: **Choo Choo Club** (ID 46, `sub+0x2E`).


### Prehistoria

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Lava Ball | 50 | Golf Ball | 9 | `sub+0x09` | 0/3 pieces |
| 2 | Wacko | 50 | Toy/Character | 11 | `sub+0x0B` | 0/3 pieces |
| 3 | Leaping Lizard | 75 | Toy/Character | 10 | `sub+0x0A` | >=1/3 pieces |
| 4 | Dino Tail | 100 | Joint/Accessory | 13 | `sub+0x0D` | >=1/3 pieces |
| 5 | Raptor Mask | 250 | Joint/Accessory | 12 | `sub+0x0C` | >=2/3 pieces |
| 6 | Bonehead | 387 | Joint/Accessory | 15 | `sub+0x0F` | >=2/3 pieces |
| 7 | Prehistoric Outfit | 425 | Skin/Outfit | 8 | `sub+0x08` | 3/3 pieces |

Club/Par reward at **3/3**: **Tooth Club** (ID 14, `sub+0x0E`).


### Barn Yard

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Egg Ball | 40 | Golf Ball | 17 | `sub+0x11` | 0/3 pieces |
| 2 | Gizzard | 60 | Toy/Character | 18 | `sub+0x12` | 0/3 pieces |
| 3 | Curly Cue | 150 | Joint/Accessory | 21 | `sub+0x15` | >=1/3 pieces |
| 4 | Pitchfork of Celebration | 187 | Toy/Character | 19 | `sub+0x13` | >=1/3 pieces |
| 5 | Overalls | 200 | Skin/Outfit | 16 | `sub+0x10` | >=2/3 pieces |
| 6 | Bullhorn | 250 | Joint/Accessory | 23 | `sub+0x17` | >=2/3 pieces |
| 7 | Moo Mask | 450 | Joint/Accessory | 20 | `sub+0x14` | 3/3 pieces |

Club/Par reward at **3/3**: **Hay Club** (ID 22, `sub+0x16`).


### Pirate's Delight

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Pirates Booty | 50 | Toy/Character | 27 | `sub+0x1B` | 0/3 pieces |
| 2 | Cannon Ball | 80 | Golf Ball | 25 | `sub+0x19` | 0/3 pieces |
| 3 | Dem Bones | 125 | Toy/Character | 26 | `sub+0x1A` | >=1/3 pieces |
| 4 | Swashbuckla | 190 | Joint/Accessory | 31 | `sub+0x1F` | >=1/3 pieces |
| 5 | Jolly Roger Cap | 227 | Joint/Accessory | 29 | `sub+0x1D` | >=2/3 pieces |
| 6 | Pirate Outfit | 275 | Skin/Outfit | 24 | `sub+0x18` | >=2/3 pieces |
| 7 | Der Be Pirate | 390 | Joint/Accessory | 28 | `sub+0x1C` | 3/3 pieces |

Club/Par reward at **3/3**: **Anchor Club** (ID 30, `sub+0x1E`).


### Fairytella

| Rank | Item | Price | Category | ID | Flag | Logic requirement |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Candy Striped Ball | 50 | Golf Ball | 1 | `sub+0x01` | 0/3 pieces |
| 2 | Delicious Cupcake | 75 | Toy/Character | 3 | `sub+0x03` | 0/3 pieces |
| 3 | G-Nome Shoes | 175 | Joint/Accessory | 5 | `sub+0x05` | >=1/3 pieces |
| 4 | Human G-Nome | 205 | Toy/Character | 2 | `sub+0x02` | >=1/3 pieces |
| 5 | G-Nome Hat | 233 | Joint/Accessory | 4 | `sub+0x04` | >=2/3 pieces |
| 6 | G-Nome Necklace | 299 | Joint/Accessory | 7 | `sub+0x07` | >=2/3 pieces |
| 7 | G-Nome Outfit | 300 | Skin/Outfit | 0 | `sub+0x00` | 3/3 pieces |

Club/Par reward at **3/3**: **Falling Star Club** (ID 6, `sub+0x06`).



## Coin Bundle filler items

Normal Coin Bundle filler items should fund normal Pro Shop purchases.

Receipt rule:

```text
add the bundle amount once to the relevant world's normal Coin count
set dirty if required
track receive processing so reconnect cannot duplicate currency
```

**Open handoff detail:** the exact Coin Bundle denominations/counts from the earlier design discussion are not present in the retained technical notes available for this consolidation. Do not silently invent denominations in Codex. Keep bundle-size constants isolated/configurable until those exact values are supplied/recovered.

---

# 14. Barker Shop


| ID | Item | Barker cost | Category | Flag |
| --- | --- | --- | --- | --- |
| 77 | Barker Shoes | 3 | Joint/Accessory | `sub+0x4D` |
| 72 | Barker Outfit | 4 | Skin/Outfit | `sub+0x48` |
| 73 | Barker Ball | 4 | Golf Ball | `sub+0x49` |
| 74 | Derby Hat | 4 | Joint/Accessory | `sub+0x4A` |
| 75 | Barker Mustache | 4 | Joint/Accessory | `sub+0x4B` |
| 76 | Barker Bowtie | 4 | Joint/Accessory | `sub+0x4C` |
| 78 | Cane Club | 4 | Club | `sub+0x4E` |


Separate YAML option from normal Shop Checks:

```text
Barker Shop Checks: Off / On
```

Current intended normal-mode default: On.

Hard rule:

```text
if Goal == Barker Coin Hunt
OR Barker Coins gate the Goal World:
    Barker Shop Checks = forced Off
```

---

# 15. World Map Secrets

```text
World Secrets: Off / On
Default: On
```

Activation rule: `previous != 1 && current == 1`.


| World | ID | Reward/cosmetic | Flag | Example address |
| --- | --- | --- | --- | --- |
| Rah's Revenge | 80 | Florence Mask | `sub+0x50` | `0x8094E958` |
| Spook-o-Rama | 82 | Dragon Wings | `sub+0x52` | `0x8094E95A` |
| Amazeon | 83 | Monkey-On-My-Back | `sub+0x53` | `0x8094E95B` |
| King's Court | 85 | Rainbow Shoes | `sub+0x55` | `0x8094E95D` |
| Wild West | 79 | Samurai Face | `sub+0x4F` | `0x8094E957` |
| Prehistoria | 84 | Lion Paws | `sub+0x54` | `0x8094E95C` |
| Barn Yard | 81 | Cupid Wings | `sub+0x51` | `0x8094E959` |
| Pirate's Delight | 87 | Sharkster Shoes | `sub+0x57` | `0x8094E95F` |
| Fairytella | 86 | Sunday Shoes | `sub+0x56` | `0x8094E95E` |


---

# 16. Minigames

YAML:

```text
Minigame Checks:
- Off
- Win Only
- Perfect Only
- Win + Perfect
```

Semantics:

```text
Win     = simply complete/pass minigame
Perfect = pass AND collect all minigame Coins
```

A Perfect run necessarily has Win=1. In Win+Perfect mode it sends both checks.

## Controller resolver

```python
controller = read_u32_be(session + 0xFC)
```

Fields:

```text
controller + 0x1C  VTable / identity
controller + 0x44  player root
controller + 0x11C raw live collected Coins / score
controller + 0x120 raw target / total Coins
controller + 0x130 status used by result builder
```

## Identity map


| World | Minigame | Sublogic class | VTable | Validation |
| --- | --- | --- | --- | --- |
| Rah's Revenge | Maze-O-Rama | CLabyrinthSubLogic | 0x804F3280 | static mapping |
| Spook-o-Rama | Ghoul Hunter | CSpidersSubLogic | 0x804FB868 | static mapping |
| Amazeon | Jungle Bogey | CAmazonBSubLogic | 0x804EAB00 | static mapping |
| King's Court | Juggles | CJugglingSubLogic | 0x804F29E0 | static mapping |
| Wild West | Mine Shaft Madness | dCMineCartSubLogic | 0x804F4DA8 | LIVE CONFIRMED |
| Prehistoria | Pterodactyl's Run | CRingsSubLogic | 0x804F88A8 | static mapping |
| Barn Yard | The Scrambler | CEggFarmSubLogic | 0x804ED108 | static mapping |
| Pirate's Delight | Cannon Fodder | CCatapultSubLogic | 0x804EB728 | static mapping |
| Fairytella | G-Nome Project | LCSimonSaysLogic | 0x804FB53C | static mapping |


Mine Shaft Madness is live-confirmed. The other 8 are strong static mappings from class names/resources. A second live minigame is useful QA, not a blocker.

## Result popup

```text
CMGResultsPopup VTable = 0x804F7918
```

Lookup:

```python
array = read_u32_be(manager + 0x100)
count = read_u32_be(manager + 0x104)
for i in range(count):
    obj = read_u32_be(array + i*4)
    if obj and read_u32_be(obj + 0x1C) == 0x804F7918:
        result = obj
```

Final flags:

```text
result + 0xC0 = Perfect
result + 0xC1 = Win
```

Live Perfect Mine Shaft Madness result:

```text
result = 0x809464CC
Perfect = 1
Win     = 1
controller live = 6/6 Coins
```

## +5 Perfect bonus

Observed:

```text
controller +0x11C/+0x120 = 6/6
result +0xB8/+0xBC       = 11/6
```

The extra 5 is the game's +5 Coin bonus for collecting all minigame Coins.

Interpretation:

```text
controller +0x11C = raw collected
controller +0x120 = raw target
result +0xB8      = final payout/score including +5 bonus
result +0xBC      = base target
result +0xC0      = authoritative Perfect
result +0xC1      = authoritative Win
```

Relevant code:

- `0x800F7284` result builder
- `0x800CB504` CMGResultsPopup constructor/path
- `0x800CB584..0x800CB5A0` result population / Perfect condition

---

# 17. World locks / unlock items

This is live-confirmed and essential for AP.

Per player:

```python
lock_addr = player_root + 0x2CC + world_index
```

Semantics:

```text
0       = UNLOCKED / visible / selectable
nonzero = LOCKED / hidden / disabled
```


| Index | World | Root-relative | Example address |
| --- | --- | --- | --- |
| 0 | Rah's Revenge | `root+0x2CC` | `0x8094E9F8` |
| 1 | Spook-o-Rama | `root+0x2CD` | `0x8094E9F9` |
| 2 | Amazeon | `root+0x2CE` | `0x8094E9FA` |
| 3 | King's Court | `root+0x2CF` | `0x8094E9FB` |
| 4 | Wild West | `root+0x2D0` | `0x8094E9FC` |
| 5 | Prehistoria | `root+0x2D1` | `0x8094E9FD` |
| 6 | Barn Yard | `root+0x2D2` | `0x8094E9FE` |
| 7 | Pirate's Delight | `root+0x2D3` | `0x8094E9FF` |
| 8 | Fairytella | `root+0x2D4` | `0x8094EA00` |


The user manually wrote the lock value and confirmed a world actually became hidden/locked; writing `0` restored it.

World Select around `0x80059414` reads these bytes. Nonzero uses hidden labels (`THEME_HIDDEN_NAME`, `THEME_HIDDEN_DIF`) and disabled state 7.

Vanilla unlock event `0x800CAF0C..0x800CAF1C` effectively does:

```python
root[0x2CC + world_index] = 0
```

Persistence:

```text
0x80080B20 runtime -> save: player_root+0x2CC, 9 bytes -> save+0xF0
0x800810DC save -> runtime: save+0xF0 -> player_root+0x2CC
```

Vanilla new-state initialization around `0x80080260` / `0x800803F4` first fills all 9 with 1, then clears indices 5, 6, 8.

Vanilla starter worlds:

```text
Prehistoria
Barn Yard
Fairytella
```

Later vanilla unlock helper `0x80083B34` corresponds to:

```text
Rah's Revenge -> Spook-o-Rama -> Wild West -> Pirate's Delight -> Amazeon -> King's Court
```

## AP enforcement

Prefer periodic reassertion rather than patching vanilla code:

```python
manager = read_u32_be(0x805DDD80)
count = read_u32_be(manager + 0x12C)
for p in range(count):
    root = read_u32_be(manager + 0x190 + p*4)
    for world in range(9):
        write_u8(root + 0x2CC + world, 0 if ap_unlocked(world) else 1)
```

Apply to all local players, because multiplayer World Select can consider a world available if any local player has it unlocked.

Fallback only if polling fails: revision-specific NOP of vanilla write at `0x800CAF1C` (`0x60000000`). Polling is preferred.

---

# 18. Starting World

```text
Starting World:
- Random [DEFAULT]
- Rah's Revenge
- Spook-o-Rama
- Amazeon
- King's Court
- Wild West
- Prehistoria
- Barn Yard
- Pirate's Delight
- Fairytella
```

AP startup:

1. lock all 9
2. unlock exactly chosen/generated start world
3. unlock others only through AP World Unlock items / goal-world rule

Normal mode pool:

```text
1 start world
8 World Unlock progression items
```

Do not place the start world's unlock item.

World Unlock item names:

```text
Unlock Rah's Revenge
Unlock Spook-o-Rama
Unlock Amazeon
Unlock King's Court
Unlock Wild West
Unlock Prehistoria
Unlock Barn Yard
Unlock Pirate's Delight
Unlock Fairytella
```

---

# 19. Goal design

## Goal A: All 27 Holes on Par

Victory = all 27 Par Club Piece / par-or-better checks.

Authoritative runtime condition can simply inspect all 27 Par Club Piece bytes or AP checked locations.

## Goal B: Barker Coin Hunt

Barker Coins become AP-owned progression/counter items. Barker Shop is forced Off.

Recommended surface:

```text
Goal = Barker Coin Hunt
Barker Coins Required = Range, max 27
```

The exact desired default requirement was not explicitly finalized. `27` is the natural full-hunt value, but keep the option/default isolated.

## Combined Barker requirement + final Goal World + Par finish

Agreed behavior:

```text
normal progression
-> reach Barker Coin requirement
-> final/Goal World enters logic and is physically unlocked
-> complete all 3 holes in that world on par
-> victory
```

Rules:

- Goal World != Starting World
- omit Goal World's normal World Unlock item
- normal item count becomes 7 ordinary unlock items + 1 Barker-gated Goal World + 1 starting world
- Barker Shop forced Off
- Barker total AP-owned/reasserted

Open design knob: exact Goal World selection policy (random vs selectable) was not explicitly finalized.

---

# 20. YAML / Options model

Confirmed/desired options:

```text
Starting World        Random default; all 9 selectable
Minigame Checks       Off / Win / Perfect / Win+Perfect
Hole-in-One Checks    Off default
Barker Coin Checks    configurable
World Secrets         On default
Shop Checks           On default
Barker Shop Checks    separate option; forced Off in Barker-counter goal modes
Goal                  All 27 Holes on Par / Barker Coin Hunt
Barker goal-world requirement can combine with Par goal
```

Recommended code shape:

```python
StartingWorld(Choice)
MinigameChecks(Choice)
HoleInOneChecks(Toggle)
BarkerCoinChecks(Toggle)
WorldSecrets(Toggle)
ShopChecks(Toggle)
BarkerShopChecks(Toggle)
Goal(Choice)
BarkerGoalWorldRequirement(Toggle)
BarkerCoinsRequired(Range)
```

Explicit defaults:

```text
Starting World = Random
HIO            = Off
Secrets        = On
Shop Checks    = On
```

Defaults not explicitly locked down in retained notes and should remain easy to change:

```text
Minigame Checks default
Barker Coin Checks default
Goal default
Barker Coins Required default
Goal World selection policy
Coin Bundle denominations
```

---

# 21. Location count model

Current families:

```text
27  Par Club Piece checks                    core
27  Barker Coin checks                       optional
27  Hole-in-One checks                       optional
 9  World Secrets                            optional
0/9/9/18 Minigame checks                     by option
63  normal world-Coin shop purchases         if Shop Checks
 9  Par Club reward/Club prize checks        with final shop tier
 7  Barker Shop purchases                    if Barker Shop Checks
```

Maximum with all compatible checks and Barker Shop allowed:

```text
187 locations
```

Do not generate the 7 Barker Shop locations in Barker-counter modes.

---

# 22. Region / rule model

Conceptual graph:

```text
Start/Menu
  -> Starting World
  -> each other World through its Unlock item
  -> optional Goal World through Barker requirement
```

A World region contains its enabled checks:

```text
3 Par Club Pieces
optional 3 Barker Coins
optional 3 HIOs
optional 1 Secret
optional Minigame Win/Perfect
optional shop locations
optional Club reward at 3/3 Par pieces
```

Normal shop rule tiers per world:

```text
rank 1-2 require world access
rank 3-4 require >=1/3 Par pieces
rank 5-6 require >=2/3 Par pieces
rank 7   require 3/3 Par pieces
Club reward requires 3/3 Par pieces
```

This is the agreed answer to “which shop items are in/out of logic and until when”.

---

# 23. Client receive behavior

## World Unlock

Add to AP-owned unlocked-world set. Periodic world-lock enforcement updates RAM.

## Normal Coin Bundle

Add the bundle amount once to its world Coin count. Track received-item progress to avoid reconnect duplication.

## Barker Coin, spendable mode

Add +1 once; player may spend it.

## Barker Coin, AP-owned counter mode

Set/reassert Barker total from received Barker progression-item count. Barker Shop forced Off.

## Persistent prize state write, if ever intentionally granted

```python
write_u8(sub + prize_id, 1)
write_u8(sub + 0xA1, 1)
```

---

# 24. Dirty/save flag

```python
dirty = sub + 0xA1
```

Set to 1 after intentional client changes that need saving.

Observed as 1 after state changes and 0 after restart/load while persistent data remained saved.

---

# 25. Suggested client polling state

Cache:

```text
previous_in_goal
previous_prize_states[88]
previous_barker_flags[27]
previous_par_piece_flags[27]
last_seen_result_object
processed_received_item_index
AP_unlocked_world_set
```

High-level loop:

```text
resolve manager/session/root safely
reassert AP world locks
read persistent state and send new persistent checks
handle normal-golf in_goal edge / HIO if enabled
identify minigame from controller VTable
scan manager objects for new CMGResultsPopup
send enabled Win/Perfect checks
reassert Barker counter if in AP-owned counter mode
```

AP server de-duplicates checks, but the client should still avoid deliberate per-frame spam.

---

# 26. Recommended names

Normal holes:

```text
Sky City - Par Club Piece
Sky City - Barker Coin
Sky City - Hole-in-One
```

Minigames:

```text
Maze-O-Rama - Win
Maze-O-Rama - Perfect
...
G-Nome Project - Win
G-Nome Project - Perfect
```

Do not create duplicate `Hole - Par` locations.

---

# 27. Pro Shop static/code notes

Useful data/strings around `0x804F98D0` include:

```text
ButG_Tabs
BUT_Egypt / BUT_Spooky / BUT_Amazon / ...
BUT_Barker
ProShopBarker
BUT_CLUB / clubPrice
BUT_BALL / ballPrice
BUT_HAT / hatPrice
BUT_MASK / maskPrice
BUT_OUTFIT / outfitPrice
BUT_SHOES / shoesPrice
BUT_BACK / backPrice
UI_CLUB_PIECES
COINS / COIN
```

Main Pro Shop code: roughly `0x800DAC88..0x800E08xx`.

Ownership-check callers observed around:

```text
0x800DC464
0x800DC7AC
0x800E07D4
```

---

# 28. Important code-address index


| Address | Meaning |
| --- | --- |
| 0x80059414 | World Select reads world lock state |
| 0x80080260 / 0x800803F4 | world-lock init |
| 0x80080B20 | world locks runtime -> save |
| 0x800810DC | world locks save -> runtime |
| 0x80083B34 | vanilla unlock mapping/helper |
| 0x80082F64 | generic stat/collectible dispatcher; Barker special path |
| 0x800CADCC | event dispatcher used in Barker path |
| 0x800CAF0C..0x800CAF1C | vanilla world unlock writes 0 |
| 0x800D60A8 | prize-state initialization |
| 0x800D6134 | Coin/Barker total getter |
| 0x800D61A8 | world Coin modifier |
| 0x800D622C | Barker collection |
| 0x800D626C | count 3-piece Par group |
| 0x800D62E4 | write Par Club Piece |
| 0x800D6AFC | owned-state check |
| 0x800D6B2C | prize acquisition type |
| 0x800D6B44 / 0x800D6B78 | price helpers |
| 0x800D6BC0 | generic acquire/purchase |
| 0x800D71A8..0x800D71B0 | set owned + dirty |
| 0x800DAC88..0x800E08xx | Pro Shop code area |
| 0x800F7284 | minigame result builder |
| 0x800CB504 | CMGResultsPopup path |
| 0x800CB584..0x800CB5A0 | result Win/Perfect population |


---

# 29. Static VTables/constants

```text
CMGResultsPopup             0x804F7918
CLabyrinthSubLogic          0x804F3280  Maze-O-Rama
CSpidersSubLogic            0x804FB868  Ghoul Hunter
CAmazonBSubLogic            0x804EAB00  Jungle Bogey
CJugglingSubLogic           0x804F29E0  Juggles
dCMineCartSubLogic          0x804F4DA8  Mine Shaft Madness [LIVE]
CRingsSubLogic              0x804F88A8  Pterodactyl's Run
CEggFarmSubLogic            0x804ED108  The Scrambler
CCatapultSubLogic           0x804EB728  Cannon Fodder
LCSimonSaysLogic            0x804FB53C  G-Nome Project
```

---

# 30. Pointer safety

Validate manager/session/root/controller/object-list pointers before use. Menus/loading may temporarily lack gameplay objects. Skip a poll rather than dereferencing stale/null pointers.

---

# 31. Generation/fill safety rules

1. Starting World must be immediately reachable.
2. Do not place its unlock item.
3. Barker-gated Goal World must differ from Starting World.
4. Omit Goal World's normal unlock item if Barker count unlocks it.
5. Ensure enough Barker progression items are obtainable before Goal World.
6. Respect 2/4/6/7+Club shop logic tiers.
7. If Barker Shop is forced Off, remove those 7 locations from generation, not merely client detection.
8. Option-disabled checks should not be generated.
9. Perfect-only mode should not generate a Win location.
10. Coin Bundle filler economy should not silently become required progression unless modeled in logic.

---

# 32. Goal completion

## All 27 Holes on Par

```python
all(read_u8(sub + 0x86 + i) == 1 for i in range(27))
```

or all 27 AP Par Club Piece locations checked.

## Barker Coin Hunt

Use AP received progression count vs configured requirement, not spendable local shop balance.

## Barker-gated Goal World

```text
received Barker count >= requirement -> add Goal World to AP unlocked set
all 3 Goal World Par Club Pieces -> victory
```

---

# 33. What NOT to do

- do not hardcode `0x8094E9xx` addresses as permanent
- do not treat any nonzero prize byte as owned
- do not require Secret `0->1`; use `!=1 -> 1`
- do not use the disproven minigame ID 27..35 theory
- do not infer Perfect from final payout fields; use `result+0xC0`
- do not enable Barker Shop while Barker total is an AP-owned goal counter
- do not let vanilla world unlocks permanently override AP locks
- do not create duplicate Par + Par Club Piece location sets
- do not forget big-endian u16/u32
- do not forget dirty flag after intentional persistent writes

---

# 34. Suggested source organization

```text
worlds/carnival_games_minigolf/
    __init__.py
    Options.py
    Items.py
    Locations.py
    Regions.py
    Rules.py
    Names/
        ItemName.py
        LocationName.py
    docs/
        setup_en.md
        en_Carnival Games MiniGolf.md

client/
    CarnivalGamesMiniGolfClient.py
    memory.py
    constants.py
```

Keep RAM offsets separate from AP generation logic.

Suggested constants:

```python
MANAGER_PTR = 0x805DDD80
MANAGER_OBJECT_ARRAY = 0x100
MANAGER_OBJECT_COUNT = 0x104
MANAGER_HOLE_DEF = 0x10C
MANAGER_SESSION = 0x114
MANAGER_PLAYER_COUNT = 0x12C
MANAGER_PLAYER_ROOTS = 0x190

ROOT_SUB = 0x1DC
ROOT_HOLE_STATE_PTR = 0x19C
ROOT_WORLD_LOCKS = 0x2CC
ROOT_STROKES = 0x2DC

SUB_PRIZES = 0x00
SUB_WORLD_COINS = 0x58
SUB_BARKER_FLAGS = 0x6A
SUB_BARKER_TOTAL = 0x85
SUB_PAR_PIECES = 0x86
SUB_DIRTY = 0xA1

HOLE_STATE_IN_GOAL = 0x127

SESSION_CONTROLLER = 0xFC
SESSION_PLAYER_INDEX = 0x2EC
SESSION_COURSE_CONTEXT = 0x2F0

MINIGAME_VTABLE = 0x1C
MINIGAME_PLAYER_ROOT = 0x44
MINIGAME_SCORE = 0x11C
MINIGAME_TARGET = 0x120
MINIGAME_STATUS = 0x130

RESULT_VTABLE_VALUE = 0x804F7918
RESULT_PERFECT = 0xC0
RESULT_WIN = 0xC1
```

---

# 35. Implementation order for Codex

1. BE memory reader/writer.
2. safe manager/session/root resolver.
3. persistent-state snapshot arrays.
4. world-lock enforcement.
5. Options.py + slot data.
6. regions + Starting World + World Unlock items.
7. normal Pro Shop table/rules.
8. Secrets.
9. Barker Coin locations.
10. live normal-hole state/HIO.
11. minigame identity map.
12. result-popup Win/Perfect detection.
13. Coin Bundle receive behavior.
14. Barker spendable/counter receive modes.
15. Barker Shop option incompatibility validation.
16. goals.
17. reconnect/save testing.
18. multiworld generation/fuzz tests.
19. full Dolphin playthrough QA.

---

# 36. QA checklist

## Memory
- [ ] manager resolves after boot/restart
- [ ] client tolerates loading/menu null pointers
- [ ] no stale heap pointers cached indefinitely

## World locks
- [x] manual lock/unlock live test passed
- [ ] all 9 starting-world choices tested
- [ ] vanilla cannot permanently reopen AP-locked worlds
- [ ] received unlock opens exactly the correct world
- [ ] multiplayer behavior tested if supported

## Holes
- [ ] 27 Par checks send once
- [ ] HIO only when option enabled
- [ ] HIO + Par can both send on same shot

## Barker
- [ ] all 27 collectible mappings exercised
- [ ] spendable AP Barker grant occurs once
- [ ] counter mode reasserts correct value
- [ ] Barker Shop absent in counter mode

## Secrets
- [x] Fairytella `0->1`
- [x] Pirate's Delight `2->1`
- [ ] remaining mappings sampled

## Shop
- [ ] representative purchase maps correct ID/name
- [ ] reconnect does not duplicate anything
- [ ] 2/4/6/7+Club rule fuzzed
- [ ] Coin Bundle economy tested

## Minigames
- [x] Mine Shaft Madness VTable live-confirmed
- [x] live score 1/6 observed
- [x] Perfect run 6/6 observed
- [x] Win=1 / Perfect=1 result live-confirmed
- [ ] second-world minigame VTable sanity test
- [ ] Win-only and Perfect-only option generation tested

## Goals
- [ ] all-27-Par victory
- [ ] Barker Hunt threshold
- [ ] Barker Goal World remains locked before threshold
- [ ] opens exactly at threshold
- [ ] all 3 Goal World holes on par finish combined mode

---

# 37. Codex quick-start summary

```python
manager = read_u32_be(0x805DDD80)
session = read_u32_be(manager + 0x114)
player_index = read_u32_be(session + 0x2EC)
root = read_u32_be(manager + 0x190 + player_index*4)
sub = root + 0x1DC

# persistent
prize(i)      = read_u8(sub + i)                    # active iff ==1
world_coins(w)= read_u16_be(sub + 0x58 + 2*w)
barker(h)     = read_u8(sub + 0x6A + h)
barker_total  = read_u8(sub + 0x85)
par_piece(h)  = read_u8(sub + 0x86 + h)
dirty_addr    = sub + 0xA1

# world gating
world_lock(w) = root + 0x2CC + w                    # 0=open, !=0=locked

# normal golf
strokes       = read_u32_be(root + 0x2DC)
hole_state    = read_u32_be(root + 0x19C)
in_goal       = read_u8(hole_state + 0x127)
hole_def      = read_u32_be(manager + 0x10C)
par           = read_u32_be(hole_def + 0x0C)
course_ctx    = read_u32_be(session + 0x2F0)

# minigame
controller    = read_u32_be(session + 0xFC)
controller_vt = read_u32_be(controller + 0x1C)
live_score    = read_u32_be(controller + 0x11C)
live_target   = read_u32_be(controller + 0x120)

# result
array          = read_u32_be(manager + 0x100)
count          = read_u32_be(manager + 0x104)
# find obj with *(obj+0x1C) == 0x804F7918
perfect        = read_u8(result + 0xC0)
win            = read_u8(result + 0xC1)
```

Core design:

```text
Starting World: Random default, selectable
Worlds: AP-lock all except start; receive unlock items
Par Club Piece = Par check
HIO optional, default Off
Barker Coin checks optional
Secrets optional, default On
Shop optional, default On
Barker Shop separate; forced Off in Barker-counter goal modes
Minigames Off/Win/Perfect/Win+Perfect

Shop logic: 2 / 4 / 6 / 7+Club by 0/1/2/3 Par pieces

Goals:
- All 27 holes on par
- Barker Coin Hunt
- optional Barker requirement opens final Goal World, then par all 3 holes there
```

**This document is the authoritative current handoff for building the APWorld/client.**
