# Testing report – COH2 V+ Mod 1.0.0

**The game was not launched during the build.** Everything under "verified" comes from `tools/verify.py`
(log in `reports/verification.txt`, 20/20 checks pass). Everything else needs in-game testing.

## Verified statically
- Tooling: unpack and repack of the untouched Kriegspiel archive is byte-identical. All 4,283 RGDs re-encode byte-identically.
  The file-adding builder reproduces the template byte for byte when nothing is added.
- The output is SGA v7 with the COH2 V+ Mod GUID. CRC32, SHA-1 and sizes are correct for all 4,382 files. All 4,305 RGDs parse with valid CRCs.
- Original file tree plus 22 new files, nothing lost. The old GUID is fully replaced. All 1,550 mod references resolve.
- **Damage model:** all 119 MGs and AT rifles fire their original Kriegspiel bullet. Damage, accuracy, penetration, ROF,
  reload, suppression, scatter and AoE are identical in all 613 Kriegspiel weapons.
- Infantry bullet copies differ from the originals only in the hidden model and the new id. 65 infantry weapons use them, and no MG does.
- No field outside the allowed change list differs from Kriegspiel.
- Radio Man: the 12 radio weapons are exact copies apart from targeting and howitzer cadence. The upgrade costs 60 munitions, once per squad.
  14 guns have `hardpoint_08`, 18 squads have the button, and the locale strings are present.
- Barrage and counter-barrage abilities are untouched apart from their range. 488 ranges are exactly ×0.80.

## Needs in-game testing
1. **Loads:** COH2 V+ Mod shows up in the tuning-pack list and a skirmish starts.
2. **MG lethality** (main fix): an MG42 or .50 cal into a crowd should kill like in Kriegspiel V5.
3. **Gunfire look:** rifles and SMGs show no glowing shell. MGs, vehicle MGs and aircraft MGs show the tracer round.
   If infantry fire looks *too* invisible, tell me. The fallback is to keep their model, but that brings back the MG-like look.
4. **Radio Man**, on one mortar and one howitzer of each faction:
   - The button appears, costs 60 munitions and can be bought once.
   - Before buying, the gun behaves exactly like Kriegspiel. The radio weapon must **not** fire.
   - After buying, the mortar prefers MGs, AT guns and vehicles over infantry. The howitzer auto-fires about every 25 s.
   - Barrage, counter-barrage and attack-ground orders still work after the upgrade.
5. **Ranges:** infantry engage at about 120 and mortars at about 240. Barrage abilities can still be cast. The hold-fire toggles still work.
6. **AI:** the D-Day test. It should keep pushing, flank, and use smoke and artillery on MG lines.
7. **Performance:** compare FPS with Kriegspiel V5 in the same large battle. No FPS gain is claimed.

## Known limitations
- **Radio Man targeting is a preference, not hard filtering.** The game decides using target threat. A lone squad can still be
  shot if it is the most threatening thing in range. Real "spot a concentration and call fire" needs Lua, which tuning packs can't include.
- **Crew rifles may not auto-fire after Radio Man.** The upgrade disables auto-targeting on `hardpoint_01` for every entity
  in the squad, which includes the crew's rifles. While the gun is manned they don't fire their rifles anyway. If the gun is lost, the
  surviving crew of an upgraded squad won't auto-fire their rifles, but they still fire when ordered.
- The enable/disable logic for the radio weapon follows the vanilla counter pattern (−1 at spawn, +1 from the upgrade). That is
  inferred from vanilla data, not seen running.
- **Bullet thickness:** vanilla CoH2 has no thinner bullet model. The available choice was visible tracer round (MGs) versus no shell model
  (infantry). Tracer thickness and frequency inside the vanilla FX files can't be edited in a tuning pack.
- The AI won't buy Radio Man. It's a player option.
- Self-propelled artillery, rocket artillery and AT/field guns don't get Radio Man.
