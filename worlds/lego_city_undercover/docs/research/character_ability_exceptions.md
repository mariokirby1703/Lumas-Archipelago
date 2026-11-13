# Character-specific ability exceptions

User reports that doctor characters can open safes using their stethoscope.
This is a reported gameplay exception, not yet independently tested or mapped to
specific native model IDs. Do not assume every medical-looking skin has it.

Research questions:
- Identify each doctor model and verify safe eligibility, including characters
  outside the standard Robber class and differences between individual safes.
- Trace whether eligibility is supplied by an item, model metadata, native
  category fallback or another rule. The native Robber class marker does not
  by itself prove that only Robber models can use the safe.
- Compare the exception with an independent AP Stethoscope permission. If the
  tool is randomized independently, the eventual gate must also cover doctors
  to prevent an unintended bypass.

Logic should express safe-opening capability rather than hard-code one costume:
once verified, alternative characters may satisfy that capability. If their
ability is independently gated, the character alone must not satisfy it.
Do not add this unverified alternative to generation rules yet.

Item classification depends on the final rules: a character that can provide
required access to checks or the goal may need progression classification even
when it is one of several alternative routes. A real optional gameplay benefit
without logic-required access can justify useful. Purely cosmetic alternatives
can remain filler. Merely owning a tool-shaped prop does not establish capability.
