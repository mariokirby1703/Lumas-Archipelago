# Vehicle states and boundary return

Implementation update: see [disembark and creature return](disembark_and_creature_return.md) for the subsequently added rail/passenger exit and ridden-character paths. Earlier limitations below describe the survey baseline.

Static survey of the pinned Steam DX11 executable, 15 November 2026. Reproduce with `tools/research_vehicle_transforms.py`. The machine-readable evidence is `vehicle_transform_inventory.json`; the packaged class map is `bridge/vehicle_types.json`.

## Actual classes, rather than model names

Seven primary ApiVehicle RTTI tables were found for the reviewed getter. All seven dispatch transform reads to `0x4a9370` and writes to `0x4abb60`: ApiVehicle, ApiVehicleCar, ApiVehicleBike, ApiVehicleStatic, ApiVehicleBoat, ApiVehicleAircraft and ApiVehicleHover. Thus ordinary cars/buses, bikes, boats, aircraft and hover vehicles do not each need a different transform offset. Whether a particular UFO model uses Hover or Aircraft must be read from its actual live vtable, not guessed from its cosmetic name.

Getter `0x4a9370` reads `vehicle+0x348`, then copies the physics matrix at `physics+0x60`. Translation is `physics+0x90`. The previously reviewed `0x506fe0` appears in DummyPlaceable and PlaceableStub tables; it was not evidence for real car support. Existing fallback compatibility is retained, but diagnostics now identify actual native classes and getter/setter RVAs. The live user's car was read successfully through the physics path; visual rollback of other types is still unverified.

The existing native return routine `0x4abe70` dispatches the virtual setter at `+0xf8`, which is shared by all seven actual classes, and performs the game's synchronization calls. `0x4abb60` handles the physics transform, linked state and occupants; it is not equivalent to a raw position write. We do not clear unknown velocity fields. Shared dispatch proves structural compatibility, not safe flight, water placement or an entire train restoration.

## Contexts

The game's context table contains RideAlong (11), DropPoint (27), FlyHover (100), RideObject (157), VehicleJump (186), VehicleLand (187), VehicleFall (188), VehicleHorn (189) and CargoDeploy (193). A context name alone does not prove that the player owns a live vehicle reference or controls it. The boundary writer currently accepts Default (46, verified unmounted) and RideObject (157, verified mounted with live weak references). Passenger/scripted, transition, airborne-character and cargo contexts remain deferred. FlyHover must not be globally enabled: it can describe the character rather than a vehicle.

## Trains and trams are controlled by scripts and splines

Native source `GAME4/jobs/scripts/city_setup/general/sf_trams/sf_trams.sf` creates Courser, binds it to CityTramSpline, sets spline limits, and distinguishes the driver, Passenger1 and other passengers. A generic pose change does not restore route distance or direction.

`train_setup/train_control.sf` tracks three vehicles (vTrain, vCarriage, vRearTrain), occupied cars, separate front/carriage/rear teleport locators and North/South line state. Before its scripted teleport it releases carriage links, calls AttachToSpline_YFree("") and DisableManualAIControl(true). After teleport/spawn it attaches each vehicle to its spline and reconnects rail vehicles. Moving only the occupied carriage cannot reproduce that process.

Reviewed script action handlers: Vehicle_AttachToSpline_YFree `0x118100`, Vehicle_ConnectRailVehicles `0x118220`, Vehicle_DisableManualAIControl `0x118590`, Vehicle_ReleaseCarriage `0x11a1a0`. The spline handler resolves a named world spline and dispatches AI virtual `+0xb8`; the manual-AI action calls `0x1929a0`, and release-carriage calls `0x199b90`. These addresses are research evidence, not enabled generic mutation commands.

Rail rollback remains unfinished. It needs a route-aware checkpoint containing the consist, spline, direction and attachment state, or a separate reviewed disembark-to-allowed-ground path. Long-distance train fast travel also needs a destination gate; the 90 metre nearby checkpoint return cannot handle it. Do not claim trains or trams are protected merely because they share ApiVehicle's matrix getter.

## Test status

Reader fixtures cover every one of the seven class tables, missing/expired references, unsupported getters and the physics layout. Native fixtures cover original teleport dispatch, identity, binding, signatures and distances. None of these synthetic checks proves airplane, boat, UFO, train or tram rollback in live gameplay. The next native trials should start with bus, then boat, then aircraft/hover; rail remains a separate implementation task.
