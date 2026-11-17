"""
Static verification of output/VanillaPlus.sga against the original Kriegspiel V5 archive.
Writes reports/verification.txt. Exit code 1 on any failure.
"""
import os, sys, struct, zlib, hashlib, json, csv, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rgd, sga7w
from flat import flat_idx
rgd.load_dict()
ID = json.load(open(os.path.join(HERE, 'vplus_identity.json')))
OLD, NEW = '3f698c4a5048428d9fdb675aa488f596', ID['guid']
lines = []; fails = 0
def ok(c, m):
    global fails
    lines.append(('PASS ' if c else 'FAIL ') + m); fails += (not c)
def norm(b): return b.replace(OLD.encode(), NEW.encode()).replace(OLD.encode('utf-16-le'), NEW.encode('utf-16-le'))

A = sga7w.read(os.path.join(ROOT, 'output', 'VanillaPlus.sga'))
O = sga7w.read(os.path.join(ROOT, 'original_backup', 'Kriegspiel_V5_2162940169.sga'))
added = ['attrib/attrib/' + p for p in json.load(open(os.path.join(ROOT, 'reports', 'added_files.json')))]
d = A['d']; blk = A['hdr'][9]; hb = d[sga7w.B + A['hdr'][8]: sga7w.B + A['toc_size']]

