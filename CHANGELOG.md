# Changelog

## 1.2.1 (2026-11-17)

### Fixed
- **Radio Man did nothing in multiplayer games** (no soldier, no fire). A multiplayer squad upgrade is only a flag; its effects
  must live in the squad. They now sit in each squad's `squad_action_apply_ext` (`required_squad_upgrade` -> add observer /
  enable the radio weapon on every entity), the same way vanilla grenadiers get their veteran leader.
- **Radio Man had no tooltip text.** The strings were stored as plain text instead of localized strings (type 4).
- **Machine guns killed tanks.** The MG damage table matched tanks as `vehicle` before `heavy_vehicle` (immune). Tanks now
  match `heavy_vehicle` first, as Kriegspiel intended. Light vehicles still take MG damage.
- **Machine guns wiped squads instantly.** Kriegspiel infantry have 30 HP. MG hit chance is now 0.35 x vanilla, so a burst pins
  first and kills over a few seconds.

### Changed
- Radio Man fires like a normal weapon: one round every 5-14 s (mortars 5-8 s, rockets 6 s, howitzers 8-14 s).

## 1.2.0 (2026-11-17)

### Fixed
- **Support weapons never fired with Radio Man.** The radio weapon was copied from Kriegspiel's hardpoint 1, which on most
  mortars and the ML-20 is a range-1 placeholder. The upgrade also applied its modifiers to the squad instead of the gun.
  Radio weapons are now copies of the real barrage / rocket weapon, and the upgrade enables them on the gun entity
  (the vanilla slot-item pattern). The gun's own weapons are never switched off any more.
- **Artillery built a ring of sandbags** when placed or spawned (e.g. with a spawner mod). The scripted spawns
  (`AE_SpawnPak43Defenses`, `AE_SpawnSupplyTruckAccessory_1/2`) are removed from the le.FH 18, ML-20 and B-4.

### Changed
- **Machine guns: vanilla hit-scan, Kriegspiel damage.** All 114 machine guns drop the physical bullet. Hit chance, suppression,
  scatter, aim, target choice and tracer look come from vanilla. Damage, penetration, criticals, rate of fire, burst,
  cooldown, reload, cover and target tables stay Kriegspiel. HMG teams pin again.
- **Radio Man = an extra soldier.** On crew-served guns the upgrade adds a forward observer (faction officer model).
  Now also on rocket artillery (Land Mattress, Katyusha, Panzerwerfer, Calliope, Wurfrahmen) and Priest / Sexton
  (radio set, no extra soldier). The in-game tooltip explains what it does.
- **The AI may retreat again** (Kriegspiel fallback values). Forced retreats stay removed for everyone, so nothing
  can make your squads retreat except your own order.
- **Less AI grenade spam:** AI priority for frag / rifle grenades 85 -> 20, AT grenades 85 -> 40, smoke 50 -> 35.

## 1.1.0 (2026-11-17)

### Fixed
- Crash when a match loaded: the Radio Man enable/auto-target modifiers had two fields the game's data layout
  doesn't allow. New `tools/schema_check.py` checks every changed table against the game's own layouts.

### Changed
- **No forced retreats.** 241 automatic retreat actions were removed: last-man-standing auto-retreat, and shell shock from
  shells, rockets and grenades. Squads are still stressed, suppressed and pinned. Player-ordered retreats and
  Withdraw and Refit are unchanged.
- **AI never retreats or falls back.** All retreat and fallback thresholds are 0.
- **AI holds positions less.** The hold tactic is capped at 40 priority with a 15 s limit, and cover at 300 with a 25 s limit.
- **Vanilla bullet look for machine guns too.** The bullet's shell model is hidden on all bullets. Every gun shows its vanilla
  tracer, thin for rifles and heavier for MGs. The physical bullets and their damage are unchanged.

## 1.0.0 (2026-11-17), first COH2 V+ Mod build

### Fixed
- Machine guns were weak in the earlier personal build because it had removed Kriegspiel's
  physical bullets. Missed bullets hitting nearby soldiers are part of Kriegspiel's damage model.
  All bullets are back, and damage, accuracy, penetration, ROF, reload, suppression, scatter and
  AoE are identical to Kriegspiel in all 613 weapons (checked by `tools/verify.py`).

### Changed
- Infantry weapons (65) fire a subtle copy of their bullet, with the same flight and hit behaviour but
  no glowing shell model.
- Machine guns (114, infantry and vehicle) and AT rifles (5) keep the visible tracer round.
- Vanilla munition and impact FX and vanilla tracer speeds on all 184 bullet weapons.
- Weapon ranges ×0.80 on 488 weapons. 64 barrage abilities and 5 hold-fire modifiers were scaled
  to match.
- AI aggression changes (cover over-rating fix, tactic time limits, attack objectives, smoke and
  artillery priorities).
- Performance: no terrain crater decal per bullet (28 bullet blueprints) or per shrapnel fragment (13).

### Added
- **Radio Man** upgrade (60 munitions, 20 s, once per squad) on 18 support-weapon squads across all
  5 factions. It adds a radio-guided copy of the gun's own weapon on hardpoint_08.
- New mod identity: name "COH2 V+ Mod", own GUID, own description with credits.
