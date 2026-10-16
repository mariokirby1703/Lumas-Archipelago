# White capsule lock: native model variant 2

On 2026-10-16 the user's running PAL ISO (native component
85eebb98e87ebd22a6fcf7a99e0ae838c91514235a5c9ce73012bf785e1c813f)
was read in stg610. Capsule actor 90B695C0 was unopened, White subtype -1,
model 90B69740, native model mode 2. Authenticated capsule controls at 80001A30
were owner 9310DDA0, selected index 0, permission word 0: White was already
correctly denied. The meter was zero at the time of inspection.

The old reconciler admitted model modes 0/1 only and skipped mode 2. The
original content constructor at 800D3F04..800D3F20 selects mode 2 when actor+144
is set, otherwise mode 1. Both represent enabled capsule content; the ghost
constructor uses mode 0.

The corrected native helper normalizes mode 2 to enabled mode 1 only in its
permission comparison. If denied it invokes the existing native ghost-model
and state-transition functions. If owned, it retains model 2 unchanged; it
never repeatedly rebuilds an allowed variant or overwrites its properties.
Opened capsules and unknown modes remain untouched. White, coloured and random
permissions retain their independent policy. Previous exact helper layouts
remain recognizable for migration; a rebuilt native ISO is required to execute
the corrected helper. No new seed is needed.

Generated-PPC tests cover mode 2 with/without ownership for White and coloured
capsules, full and compact ABIs, no repeated enabled-model replacement, and
opened/unknown-mode preservation. Original-ELF assertions reproduce the native
variant selection. A live visual/collision retest on the rebuilt ISO is still
required. This does not claim that every startup/respawn timing case is proven.

The result-screen item HUD placement and missing music box reported just before
this issue remain a separate pending task; the user will leave results open for
a live transform measurement. Existing gameplay/map layouts must be retained.