# ---------------- 1. archive integrity
ok(d[:8] == b'_ARCHIVE' and struct.unpack_from('<H', d, 8)[0] == 7, 'SGA v7 header')
ok(d[12:140].decode('utf-16-le').rstrip('\0') == NEW, 'archive identity = Vanilla+ GUID ' + NEW)
C = {}; bad = 0
for i, f in enumerate(A['files']):
    raw = sga7w.raw_of(A, i)
    if zlib.crc32(raw) & 0xffffffff != f[7]: bad += 1
    if f[5] == 4 and any(hb[f[8] + 20 * j:f[8] + 20 * j + 20] != hashlib.sha1(raw[j * blk:(j + 1) * blk]).digest()
                         for j in range(max(1, (len(raw) + blk - 1) // blk))): bad += 1
    c = sga7w.content(A, i)
    if len(c) != f[3]: bad += 1
    C[A['paths'][i]] = c
ok(bad == 0, f'CRC32 / SHA-1 / size of all {len(C)} stored files ({bad} bad)')
opaths = {p.replace(OLD, NEW) for p in O['paths']}
ok(set(C) == opaths | set(added), f'file tree = original {len(opaths)} + {len(added)} new files, nothing lost')
ok(all(OLD.encode() not in c and OLD.encode('utf-16-le') not in c for c in C.values()) and OLD.encode() not in d[:A['data_pos']],
   'Kriegspiel GUID fully replaced (no collision with the Workshop Kriegspiel)')
T = {}; rb = 0
for p, c in C.items():
    if not p.endswith('.rgd'): continue
    try:
        sz = struct.unpack_from('<I', c, 68)[0]
        if zlib.crc32(c[72:72 + sz]) & 0xffffffff != struct.unpack_from('<I', c, 64)[0]: rb += 1
        T[p] = rgd.parse_table(c[72:72 + sz], 0)
    except Exception: rb += 1
ok(rb == 0, f'all {len(T)} RGD files parse with valid chunk CRC ({rb} bad)')
names = {os.path.basename(p)[:-4] for p in T}
refs = set()
def collect(tab):
    for h_, t, v in tab:
        if t == 3 and v.split(':')[0].lstrip('$') == NEW and not v.startswith('$'): refs.add(v.split(':', 1)[1])
        elif t in (100, 101): collect(v)
for t in T.values(): collect(t)
unres = sorted(r for r in refs if r not in names)
ok(not unres, f'all {len(refs)} mod references resolve to a file in the pack (unresolved: {unres[:5]})')
ucs = C['locale/english/english.ucs'].decode('utf-16')
ok(all(('\n%d\t' % i) in ucs for i in range(1972, 1978)), 'Radio Man locale strings 1972-1977 present')

# ---------------- 1b. ids: unique, and new ones continue the mod's dense blocks
pb = collections.Counter(); act = collections.Counter()
def ids(tab):
    for h_, t, v in tab:
        if t == 1 and h_ == rgd.h('pbgid'): pb[v] += 1
        elif t == 1 and h_ == 0x3251a3ee: act[v] += 1
        elif t in (100, 101): ids(v)
for t in T.values(): ids(t)
ok(all(n == 1 for k, n in act.items()), f'all {len(act)} action ids unique ({sum(1 for n in act.values() if n > 1)} duplicated)')
newpb = [flat_idx(T[p]).get('/pbgid') for p in added]
oldpb = {flat_idx(T[p]).get('/pbgid') for p in T if p not in added}
ok(len(set(newpb)) == len(newpb) and not (set(newpb) & oldpb) and max(newpb) - 0x40000000 < 1000,
   f'{len(newpb)} new instance ids are unique, collide with nothing, and continue the mod block (offsets {min(newpb) - 0x40000000}-{max(newpb) - 0x40000000})')
ok(max(act) - 0x40000000 < 200000, f'action ids stay in the mod block (max offset {max(act) - 0x40000000})')

# ---------------- 2. field-level diff against Kriegspiel
OF = {}
for i, p in enumerate(O['paths']):
    if p.endswith('.rgd'):
        c = norm(sga7w.content(O, i)); sz = struct.unpack_from('<I', c, 68)[0]
        OF[p.replace(OLD, NEW)] = flat_idx(rgd.parse_table(c[72:72 + sz], 0))
NF = {p: flat_idx(t) for p, t in T.items()}
ALLOWED = [re.compile(x) for x in [
    r'^/weapon_bag/fx_tracer_speed$', r'^/weapon_bag/fx_munition_name$',
    r'^/weapon_bag/range/(max|min|distance/(near|mid|far))$', r'^/ability_bag/range$', r'.*/range_weapon_modifier/value$',
    r'^/ai_settings_bag/(combat_ratings/cover_table/[^/]+/class_rating_multiplier|skirmish_settings/(combat_eval|tasks)/.*)$',
    r'^/ai_squad_bag/tactics/(hold_tactic|cover_tactic|rush_at_target)/(priority|0x1810bb21)$',
    r'^/ai_ability_bag/ai_tactic/priority$',
    r'^/explosion_ext/terrain_hit/deformation/(deform_decal_file|vertical_scale)$', r'^/projectile_ext/spawn_collision_fx$',
    r'^/ai_settings_bag/fallback/(retreat_health_ratio|retreat_combat_rating_ratio|retreat_capacity_ratio|fallback_combat_rating_ratio|fallback_capacity_ratio|fallback_squad_health_ratio|fallback_vehicle_health_ratio|retreat_on_pinned|retreat_on_suppression)$',
    r'^/entity_blueprint_ext/is_visible_in_game$']]
MG_HIT = re.compile(r'^/weapon_bag/((accuracy|suppression|scatter|aim|priority|behaviour|area_effect/distance)/.*|fx_[^/]+|projectile/projectile)$')
mg_files = {'attrib/attrib/' + r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'mg_hitscan_changes.csv'))) if r[0] != 'file'}
sandbag_files = {'attrib/attrib/' + r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'sandbags_changes.csv'))) if r[0] != 'file'}
gun_ebps = {r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'radio_changes.csv'))) if r[1] == 'gun entity'}
squads = {r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'radio_changes.csv'))) if r[1] == 'squad'}
unexpected = collections.Counter(); proj_mg_changed = []; proj_inf_bad = []
for p, a in OF.items():
    b = NF[p]; rel = p.split('attrib/attrib/', 1)[1]
    structural = rel in gun_ebps or rel in squads
    for k in a:
        if k not in b:
            if '/retreat_action' in k: continue                     # forced retreat removed on purpose
            if p in sandbag_files and k.startswith('/construction_ext/on_construction_actions/delay'): continue   # scripted sandbag ring
            unexpected['<removed key> ' + k] += 1; continue
        if a[k] == b[k]: continue
        if p in mg_files and MG_HIT.match(k): continue
        if k == '/weapon_bag/projectile/projectile':
            proj_mg_changed.append(p); continue
        if not any(x.match(k) for x in ALLOWED): unexpected[k] += 1
    extra = set(b) - set(a)
    if extra and not structural: unexpected['<new keys in> ' + rel] += 1
    if extra and rel in gun_ebps and not all(k.startswith(('/combat_ext/hardpoints/hardpoint#', '/action_apply_ext/actions/apply_modifiers_action')) for k in extra):
        unexpected['<unexpected new keys in gun> ' + rel] += 1
    if extra and rel in squads and not all(k.startswith('/squad_upgrade_ext/upgrades/upgrade') for k in extra):
        unexpected['<unexpected new keys in squad> ' + rel] += 1
