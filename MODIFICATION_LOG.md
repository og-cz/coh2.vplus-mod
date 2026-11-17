# Modification log – COH2 V+ Mod 1.0.0

Base: Kriegspiel V5 – Realism Overhaul (Workshop 2162940169), SGA v7 with 4,360 files.
Output: `output/VanillaPlus.sga`, with 4,382 files (757 changed or added). Every old→new value is in `reports/*.csv`.

## 1. Damage mechanics (restored)

| Item | Kriegspiel | Personal build (old) | COH2 V+ Mod |
|---|---|---|---|
| MG / AT-rifle `weapon_bag/projectile` | `bullet_*_mp` | removed (hitscan) | **original `bullet_*_mp`** |
| Infantry `weapon_bag/projectile` | `bullet_*_mp` | removed | `bullet_*_inf_mp` (same bullet, model hidden) |
| Damage, accuracy, penetration, ROF, burst, cooldown, reload, aim, suppression, scatter, AoE, criticals | — | unchanged | unchanged (verified on all 613 weapons) |

Root cause of the weak MGs: Kriegspiel resolves many hits through the physical bullet. A missed shot keeps flying and
can hit another soldier. Hitscan kept only the aimed hit, so effective damage dropped sharply even though no number changed.

## 2. Gunfire presentation (`reports/gunfire_changes.csv`)
- **Infantry** (rifles, carbines, SMGs, pistols, snipers; 65 weapons) use 9 new blueprints, `ebps/projectile/bullet_*_inf_mp`.
  Each is a byte-level copy of the original bullet with only `is_visible_in_game=False` and a new `pbgid`. Speed,
  homing collision and explosion are identical, so hits behave the same.
- **Machine guns** (71 LMGs, 43 HMGs, including every tank, halftrack, armoured car and aircraft MG) and 5 AT rifles keep
  the original visible bullet. That gives one consistent machine-gun look for all factions and vehicles.
- `fx_munition_name` and `fx_tracer_speed` now use the vanilla value for each weapon's vanilla tracer (from your CoH2
  `AttribArchive.sga`). This removes `mg_phosphorus` from 25 MGs. `fx_tracer_name` was already vanilla everywhere.
- Not touched: tank guns, AT guns, autocannons, flak, rockets, artillery, mortars, flamethrowers, grenades.

## 3. Ranges ×0.80 (`reports/ranges_changes.csv`, `ability_ranges_changes.csv`)
- 488 weapons: `range/max` and `range/distance/near|mid|far`. The minimum range is kept.
- 64 barrage abilities (cast range), and 5 additive hold-fire modifiers (−35/−85/−135 → −28/−68/−108).
- Excluded: grenades, mines, shrapnel and ricochet helpers, DoT helpers, and 9 dummy weapons.

## 4. AI (`reports/ai_changes.csv`, 305 values, same as the personal build)
- Combat-rating cover multipliers: green 1000→6, yellow 500→3, garrison 250→8, trench 500→12, bunker 500→10.
- Squad `hold_tactic` and `cover_tactic`: priorities capped (150 / 400), and time limits 20 / 30 s (they were "never").
- Combat evaluation win ratio 1.0/0.5 → 0.7/0.35. Attack objectives 2→4. Capture tasks 4→6.
- Assault squads: `rush_at_target` 300. Smoke abilities 300. Barrage and off-map abilities ≥150.

## 5. Performance (`reports/perf_changes.csv`)
- `explosion_ext/terrain_hit/deformation` turned off on 19 bullet blueprints, 9 infantry variants and 13 shrapnel/ricochet/WP-fragment
  blueprints (no crater decal per hit). `spawn_collision_fx` is off on 3 fragment blueprints.
- Bullets and shrapnel still fly and hit; their damage is unchanged.

## 6. Radio Man (`reports/radio_changes.csv`)
- New `upgrade/vplus_radio_man_mp`: 60 munitions, 20 s, once per squad, shown in the unit upgrade panel. Its structure is based on
  vanilla `aef_tank_commander_mp`. When bought it:
  - enables `hardpoint_08` (the radio weapon);
  - disables auto-targeting on `hardpoint_01`, the gun's normal weapon. The gun still fires on attack orders, and barrage and
    counter-barrage use other hardpoints;
  - gives sight ×1.2.
- 12 radio weapons, `<weapon>_vplus_radio_mp`, are exact copies of the gun's weapon *after* range scaling. Only the target
  priority changes: threat 40, current target 10, flat distance. Howitzer copies (le.FH 18, ML-20, B-4) also get a 25 s reload and no burst.
- 14 gun entities get padding up to `hardpoint_08`, which holds the radio weapon. A spawn action applies `enable_weapon_modifier −1`, so the
  radio weapon is off until the upgrade is bought.
- 18 squads get the upgrade button: US 60/81/107mm and 75mm pack howitzer; UK 2"/3"/4.2" and 75mm; Wehrmacht 50/81/120mm
  and le.FH 18; Soviet 50/82/120mm, ML-20 and B-4; OKW le.IG 18.
- Locale: strings 1972–1974 appended to `english.ucs`.

## 7. Identity
- New GUID `000a73d70e7a4afb86e5c04167fcd04e`. It replaces Kriegspiel's in every reference, so the two can be installed side by side.
- `.info`: name "COH2 V+ Mod" and a new description with credits. Kriegspiel's preview `kspfp.tga` is still inside.
  The Workshop preview banner is `workshop/preview_banner.jpg`.
