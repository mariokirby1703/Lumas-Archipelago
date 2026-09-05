# Changelog

## 0.1.0

Initial release for Create on Wii (PAL, `SECP69`).

- Randomized World Access and Create Objects, synchronized through Dolphin.
- Challenge Spark checks, the hub Create Chain, and optional per-world Create Chain checks.
- Ten base worlds and four optional II worlds.
- Goal World Unlock and Spark Hunt, with configurable Spark requirements.
- Defaults: 100 required Sparks, Goal World Unlock, Create Chains enabled, II worlds disabled,
  and random starting and goal worlds. At 0 Sparks, both modes use normal goal-world item access.
- Universal Tracker support for recorded alternative solutions.
- A launcher client with `.apcreate` support and connection status commands.

Only Save Slot 3 is supported. Start each seed with a fresh save and keep the client open while
playing. See the [setup guide](docs/setup_en.md) for save handling and connection instructions.