ok(not unexpected, 'no field outside the allowed list differs from Kriegspiel ' + (str(unexpected.most_common(8)) if unexpected else ''))

W = {p: f for p, f in NF.items() if '/attrib/weapon/' in p and p in OF}
mg = [p for p, f in W.items() if ':bullet_' in str(OF[p].get('/weapon_bag/projectile/projectile', '')) and '/single_fire/' not in p and '/sub_machine_gun/' not in p and 'infantry_anti_tank_weapon' not in p]
ok(len(mg) == len(mg_files) and all(W[p]['/weapon_bag/projectile/projectile'] == '' for p in mg),
   f'MG: all {len(mg)} machine guns (infantry, team, vehicle, aircraft) fire vanilla hitscan (no physical bullet)')
hmg = [p for p in mg if any(x in p for x in ('hmg_team_', 'vickers_hmg', 'maxim_m1910', 'dshk_38_sokolov', '/m1919a4_30cal', '/m2hb_50cal_', 'sg43'))]
ok(len(hmg) >= 12 and all(W[p].get('/weapon_bag/suppression/amount', 0) > 0 for p in hmg), f'MG: all {len(hmg)} heavy MG teams have vanilla suppression again (they pin)')
KS_DMG = re.compile(r'^/weapon_bag/(damage|penetration|deflection|critical|burst|cooldown|reload|moving|cover_table|range|0x919f2f95|setup)/')
dd = [(p, k) for p in mg for k in W[p] if KS_DMG.match(k) and W[p][k] != OF[p].get(k) and not k.startswith('/weapon_bag/range/')]
ok(not dd, f'MG: damage / penetration / criticals / rate of fire / burst / cooldown / reload / cover / target table identical to Kriegspiel ({dd[:3]})')
STATS = re.compile(r'^/weapon_bag/(damage|accuracy|penetration|burst|cooldown|reload|aim|suppression|scatter|area_effect|moving|suppressed|deflection|critical|cover_table)/')
other = [p for p in W if p not in mg]
diff_stats = [(p, k) for p in other for k in W[p] if STATS.match(k) and W[p][k] != OF[p].get(k)]
ok(not diff_stats, f'DAMAGE MODEL: all {len(other)} other Kriegspiel weapons (rifles, SMGs, AT, guns, artillery) identical ({len(diff_stats)} diffs)')
ok(all(W[p].get('/weapon_bag/projectile/projectile') == OF[p].get('/weapon_bag/projectile/projectile') for p in other),
   'DAMAGE MODEL: rifles / SMGs / AT rifles / guns keep their original Kriegspiel projectile')

# ---------------- 3. Radio Man
radio_w = [p for p in added if '_vplus_radio_mp' in p]
rbad = []
for p in radio_w:
    src = p.replace('_vplus_radio_mp', '_mp'); a, b = NF[src], NF[p]
    for k in set(a) | set(b):
        if a.get(k) != b.get(k) and not k.endswith('/0x3251a3ee') and not (k in ('/pbgid', '/weapon_bag/name', '/weapon_bag/behaviour/enable_auto_target_search', '/weapon_bag/burst/can_burst')
                                         or k.startswith('/weapon_bag/priority/') or k.startswith('/weapon_bag/reload/duration/')):
            rbad.append((p, k))
    if b.get('/weapon_bag/range/max', 0) <= 1.0 or not b.get('/weapon_bag/behaviour/enable_auto_target_search') or b.get('/weapon_bag/reload/duration/max', 0) < 10: rbad.append((p, 'dummy/auto/cadence'))
