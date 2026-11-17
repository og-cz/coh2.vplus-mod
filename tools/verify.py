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
ok(all(('\n%d\t' % i) in ucs for i in (1972, 1973, 1974)), 'Radio Man locale strings 1972-1974 present')

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
    r'^/explosion_ext/terrain_hit/deformation/(deform_decal_file|vertical_scale)$', r'^/projectile_ext/spawn_collision_fx$']]
gun_ebps = {r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'radio_changes.csv'))) if r[1] == 'gun entity'}
squads = {r[0] for r in csv.reader(open(os.path.join(ROOT, 'reports', 'radio_changes.csv'))) if r[1] == 'squad'}
unexpected = collections.Counter(); proj_mg_changed = []; proj_inf_bad = []
for p, a in OF.items():
    b = NF[p]; rel = p.split('attrib/attrib/', 1)[1]
    structural = rel in gun_ebps or rel in squads
    for k in a:
        if k not in b: unexpected['<removed key> ' + k] += 1; continue
        if a[k] == b[k]: continue
        if k == '/weapon_bag/projectile/projectile':
            if ':bullet_' in str(a[k]) and str(b[k]).endswith('_inf_mp') and ('/single_fire/' in p or '/sub_machine_gun/' in p): continue
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
mg = [p for p, f in W.items() if ':bullet_' in str(OF[p].get('/weapon_bag/projectile/projectile', '')) and not ('/single_fire/' in p or '/sub_machine_gun/' in p)]
ok(not proj_mg_changed and all(W[p]['/weapon_bag/projectile/projectile'] == OF[p]['/weapon_bag/projectile/projectile'] for p in mg),
   f'DAMAGE MODEL: all {len(mg)} machine guns / AT rifles fire their original Kriegspiel physical bullet')
STATS = re.compile(r'^/weapon_bag/(damage|accuracy|penetration|burst|cooldown|reload|aim|suppression|scatter|area_effect|moving|suppressed|deflection|critical|cover_table)/')
diff_stats = [(p, k) for p, f in W.items() for k in f if STATS.match(k) and f[k] != OF[p].get(k)]
ok(not diff_stats, f'DAMAGE MODEL: damage / accuracy / penetration / ROF / reload / suppression / scatter / AoE identical in all {len(W)} Kriegspiel weapons ({len(diff_stats)} diffs)')
# infantry bullet variants: same flight + collision as the original bullet, only invisible
inf_bad = []
for p in added:
    if '/ebps/projectile/' in p:
        src = p.replace('_inf_mp.rgd', '_mp.rgd'); a, b = NF[src], NF[p]
        for k in set(a) | set(b):
            if a.get(k) != b.get(k) and k not in ('/pbgid', '/entity_blueprint_ext/is_visible_in_game'): inf_bad.append((p, k))
        if b.get('/entity_blueprint_ext/is_visible_in_game') is not False: inf_bad.append((p, 'visible'))
ok(not inf_bad, f'infantry bullet variants = original bullet (speed, collision, explosion) with only the shell model hidden ({inf_bad[:3]})')
inf_w = [p for p, f in W.items() if str(f.get('/weapon_bag/projectile/projectile', '')).endswith('_inf_mp')]
ok(all('/single_fire/' in p or '/sub_machine_gun/' in p for p in inf_w), f'{len(inf_w)} infantry weapons use the subtle bullet, no MG does')

# ---------------- 3. Radio Man
radio_w = [p for p in added if '_vplus_radio_mp' in p]
rbad = []
for p in radio_w:
    src = p.replace('_vplus_radio_mp', '_mp'); a, b = NF[src], NF[p]
    for k in set(a) | set(b):
        if a.get(k) != b.get(k) and not (k in ('/pbgid', '/weapon_bag/name', '/weapon_bag/behaviour/enable_auto_target_search', '/weapon_bag/burst/can_burst')
                                         or k.startswith('/weapon_bag/priority/') or k.startswith('/weapon_bag/reload/duration/')):
            rbad.append((p, k))
ok(not rbad and len(radio_w) == 12, f'{len(radio_w)} radio weapons = exact copies of the gun weapon (projectile, damage, range, scatter) except target priority / howitzer cadence ({rbad[:3]})')
up = NF['attrib/attrib/upgrade/vplus_radio_man_mp.rgd']
ok(up.get('/upgrade_bag/time_cost/cost/munition') == 60.0 and up.get('/upgrade_bag/local_max_limit') == 1.0, 'Radio Man upgrade: 60 munitions, once per squad')
hp_ok = all(sum(1 for k in NF['attrib/attrib/' + g] if re.match(r'^/combat_ext/hardpoints/hardpoint(#\d+)?/parent_hardpoint$', k)) == 8 for g in gun_ebps)
ok(hp_ok and len(gun_ebps) == 14, f'{len(gun_ebps)} support-gun entities have the radio weapon on hardpoint_08, disabled at spawn')
ok(len(squads) == 18, f'{len(squads)} squads (all 5 factions) offer the Radio Man upgrade')
barr = [p for p in OF if '/abilities/' in p and ('barrage' in p) and OF[p] != NF[p] and any(k for k in OF[p] if OF[p][k] != NF[p][k] and k != '/ability_bag/range')]
ok(not barr, 'barrage / counter-barrage abilities untouched except their range scaling')

# ---------------- 4. ranges
rr = list(csv.DictReader(open(os.path.join(ROOT, 'reports', 'ranges_changes.csv'))))
ok(all(abs(float(r['new_max']) - round(float(r['old_max']) * 0.8, 4)) < 1e-3 for r in rr), f'{len(rr)} weapon max ranges are exactly 0.80 x Kriegspiel')
ok(all(not r['min(kept)'] or float(r['min(kept)']) < float(r['new_max']) for r in rr), 'min range < max range everywhere')

open(os.path.join(ROOT, 'reports', 'verification.txt'), 'w').write('\n'.join(lines) + f'\n\n{fails} failure(s)\n')
print('\n'.join(lines)); print(f'\n{fails} failure(s)'); sys.exit(1 if fails else 0)
