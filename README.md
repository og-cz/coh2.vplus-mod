<div align="center">

# COH2 V+ Mod

![COH2 V+ Mod](workshop/preview_banner.jpg)

**An ambitious, large-scale overhaul for Company of Heroes 2.**
Real bullets. Deadly machine guns. An enemy that attacks. Built to grow into a bigger WW2 army.

`Tuning Pack` · `All 5 factions` · `Skirmish & Custom Games` · `Version 1.0.0`

</div>

---

## Table of contents

1. [About](#about)
2. [Screenshots](#screenshots)
3. [Features](#features)
   - [Weapons and gunfire](#weapons-and-gunfire)
   - [Engagement ranges](#engagement-ranges)
   - [Aggressive AI](#aggressive-ai)
   - [Radio Man support upgrade](#radio-man-support-upgrade)
   - [Performance](#performance)
4. [Roadmap](#roadmap)
5. [Installation](#installation)
6. [How to play](#how-to-play)
7. [Building from source](#building-from-source)
8. [Project structure](#project-structure)
9. [FAQ](#faq)
10. [Known limitations](#known-limitations)
11. [Changelog](#changelog)
12. [Credits](#credits)

---

## About

**COH2 V+ Mod** turns Company of Heroes 2 into a harder, more brutal and more realistic battlefield.
Every round fired is a real projectile, machine-gun nests can stop an assault cold, and the AI keeps pushing
into fortified lines with smoke, artillery and flanking waves instead of hiding behind its own defences.

This is a big project with a long roadmap. Version 1.0 lays the combat foundation. Future versions will
add **new units, more detailed soldiers, historically accurate elite infantry and real tank variants
that are not in the base game**.

---

## Screenshots

> Screenshots coming soon.

<!--
Put images in docs/screenshots/ and add them here, for example:
![Beach assault](docs/screenshots/beach_assault.jpg)
![MG nest](docs/screenshots/mg_nest.jpg)
-->

---

## Features

### Weapons and gunfire

| | |
|---|---|
| **Real bullets** | Every rifle, SMG and machine-gun round physically flies downrange. A missed shot keeps going and can hit the soldier behind your target, so firing into a crowd is deadly. |
| **Subtle infantry fire** | Rifles, carbines, SMGs, pistols and snipers fire quick, low-key rounds, without big glowing tracers on every shot. |
| **Heavy machine-gun tracers** | HMG and LMG teams and every tank, halftrack, armoured car and aircraft MG fire heavy, visible tracer rounds, the same look across all factions. |
| **Vanilla impacts** | Classic CoH2 bullet impacts and tracer speeds. No phosphorus or other custom hit effects. |
| **Deadly shrapnel** | Shells burst into fragments that kill. Cover and spacing matter. |
| **Criticals and morale** | Weapon jams, crew and engine criticals, suppression and pinning all stay part of every fight. |

### Engagement ranges

Ranges are realistic but not extreme. Every weapon class keeps the same balance relative to the others.

| Weapon class | Range |
|---|---|
| Rifles, SMGs, LMGs, HMGs | 120 |
| AT guns, infantry AT weapons, tank guns | 120 |
| Mortars | 240 |
| Light artillery | 320–600 |
| Heavy artillery | 320–800 |
| Flamethrowers | 20–40 |

The "hold fire" range toggles and the cast range of barrage abilities are scaled to match.

### Aggressive AI

The AI is built to **attack**, not to wait.

- **Breaks fortified lines.** It no longer treats MGs behind heavy cover as untouchable, so it keeps advancing.
- **Several attack axes.** It runs up to 4 attack objectives at once and hits the line from different directions.
- **Flanks MG nests.** Its pathing avoids firing arcs, so infantry go around the gun instead of walking into it.
- **Uses its toolbox.** Smoke on suppressing MGs, and mortars, artillery and off-map strikes on static positions.
- **Stays on the offensive.** Squads don't camp in cover forever, assault squads rush, and attacks are re-launched after losses.
- **Fair.** It gets no extra units or production bonuses. The AI just fights better with what it has.

### Radio Man support upgrade

An optional **per-unit upgrade (60 munitions, 20 s)** for crew-served support weapons in all factions.

| Weapon type | Without Radio Man | With Radio Man |
|---|---|---|
| Mortars | Normal auto-fire at anything in range | Fire directed at the most important targets first: MG teams, AT guns, mortars, vehicles, garrisons. Lone squads only when nothing bigger is in range. |
| Infantry support guns | Normal | Same priority targeting as mortars |
| Howitzers | Fire only when ordered (barrages) | Slow, deliberate fire missions on their own, about 1 shell every 25 s |
| All | – | +20% sight for the crew |

Barrage, counter-barrage and attack-ground orders work exactly as before.

**Available on:**

| Faction | Units |
|---|---|
| US Forces | 60 mm, 81 mm and 107 mm mortars; 75 mm pack howitzer |
| British Forces | 2-inch, 3-inch and 4.2-inch mortars; 75 mm pack howitzer |
| Wehrmacht | 50 mm, 81 mm and 120 mm mortars; le.FH 18 105 mm howitzer |
| Soviet Union | 50 mm, 82 mm and 120 mm mortars; ML-20 152 mm and B-4 203 mm howitzers |
| Oberkommando West | le.IG 18 infantry support gun |

### Performance

Built for huge battles on regular PCs:

- Bullets and shrapnel fragments no longer stamp a crater decal on the terrain at every hit.
- Infantry rounds don't render a glowing shell model.
- Shrapnel fragments don't spawn an extra collision effect each.

---

## Roadmap

COH2 V+ Mod is planned as a long-term project. Upcoming work:

- [ ] **New units** for every faction
- [ ] **More detailed soldiers**: better loadouts and squad compositions
- [ ] **Historically accurate elite infantry**, including Waffen-SS formations
- [ ] **Real tank variants not in the base game**, such as Sd.Kfz. 222 scout car variants and other historical versions
- [ ] More special and rare vehicles
- [ ] Further AI work for very large battles
- [ ] More performance options

Ideas and feedback are welcome. Open an issue.

---

## Installation

### From the Steam Workshop
Subscribe on the Workshop page (link coming soon). Steam downloads it automatically.

### Manual install
1. Download `VanillaPlus.sga` from the Releases page, or build it yourself (see below).
2. Copy it to:
   ```
   Documents\My Games\Company of Heroes 2\mods\tuning\
   ```
   Or run **`install.bat`** from this folder.
3. Start Company of Heroes 2.

---

## How to play

1. **Play → Custom Game** (or Skirmish).
2. Add AI opponents. **Hard** or **Expert** is recommended to see the aggressive AI at its best.
3. **Game Options → Tuning Pack → COH2 V+ Mod**.
   *The mod list can take about 20 seconds to appear after the game starts.*
4. Start the match.

**Tips**
- Keep MGs in cover with flanks covered. The AI *will* try to go around them.
- Buy **Radio Man** on mortars to let them pick off enemy MG nests and AT guns on their own.
- Spread your infantry out. Bullets that miss keep flying, and shrapnel kills.

---

## Building from source

**Requirements:** Windows, Company of Heroes 2, and Python 3.9+ (no extra packages).

```bat
build.bat
```

This runs the full pipeline:

| Step | Script | What it does |
|---|---|---|
| 1 | `tools/build_vplus.py` | Applies every change (gunfire, ranges, AI, performance, Radio Man) and writes `modified/` plus `reports/` |
| 2 | `tools/pack.py` | Packs everything into `output/VanillaPlus.sga` with the mod's own identity |
| 3 | `tools/verify.py` | Re-reads the pack and checks integrity, references and that combat stats are unchanged |
| 4 | `tools/audit.py` | Writes `reports/AUDIT.md`: every squad in every faction and how its weapons were treated |

Then run `install.bat` to copy the result into the game.

**Tuning:** all numbers live at the top of `tools/build_vplus.py`:

| Setting | Default | Meaning |
|---|---|---|
| `RANGE_FACTOR` | `0.80` | Global weapon range multiplier |
| `RADIO['munition_cost']` | `60` | Radio Man price |
| `RADIO['howitzer_reload_seconds']` | `25` | Howitzer auto-fire interval with Radio Man |
| `RADIO['sight_multiplier']` | `1.2` | Radio Man sight bonus |
| `RADIO['priority']` | threat 40 | How strongly Radio Man prefers big targets |
| `COVER_RATING`, `AI_SETTINGS` | see file | AI aggression |

---

## Project structure

```
coh2.vanilla-plus/
├── build.bat / install.bat     one-click build and install
├── tools/                      build pipeline (Python)
│   ├── build_vplus.py          all gameplay changes
│   ├── pack.py                 SGA packer
│   ├── verify.py               static checks
│   ├── audit.py                all-faction audit
│   ├── rgd.py, flat.py         attribute file reader/writer
│   └── sga7*.py                archive reader/writer
├── reports/                    every changed value (CSV) + audit + verification log
├── workshop/                   Workshop banner + release checklist
├── docs/screenshots/           screenshots
├── CHANGELOG.md  MODIFICATION_LOG.md  TESTING_REPORT.md
└── (not in git) original_backup/ extracted_assets/ modified/ output/
```

---

## FAQ

**Does it work in multiplayer?**
Yes, in custom games where everyone uses the tuning pack. It is not for automatch.

**Do I need any other mod?**
No. COH2 V+ Mod is standalone.

**The mod doesn't show up in the list.**
Wait about 20 seconds after the game starts, or restart the game. Check that `VanillaPlus.sga` is in `mods\tuning\`, not in `mods\tuning\subscriptions\`.

**Why don't my rifles show big tracers?**
That's intentional. Infantry fire is subtle, while machine guns show the heavy tracer rounds.

**Will the AI buy Radio Man?**
No. It's a player option.

---

## Known limitations

- Radio Man targeting is a strong *preference*, not a hard filter. A lone squad can still be shelled if it's the
  biggest threat in range.
- If an upgraded mortar or gun is destroyed, the surviving crew won't auto-fire their rifles. They still fire when ordered.
- The AI's top-level strategy script is part of the base game. The mod tunes all the data the AI uses, not the script itself.

See `TESTING_REPORT.md` for the full test plan.

---

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md). Current version: **1.0.0**.

---

## Credits

- **RebelSoldier**, for the original realism overhaul this mod is built on.
- **Company of Heroes 2** © Relic Entertainment / SEGA. This is a fan-made mod, not affiliated with Relic or SEGA.