ok(not rbad and len(radio_w) == 19, f'{len(radio_w)} radio weapons = copies of the REAL gun/rocket weapon (range > 1, auto-target on, >= 10 s per shot) ({rbad[:3]})')
ups = [p for p in added if '/upgrade/vplus_radio_' in p]
ok(len(ups) == 6 and all(NF[p].get('/upgrade_bag/time_cost/cost/munition') == 60.0 and NF[p].get('/upgrade_bag/local_max_limit') == 1.0 for p in ups), f'{len(ups)} Radio Man upgrades (5 factions + vehicles): 60 munitions, once per squad')
crew = [p for p in ups if 'radio_man_' in p]
ok(all(any(k.endswith('/unit_type') and str(v).endswith(('lieutenant_mp', 'forward_observation_officer_mp', 'officer_mp', 'soviet_officer_mp', 'field_officer_mp')) for k, v in NF[p].items()) and
       'action\\add_to_squad_loadout_action.lua' in NF[p].values() for p in crew) and len(crew) == 5, 'crew Radio Man adds one observer soldier (add_to_squad_loadout_action)')
ok(all('entities' in NF[p].values() and 'hardpoint_08' in NF[p].values() for p in ups), 'Radio Man enables hardpoint_08 on the gun entity (change_target_action -> entities)')
ok(not any(v == 'hardpoint_01' for p in ups for v in NF[p].values()), 'Radio Man never touches the gun\'s own weapons (hardpoint_01 untouched)')
hp_ok = all(sum(1 for k in NF['attrib/attrib/' + g] if re.match(r'^/combat_ext/hardpoints/hardpoint(#\d+)?/parent_hardpoint$', k)) == 8 for g in gun_ebps)
ok(hp_ok and len(gun_ebps) == 21, f'{len(gun_ebps)} support guns / rocket launchers have the radio weapon on hardpoint_08, disabled at spawn')
ok(len(squads) >= 25, f'{len(squads)} squads (all 5 factions) offer the Radio Man upgrade')
barr = [p for p in OF if '/abilities/' in p and ('barrage' in p) and OF[p] != NF[p] and any(k for k in OF[p] if OF[p][k] != NF[p][k] and k != '/ability_bag/range')]
ok(not barr, 'barrage / counter-barrage abilities untouched except their range scaling')
sb = [p for p in sandbag_files if any(fn in str(NF[p].values()) for fn in ('AE_SpawnPak43Defenses', 'AE_SpawnSupplyTruckAccessory'))]
ok(len(sandbag_files) == 3 and not sb, 'leFH 18 / ML-20 / B-4 no longer build the scripted sandbag ring')
fb = [p for p in NF if '/ai_settings/' in p and any(k.startswith('/ai_settings_bag/fallback/') and NF[p][k] != OF[p].get(k) for k in NF[p])]
ok(not fb, 'AI retreat / fallback logic = Kriegspiel (the AI may retreat by its own decision)')
gr = [p for p in NF if '/ai_ability/' in p and '/grenades/' in p and NF[p].get('/ai_ability_bag/ai_tactic/priority', -1) > 40]
ok(not gr, 'AI grenade priority lowered (no grenade spam)')

# ---------------- 3b. retreat
left = [p for p, t in T.items() if 'action\\retreat_action.lua' in str(NF[p].values()) and '/abilities/' not in p]
auto_left = [p for p, t in T.items() if 'soldier_auto_retreat' in p and 'retreat_action' in str(NF[p].values())]
ok(not left and not auto_left, f'no automatic forced retreat left (shells/weapons/entities/auto abilities) ({left[:3]})')
wr = [p for p in NF if p.endswith('withdraw_and_refit.rgd') and '/attrib/abilities/' in p]
ok(all('retreat_action' in str(NF[p].values()) for p in wr), 'player-ordered Withdraw and Refit still works')
bul = [p for p in NF if '/ebps/projectile/bullet_' in p]
ok(bul and all(NF[p].get('/entity_blueprint_ext/is_visible_in_game') is False for p in bul), f'all {len(bul)} bullet blueprints draw no shell model (vanilla tracer look)')

# ---------------- 4. ranges
rr = list(csv.DictReader(open(os.path.join(ROOT, 'reports', 'ranges_changes.csv'))))
ok(all(abs(float(r['new_max']) - round(float(r['old_max']) * 0.8, 4)) < 1e-3 for r in rr), f'{len(rr)} weapon max ranges are exactly 0.80 x Kriegspiel')
ok(all(not r['min(kept)'] or float(r['min(kept)']) < float(r['new_max']) for r in rr), 'min range < max range everywhere')

open(os.path.join(ROOT, 'reports', 'verification.txt'), 'w').write('\n'.join(lines) + f'\n\n{fails} failure(s)\n')
print('\n'.join(lines)); print(f'\n{fails} failure(s)'); sys.exit(1 if fails else 0)
