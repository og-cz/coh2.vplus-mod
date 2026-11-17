# Changelog

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
