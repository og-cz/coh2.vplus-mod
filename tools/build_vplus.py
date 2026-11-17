"""
Vanilla+ (built on Kriegspiel V5) - deterministic build script.

Reads   extracted_assets/   untouched copy of the Kriegspiel V5 archive
Writes  modified/           every file Vanilla+ changes or adds (decompressed)
        reports/            old -> new value of every change + audit
Pack with tools/pack.py, check with tools/verify.py  (or just run build.bat)

Sections
  1. Gunfire presentation  - Kriegspiel physical bullets KEPT (damage model), visuals changed
  2. Weapon ranges x0.80
  3. AI (aggressive)       - unchanged from the first personal build
  4. Performance           - per-bullet / per-fragment terrain deformation off
  5. Radio Man upgrade     - optional per-unit upgrade for mortars, infantry guns, howitzers
"""
import os, sys, json, csv, glob, copy, struct, collections, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rgd
rgd.load_dict()
H = rgd.h

SRC = os.path.join(ROOT, 'extracted_assets'); MOD = os.path.join(ROOT, 'modified'); REP = os.path.join(ROOT, 'reports')
ATTR = os.path.join(SRC, 'attrib', 'attrib')
G = '3f698c4a5048428d9fdb675aa488f596:'        # mod-local reference prefix (swapped for the Vanilla+ GUID at pack time)
RANGE_FACTOR = 0.80

# ------------------------------------------------------------- tunables
RADIO = {
    'munition_cost': 60.0,
    'build_time': 20.0,
    'sight_multiplier': 1.2,             # observer / radio spotting bonus for the unit
    'radio_hardpoint': 8,                # radio fire-mission weapon lives on hardpoint_08
    # target preference of the radio weapon (Kriegspiel default: threat 1, current_target 2, distance 3/2/1)
    'priority': {'threat': 40.0, 'current_target': 10.0, 'penetration': 2.0,
                 'distance': {'near': 1.0, 'mid': 1.0, 'far': 1.0}},
    # crewed guns: the upgrade adds one forward observer (officer model of the faction) to the squad
    'observer': {'aef': 'lieutenant_mp', 'british': 'forward_observation_officer_mp', 'german': 'officer_mp',
                 'soviet': 'soviet_officer_mp', 'west_german': 'field_officer_mp'},
    'upgrades': {
        'crew': {'name': 'vplus_radio_man_%s_mp', 'loc': (1972, 1973, 1974),
                 'screen_name': 'Radio Man',
                 'help_text': 'A forward observer with a field radio joins the crew (+1 soldier). He spots and calls fire on his own: '
                              'the gun now fires single aimed rounds at enemies your army can see - machine guns, AT guns, mortars, '
                              'vehicles and garrisons first, infantry in the open last. Steady fire support like a normal weapon '
                              '(one round every 5-14 s depending on the gun), not a spam barrage. Your manual barrages, smoke and counter-barrage work '
                              'exactly as before. +20% sight. The fire missions keep running even if the observer is killed.',
                 'extra_text': '+1 observer soldier. Gun auto-fires at priority targets. +20% sight.'},
        'vehicle': {'name': 'vplus_radio_set_mp', 'loc': (1975, 1976, 1977),
                    'screen_name': 'Radio Man',
                    'help_text': 'The crew gets a radio link to the front line. The launcher now fires single rockets / shells on its own '
                                 'at enemies your army can see - machine guns, AT guns, mortars, vehicles and garrisons first. Steady fire '
                                 '(one shot every 6-8 s), not a full salvo. Full barrages stay manual. +20% sight.',
                    'extra_text': 'Launcher auto-fires single shots at priority targets. +20% sight.'},
    },
}
# ebps name -> (kind, hardpoint of the REAL weapon to copy (Kriegspiel hardpoint_01 is often a range-1 dummy), seconds per radio shot)
SUPPORT_GUNS = {   # seconds per radio shot ~ vanilla auto-fire cadence: steady fire support, not a spam barrage
    'm2_60mm_mortar_mp': ('crew', 2, 5.0), 'granatewerfer_36_50mm_mortar_mp': ('crew', 2, 5.0), 'rm38_50mm_mortar_mp': ('crew', 2, 5.0),
    'm1_81mm_mortar_mp': ('crew', 2, 6.0), 'granatewerfer_34_81mm_mortar_mp': ('crew', 2, 6.0), 'pm41_82mm_mortar_mp': ('crew', 2, 6.0),
    'm2_107mm_mortar_mp': ('crew', 2, 8.0), 'granatewerfer_42_120mm_mortar_mp': ('crew', 2, 8.0), 'hm-120_38_mortar_mp': ('crew', 2, 8.0),
    'm1_75mm_pack_howitzer_mp': ('crew', 2, 6.0), 'le_ig_18_inf_support_gun_mp': ('crew', 2, 6.0),
    'howitzer_105mm_le_fh18_mp': ('crew', 2, 8.0), 'm1937_152mm_ml_20_artillery_mp': ('crew', 3, 10.0),
    'm1931_203mm_b-4_howitzer_artillery_mp': ('crew', 2, 14.0), 'brit_land_mattress_launcher_mp': ('crew', 2, 6.0),
    'katyusha_bm-13n_mp': ('vehicle', 2, 6.0), 'panzerwerfer_sdkfz_4_1_mp': ('vehicle', 2, 6.0),
    't34_calliope_mp': ('vehicle', 2, 6.0), 'halftrack_sdkfz_251_wurfrahmen_40_mp': ('vehicle', 3, 6.0),
    'm7b1_priest_mp': ('vehicle', 2, 8.0), 'sexton_spg_mp': ('vehicle', 2, 8.0),
}
ARTILLERY_SANDBAG_FUNCS = ('AE_SpawnPak43Defenses', 'AE_SpawnSupplyTruckAccessory_1', 'AE_SpawnSupplyTruckAccessory_2')

# ------------------------------------------------------------- helpers
def child(tab, name):
    hs = H(name) if isinstance(name, str) else name
    for e in tab:
        if e[0] == hs: return e
    return None
def node(tab, *names):
    cur = None; t = tab
    for n in names:
        if t is None: return None
        cur = child(t, n)
        if cur is None: return None
        t = cur[2] if cur[1] in (100, 101) else None
    return cur
def walk(tab, fn, path=()):
    for e in tab:
        p = path + (rgd.name(e[0]),); fn(p, e)
        if e[1] in (100, 101): walk(e[2], fn, p)
def r4(x): return float(f'{x:.4f}')

changed = {}   # rel -> (orig_bytes, table)      rel is relative to attrib/attrib
added = {}     # rel -> (template_bytes, table)  new files
def load(rel):
    if rel in changed: return changed[rel][1]
    d, t = rgd.load(os.path.join(ATTR, rel)); changed[rel] = (d, t); return t
def rel_of(name, folder):
    hits = glob.glob(os.path.join(ATTR, folder, '**', name + '.rgd'), recursive=True)
    return os.path.relpath(hits[0], ATTR).replace('\\', '/') if hits else None
log = collections.defaultdict(list)

# pbgid / action-id allocators.
# Mod-created instances use a dense block starting at 0x40000000 (Kriegspiel: 1073741824..1073742515) and the
# action ids (0x3251a3ee) a block above it. New ids MUST continue those blocks: ids far outside them crash the
# game when it loads the tuning pack.
used_pbgid = set(); used_action = set()
def _collect(tab):
    for h_, t, v in tab:
        if t == 1 and h_ == H('pbgid'): used_pbgid.add(v)
        elif t == 1 and h_ == 0x3251a3ee: used_action.add(v)
        elif t in (100, 101): _collect(v)
_next_pbgid = [None]; _next_action = [None]
def new_id():            # instance pbgid
    if _next_pbgid[0] is None: _next_pbgid[0] = max(x for x in used_pbgid if x >= 0x40000000) + 1
    v = _next_pbgid[0]; _next_pbgid[0] += 1; return v
def new_action_id():     # action id (0x3251a3ee)
    if _next_action[0] is None: _next_action[0] = max(x for x in used_action if x >= 0x40000000) + 1
    v = _next_action[0]; _next_action[0] += 1; return v

# ======================================================= 1. GUNFIRE
def weapon_class(rel):
    r = rel.replace('\\', '/')
    if '/single_fire/' in r or '/sub_machine_gun/' in r: return 'infantry'
    if 'infantry_anti_tank_weapon' in r: return 'at_rifle'
    return 'machine_gun'

def disable_deformation(t, rel, why):
    ex = child(t, 'explosion_ext')
    dfm = node(ex[2], 'terrain_hit', 'deformation') if ex else None
    if not dfm: return
    df = child(dfm[2], 'deform_decal_file'); vs = child(dfm[2], 'vertical_scale')
    if df and df[2]: log['perf'].append([rel, 'explosion_ext/terrain_hit/deformation/deform_decal_file', df[2], '', why]); df[2] = ''
    if vs and vs[2]: log['perf'].append([rel, 'explosion_ext/terrain_hit/deformation/vertical_scale', vs[2], 0.0, why]); vs[2] = 0.0

# ---- machine guns: vanilla hitscan fire, Kriegspiel damage
VANILLA_ATTR = os.environ.get('VPLUS_VANILLA_ATTR', '/home/claude/vanilla/out/attribdata/attrib')
MG_VANILLA_MAP = {   # Kriegspiel-only MG weapons -> closest vanilla weapon for the hit model
    'aef_base_m2hb_50_cal_api_mp': 'aef_base_m2hb_50cal_mp', 'm1919a4_30cal_api_mp': 'm1919a4_30cal_mp',
    'm2hb_50cal_api_mp': 'm2hb_50cal_mp', 'rifleman_m2stinger_lmg_mp': 'riflemen_30cal_lmg_mp',
    'bunker_mg_42_api_mp': 'bunker_mg42_mp', 'hmg_team_mg_42_api_mp': 'hmg_team_mg42_mp',
    'stuka_mg_81_turret_mp': 'stuka_mg_17_strafe_mp', 'bunker_vickers_hmg_api_mp': 'bunker_vickers_hmg_mp',
    'vickers_hmg_api_mp': 'vickers_hmg_mp', 'aec_vickers_pintle_mp': 'tank_vickers_k_pintle_mount_mp',
    'churchill_vickers_pintle_mp': 'churchill_vickers_k_mount_mp',
    'commando_vickers_k_light_machine_gun_mp': 'infantry_vickers_k_machine_gun_mp',
    'tommy_lewis_light_machine_gun_mp': 'tommy_bren_light_machine_gun_mp',
    'bunker_starting_postion_dshk_api_mp': 'bunker_starting_position_dshk_mp', 'dshk_38_sokolov_api_mp': 'dshk_38_sokolov_mp',
    'il2_12mm_berezin_turret_mp': 'stuka_mg_17_strafe_mp', 'm5_halftrack_quad_50cal_m2hb_mp': 'm5_halftrack_quad_50_cal_m2hb_mp',
    'maxim_m1910_hmg_api_mp': 'maxim_m1910_hmg_mp', 'sg43_goryunov_hmg_mp': 'maxim_m1910_hmg_mp',
    'il2_7mm_shkas_machine_gun_mp': 'stuka_mg_17_strafe_mp',
}
# hit model taken from vanilla (how a hitscan MG hits and pins). Everything else - damage, penetration, deflection,
# criticals, rate of fire, burst, cooldown, reload, range, cover table, target table, moving - stays Kriegspiel.
MG_ACCURACY = 0.35        # x vanilla hit chance (Kriegspiel damage is ~2x vanilla, Kriegspiel infantry have 30 HP)
MG_HIT_SECTIONS = ('accuracy', 'suppression', 'scatter', 'aim', 'priority', 'behaviour')
def _graft(ks_tab, v_tab, rel, prefix, strings=False):
    """copy every vanilla leaf value onto the same key path in Kriegspiel (layout untouched; refs never copied)"""
    seen = collections.Counter()
    for vh, vt, vv in v_tab:
        seen[vh] += 1; n = 0; tgt = None
        for e in ks_tab:
            if e[0] == vh:
                n += 1
                if n == seen[vh]: tgt = e; break
        if tgt is None or tgt[1] != vt: continue
        name = prefix + '/' + rgd.name(vh)
        if vt in (100, 101): _graft(tgt[2], vv, rel, name, strings); continue
        if vt == 3 and (not strings or ':' in vv or vv.endswith('.lua') or rgd.name(vh) == '$REF'): continue
        if vt not in (0, 1, 2, 3) or tgt[2] == vv: continue
        log['mg_hitscan'].append([rel, name, tgt[2], vv]); tgt[2] = vv

def mg_hitscan(rel, t, wb):
    base = os.path.basename(rel)[:-4]; vname = MG_VANILLA_MAP.get(base, base)
    hits = glob.glob(os.path.join(VANILLA_ATTR, 'weapon', '**', vname + '.rgd'), recursive=True)
    if not hits: raise SystemExit('no vanilla reference for machine gun ' + rel)
    vwb = child(rgd.load(hits[0])[1], 'weapon_bag')[2]
    for sec in MG_HIT_SECTIONS:
        k, v = child(wb[2], sec), child(vwb, sec)
        if k and v: _graft(k[2], v[2], rel, '/weapon_bag/' + sec)
    k, v = node(wb[2], 'area_effect', 'distance'), node(vwb, 'area_effect', 'distance')   # no hidden splash on top of the hit
    if k and v: _graft(k[2], v[2], rel, '/weapon_bag/area_effect/distance')
    for vh, vt, vv in vwb:                                       # vanilla tracer / muzzle / impact look
        nm = rgd.name(vh)
        if nm.startswith('fx_') and vt in (0, 1, 2, 3):
            e = child(wb[2], vh)
            if e and e[1] == vt and e[2] != vv and not (vt == 3 and ':' in vv):
                log['mg_hitscan'].append([rel, '/weapon_bag/' + nm, e[2], vv]); e[2] = vv
    # Kriegspiel infantry have 30 HP (vanilla 80): vanilla hit chance x Kriegspiel damage shreds squads instantly.
    # Scale the hit chance so a burst pins first and kills over a few seconds, like a Kriegspiel MG nest.
    for k in ('near', 'mid', 'far'):
        e = node(wb[2], 'accuracy', k)
        if e and e[1] == 0: e[2] = r4(e[2] * MG_ACCURACY)
    log['mg_hitscan'].append([rel, '/weapon_bag/accuracy', 'vanilla', 'vanilla x %g' % MG_ACCURACY])
    # target table: the game uses the FIRST matching unit type. Tanks are both 'vehicle' (damage 0.3) and 'heavy_vehicle'
    # (Kriegspiel: damage 0, penetration 0). With hit-scan every round reached the tank, so 'vehicle' killed them.
    # Put 'heavy_vehicle' first: tanks shrug off MG fire again, light vehicles still take damage.
    tt = child(wb[2], 0x919f2f95)
    if tt and tt[1] in (100, 101):
        ut = lambda e: (child(e[2], 'unit_type') or [0, 0, ''])[2] if e[1] in (100, 101) else ''
        hv = [e for e in tt[2] if ut(e) == 'heavy_vehicle']; vh = [i for i, e in enumerate(tt[2]) if ut(e) == 'vehicle']
        if hv and vh and tt[2].index(hv[0]) > vh[0]:
            ids_ = [e[0] for e in tt[2]]                 # keep the key sequence, swap the contents
            items = [e for e in tt[2] if e is not hv[0]]; items.insert(vh[0], hv[0])
            for e, h_ in zip(items, ids_): e[0] = h_
            tt[2][:] = items
            log['mg_hitscan'].append([rel, '/weapon_bag/target_table', 'vehicle before heavy_vehicle', 'heavy_vehicle first (tanks immune as in Kriegspiel)'])
    pr = node(wb[2], 'projectile', 'projectile')
    log['mg_hitscan'].append([rel, '/weapon_bag/projectile/projectile', pr[2], '']); pr[2] = ''
    log['gunfire'].append([rel, 'machine_gun', '', pr and 'bullet', '(hitscan, vanilla %s)' % vname, '', '', '', ''])

def gunfire(ref):
    inf_variant = {}                       # bullet name -> infantry variant name
    for f in sorted(glob.glob(os.path.join(ATTR, 'weapon', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/')
        t = load(rel); wb = child(t, 'weapon_bag')
        pr = node(wb[2], 'projectile', 'projectile')
        if not pr or ':bullet_' not in pr[2]: continue
        cls = weapon_class(rel)
        if cls == 'machine_gun':
            mg_hitscan(rel, t, wb); continue
        tr = child(wb[2], 'fx_tracer_name'); sp = child(wb[2], 'fx_tracer_speed'); mu = child(wb[2], 'fx_munition_name')
        v = ref.get(tr[2] if tr else '', {'fx_tracer_speed': 120.0, 'fx_munition_name': 'bullet'})
        bullet = pr[2].split(':', 1)[1]
        new_proj = pr[2]
        # every bullet blueprint now draws no shell model, so infantry keep their original bullet;
        # infantry vs machine-gun look comes from the vanilla tracer of each weapon (thin rifle / heavy MG)
        row = [rel, cls, tr[2] if tr else '', pr[2].split(':')[-1], new_proj.split(':')[-1],
               sp[2] if sp else '', v['fx_tracer_speed'], mu[2] if mu else '', v['fx_munition_name']]
        pr[2] = new_proj
        if sp: sp[2] = float(v['fx_tracer_speed'])          # vanilla tracer speed (visual)
        if mu: mu[2] = v['fx_munition_name']                # vanilla impact/munition FX (mg_phosphorus etc. removed)
        log['gunfire'].append(row)
    # all original bullet blueprints: stay visible (machine-gun look), but no terrain crater per bullet
    for f in sorted(glob.glob(os.path.join(ATTR, 'ebps', 'projectile', 'bullet_*.rgd'))):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        disable_deformation(t, rel, 'bullet impact (machine-gun projectile)')
        vis = node(t, 'entity_blueprint_ext', 'is_visible_in_game')
        if vis and vis[2]: log['gunfire_new_blueprints'].append([rel, 'original bullet', 'is_visible_in_game=False (vanilla tracer look)']); vis[2] = False
    # infantry variants: identical flight/collision (same damage model) but no glowing shell model
    for bullet, var in []:
        src = 'ebps/projectile/%s.rgd' % bullet
        d, t = rgd.load(os.path.join(ATTR, src)); t = copy.deepcopy(load(src))
        child(t, 'pbgid')[2] = new_id()
        vis = node(t, 'entity_blueprint_ext', 'is_visible_in_game'); vis[2] = False
        added['ebps/projectile/%s.rgd' % var] = (d, t)
        log['gunfire_new_blueprints'].append(['ebps/projectile/%s.rgd' % var, 'copy of ' + src, 'is_visible_in_game=False'])

# ======================================================= 2. RANGES x0.80
RANGE_DIRS = ('small_arms', 'ballistic_weapon', 'explosive_weapons/mortar', 'explosive_weapons/light_artillery',
              'explosive_weapons/heavy_artillery', 'flame_throwers')
EXCLUDE_TOKENS = ('shrapnel', 'ricochet', 'fragment', '_dot', 'dotdamage', 'grenade', 'mine')
def in_scope(rel):
    p = rel.split('/')
    if p[0] != 'weapon' or len(p) < 3: return False
    if not any('/'.join(p[2:]).startswith(d) for d in RANGE_DIRS): return False
    return not any(tok in rel.lower() for tok in EXCLUDE_TOKENS)
def ranges():
    for f in sorted(glob.glob(os.path.join(ATTR, 'weapon', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/')
        if not in_scope(rel): continue
        t = load(rel); wb = child(t, 'weapon_bag'); rg = child(wb[2], 'range')
        if not rg: continue
        mx = child(rg[2], 'max'); mn = child(rg[2], 'min')
        if not mx or mx[2] <= 1.0: continue
        if mn and mn[2] >= mx[2]: continue
        dist = child(rg[2], 'distance'); old = {'max': mx[2]}
        mx[2] = r4(mx[2] * RANGE_FACTOR)
        for k in ('near', 'mid', 'far'):
            e = child(dist[2], k) if dist else None
            if e: old[k] = e[2]
            if e and e[2] > 0: e[2] = r4(e[2] * RANGE_FACTOR)
        if mn and mn[2] >= mx[2]: mn[2] = r4(mn[2] * RANGE_FACTOR)
        g = lambda k: child(dist[2], k)[2] if dist and child(dist[2], k) else ''
        nm = node(wb[2], 'name')
        log['ranges'].append([rel, nm[2] if nm else '', mn[2] if mn else '', old['max'], mx[2],
                              old.get('near', ''), g('near'), old.get('mid', ''), g('mid'), old.get('far', ''), g('far')])
def barrage_abilities():
    for f in sorted(glob.glob(os.path.join(ATTR, 'abilities', '**', '*.rgd'), recursive=True)):
        if b'artillery_attack' not in open(f, 'rb').read(): continue
        rel = os.path.relpath(f, ATTR).replace('\\', '/')
        found = []; t = load(rel)
        walk(t, lambda p, e: found.append(1) if p[-1] == 'artillery_attack' else None)
        ab = child(t, 'ability_bag'); rg = child(ab[2], 'range') if ab else None
        if not found or not rg or rg[1] != 0 or rg[2] <= 0: continue
        old = rg[2]; rg[2] = r4(old * RANGE_FACTOR); log['ability_ranges'].append([rel, old, rg[2]])
def additive_range_modifiers():
    for f in sorted(glob.glob(os.path.join(ATTR, '**', '*.rgd'), recursive=True)):
        if b'range_weapon_modifier' not in open(f, 'rb').read(): continue
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        def fn(p, e):
            if e[1] != 100: return
            ref = child(e[2], '$REF'); use = child(e[2], 'usage_type'); val = child(e[2], 'value')
            if ref and ref[2] == 'modifiers\\range_weapon_modifier.lua' and use and use[2] == 'addition' and val:
                old = val[2]; val[2] = r4(old * RANGE_FACTOR)
                log['ability_ranges'].append([rel + ' (additive range_weapon_modifier)', old, val[2]])
        walk(t, fn)

# ======================================================= 2b. NO FORCED RETREAT
def no_forced_retreat():
    """Kriegspiel forces squads to retreat (last man standing, shell shock from explosions).
    Only the player (or the AI's own decision) may order a retreat: every retreat_action is removed.
    The 'soldier_stressed' critical and suppression/pinning stay."""
    RA = 'action\\retreat_action.lua'
    for f in sorted(glob.glob(os.path.join(ATTR, '**', '*.rgd'), recursive=True)):
        if b'retreat_action' not in open(f, 'rb').read(): continue
        rel = os.path.relpath(f, ATTR).replace('\\', '/')
        if rel.startswith('abilities/'):
            d0, t0 = rgd.load(f); act = node(t0, 'ability_bag', 'activation')
            if not act or act[2] != 'always_on': continue      # player-ordered abilities (e.g. Withdraw and Refit) stay
        t = load(rel); n = [0]
        def strip(tab):
            for e in tab:
                if e[1] in (100, 101):
                    keep = []
                    for x in e[2]:
                        ref = child(x[2], '$REF') if x[1] in (100, 101) else None
                        if ref and ref[2] == RA: n[0] += 1
                        else: keep.append(x)
                    e[2][:] = keep
                    strip(e[2])
        strip(t)
        if n[0]: log['retreat'].append([rel, n[0], 'retreat_action removed'])

# ======================================================= 3. AI (kept from personal build)
COVER_RATING = {'tp_heavy': 6.0, 'tp_light': 3.0, 'tp_garrison_cover': 8.0, 'tp_trench': 12.0, 'tp_z_bunker': 10.0,
                'tp_z_emplacement': 3.0, 'tp_zz_team_weapon_heavy': 5.0, 'tp_garrison_halftrack': 5.0}
AI_SETTINGS = {('skirmish_settings', 'combat_eval', 'combat_eval_required_win_ratio_at_min_class_rating'): 0.70,
               ('skirmish_settings', 'combat_eval', 'combat_eval_required_win_ratio_at_max_class_rating'): 0.35,
               ('skirmish_settings', 'tasks', 'max_num_attack_objectives'): 4,
               ('skirmish_settings', 'tasks', 'max_num_capture_tasks'): 6}
TACTIC_TIME = 0x1810bb21
GRENADE_PRIORITY = {'anti_infantry': 20.0, 'anti_tank': 40.0, 'smoke': 35.0}   # Kriegspiel: 85 / 85 / 50 -> AI threw them constantly
def ai():
    for f in sorted(glob.glob(os.path.join(ATTR, 'ai_settings', '*.rgd'))):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel); bag = child(t, 'ai_settings_bag')[2]
        ct = node(bag, 'combat_ratings', 'cover_table')
        for cov, val in COVER_RATING.items():
            e = node(ct[2], cov, 'class_rating_multiplier')
            if e and e[2] != val: log['ai'].append([rel, 'cover_table/%s/class_rating_multiplier' % cov, e[2], val]); e[2] = val
        for path, val in AI_SETTINGS.items():   # AI fallback / retreat logic stays Kriegspiel (the AI may retreat)
            e = node(bag, *path)
            if e is None: continue
            val = type(e[2])(val)
            if e[2] != val: log['ai'].append([rel, '/'.join(path), e[2], val]); e[2] = val
    for f in sorted(glob.glob(os.path.join(ATTR, 'ai_squad', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        tac = node(t, 'ai_squad_bag', 'tactics')
        if not tac: continue
        assault = any(s in rel.lower() for s in ('assault', 'stormtrooper', 'shock'))
        for name, (cap, tl_new) in {'hold_tactic': (40.0, 15.0), 'cover_tactic': (300.0, 25.0)}.items():
            e = child(tac[2], name)
            if not e: continue
            pr = child(e[2], 'priority'); tl = child(e[2], TACTIC_TIME)
            if pr and pr[2] > cap: log['ai'].append([rel, name + '/priority', pr[2], cap]); pr[2] = cap
            if tl and (tl[2] < 0 or tl[2] > tl_new): log['ai'].append([rel, name + '/time_limit', tl[2], tl_new]); tl[2] = tl_new
        if assault:
            pr = node(tac[2], 'rush_at_target', 'priority')
            if pr and 0 <= pr[2] < 300: log['ai'].append([rel, 'rush_at_target/priority', pr[2], 300.0]); pr[2] = 300.0
    for f in sorted(glob.glob(os.path.join(ATTR, 'ai_ability', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        pr = node(t, 'ai_ability_bag', 'ai_tactic', 'priority'); at = node(t, 'ai_ability_bag', 'ai_tactic')
        if not pr or pr[2] < 0: continue
        filt = ''.join(str((child(at[2], k) or [0, 0, ''])[2]) for k in ('squad_target_filter', 'position_target_filter', 'entity_target_filter'))
        lr = rel.lower(); new = None
        if 'BestEnemyInfantryGrenade' in filt: new = GRENADE_PRIORITY['anti_infantry']          # frag grenades / rifle grenades
        elif ('/grenades/' in lr or '/accessory_weapons/' in lr) and 'FirstEnemyVehicle' in filt: new = GRENADE_PRIORITY['anti_tank']
        elif '/grenades/' in lr and 'CausingSuppression' in filt: new = GRENADE_PRIORITY['smoke']
        elif 'barrage' in lr or 'offmap' in lr: new = max(pr[2], 150.0)
        if new and new != pr[2]: log['ai'].append([rel, 'ai_tactic/priority', pr[2], new]); pr[2] = new

# ======================================================= 4. PERFORMANCE
SHRAPNEL = ('explosion_shrapnel_projectile_mp', 'explosion_wp_fragment_projectile_mp', 'explosion_ricochet_projectile_mp')
def perf():
    for f in sorted(glob.glob(os.path.join(ATTR, 'ebps', 'projectile', '*.rgd'))):
        b = os.path.basename(f)[:-4]
        if not (b in SHRAPNEL or b.startswith('shell_ricochet_')): continue
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        disable_deformation(t, rel, 'shrapnel fragment')
        sc = node(t, 'projectile_ext', 'spawn_collision_fx')
        if sc and sc[2]: log['perf'].append([rel, 'projectile_ext/spawn_collision_fx', True, False, 'shrapnel fragment']); sc[2] = False

# ======================================================= 5. RADIO MAN
VANILLA_UPGRADE_TEMPLATE = os.path.join(HERE, 'templates', 'aef_tank_commander_mp.rgd')   # vanilla upgrade used as structure template

def modifier(tpl_mod_entry, ref, value, usage, target, application):
    m = copy.deepcopy(tpl_mod_entry)
    m[0] = H(ref.split('\\')[-1][:-4])
    child(m[2], '$REF')[2] = ref; child(m[2], 'value')[2] = float(value)
    child(m[2], 'usage_type')[2] = usage; child(m[2], 'target_type_name')[2] = target
    child(m[2], 'application_type')[2] = application; child(m[2], 'modifier_id')[2] = ''
    child(m[2], 'exclusive')[2] = False
    if ref.split('\\')[-1] in ('enable_weapon_modifier.lua', 'auto_target_enable_weapon_modifier.lua'):
        # these modifier types have no tooltip fields in the game's data layout - extra keys crash the loader
        m[2] = [e for e in m[2] if rgd.name(e[0]) not in ('positive_tooltip', 'negative_tooltip')]
    return m

def _tpl(name): return rgd.load(os.path.join(HERE, 'templates', name))

def radio_man():
    hp = RADIO['radio_hardpoint']; hpname = 'hardpoint_%02d' % hp
    tpl_d, tpl_t = _tpl('aef_tank_commander_mp.rgd')                     # vanilla upgrade (structure)
    tpl_apply = copy.deepcopy(node(tpl_t, 'upgrade_bag', 'actions')[2][1])          # apply_modifiers_action
    tpl_mod = copy.deepcopy(child(tpl_apply[2], 'modifiers')[2][1])                 # a modifier entry
    _, med = _tpl('troop_support_medics_upg.rgd')                         # vanilla: add_to_squad_loadout_action
    tpl_loadout = copy.deepcopy(node(med, 'upgrade_bag', 'actions')[2][0])
    _, slot = _tpl('m2hb_turret_mounted_sherman_mp.rgd')                  # vanilla: change_target_action(entities)->apply_modifiers
    tpl_ct = copy.deepcopy([e for e in node(slot, 'slot_item_bag', 'on_add_actions')[2] if rgd.name(e[0]) == 'change_target_action'][0])

    def fire_mission_action():
        """squad upgrade -> every entity of the squad (the gun / the vehicle): enable hardpoint_08, +20% sight"""
        ct = copy.deepcopy(tpl_ct); child(ct[2], 0x3251a3ee)[2] = new_action_id()
        am = child(child(ct[2], 'actions')[2], 'apply_modifiers_action'); child(am[2], 0x3251a3ee)[2] = new_action_id()
        child(am[2], 'modifiers')[2] = [
            modifier(tpl_mod, 'modifiers\\enable_weapon_modifier.lua', 1.0, 'enable', hpname, 'apply_to_weapon'),
            modifier(tpl_mod, 'modifiers\\sight_radius_modifier.lua', RADIO['sight_multiplier'], 'multiplication', '', 'apply_to_entity')]
        return ct

    # vanilla multiplayer pattern (grenadier_squad_mp, veteran squad leader): sbps squad_action_apply_ext
    #   actions      -> requirement_action(required_squad_upgrade X) -> add_to_squad_loadout_action      (squad level)
    #   0xc4ddb307   -> requirement_action(required_squad_upgrade X) -> apply_modifiers_action           (every entity)
    _, gren = _tpl('grenadier_squad_mp.rgd')
    g_sae = child(gren, 'squad_action_apply_ext')[2]
    tpl_req_sq = copy.deepcopy(child(child(g_sae, 'actions')[2], 'requirement_action'))
    tpl_req_en = copy.deepcopy(child(child(g_sae, 0xc4ddb307)[2], 'requirement_action'))
    tpl_sae_actions = [e for e in g_sae if rgd.name(e[0]) == 'actions'][0]
    tpl_sae_ent = [e for e in g_sae if e[0] == 0xc4ddb307][0]

    def squad_effects(t, rel, kind, faction, uname):
        sae = child(t, 'squad_action_apply_ext')
        if sae is None: raise SystemExit('no squad_action_apply_ext in ' + rel)
        def req(tpl, actions):
            r = copy.deepcopy(tpl); child(r[2], 0x3251a3ee)[2] = new_action_id()
            node(r[2], 'requirement_table', 'required_squad_upgrade', 'upgrade_name')[2] = G + uname
            child(r[2], 'action_table')[2] = actions; return r
        def slot(tpl):
            e = child(sae[2], tpl[0])
            if e is None: e = [tpl[0], tpl[1], []]; sae[2].append(e)
            return e
        if kind == 'crew':
            lo = copy.deepcopy(tpl_loadout); child(lo[2], 0x3251a3ee)[2] = new_action_id()
            child(lo[2], 'unit_type')[2] = G + RADIO['observer'][faction]; child(lo[2], 'count')[2] = 1
            slot(tpl_sae_actions)[2].append(req(tpl_req_sq, [lo]))
        am = copy.deepcopy(tpl_apply); child(am[2], 0x3251a3ee)[2] = new_action_id()
        child(am[2], 'permanent')[2] = False; child(am[2], 'duration')[2] = 0.0
        child(am[2], 'modifiers')[2] = [
            modifier(tpl_mod, 'modifiers\\enable_weapon_modifier.lua', 1.0, 'enable', hpname, 'apply_to_weapon'),
            modifier(tpl_mod, 'modifiers\\sight_radius_modifier.lua', RADIO['sight_multiplier'], 'multiplication', '', 'apply_to_entity')]
        slot(tpl_sae_ent)[2].append(req(tpl_req_en, [am]))

    def make_upgrade(kind, faction=None):
        U = RADIO['upgrades'][kind]; name = U['name'] % faction if '%s' in U['name'] else U['name']
        rel = 'upgrade/%s.rgd' % name
        if rel in added: return name
        up = copy.deepcopy(tpl_t); bag = child(up, 'upgrade_bag')[2]
        child(up, 'pbgid')[2] = new_id()
        ui = child(bag, 'ui_info')[2]
        for k, lid in zip(('screen_name', 'help_text', 'extra_text'), U['loc']):
            e = child(ui, k); e[1] = 4; e[2] = '$' + G + str(lid)     # 4 = localized string (Kriegspiel uses the same)
        child(ui, 'icon_name')[2] = 'Icons_commander_cmdr_soviet_radio_intercept'
        child(ui, 'hotkey_name')[2] = 'R'
        child(bag, 'actions')[2] = []          # multiplayer: the upgrade is a flag, the squad applies the effects (see squad_effects)
        cost = node(bag, 'time_cost', 'cost')[2]
        for k in ('popcap', 'action', 'fuel', 'command', 'manpower'): child(cost, k)[2] = 0.0
        child(cost, 'munition')[2] = RADIO['munition_cost']
        node(bag, 'time_cost', 'time_seconds')[2] = RADIO['build_time']
        child(bag, 'requirements')[2] = []            # buyable anywhere, once per squad
        child(bag, 'local_max_limit')[2] = 1.0
        for k in ('code_1', 'code_2', 'code_3'):
            e = node(bag, 'speech_code_3', k)
            if e: e[2] = ''
        added[rel] = (tpl_d, up)
        log['radio'].append([rel, 'new upgrade', '%s: %g munitions, %g s, once per squad%s' % (kind, RADIO['munition_cost'], RADIO['build_time'],
                             ', adds 1x ' + RADIO['observer'][faction] if kind == 'crew' else '')])
        return name

    # ---- per gun / launcher: radio weapon (copy of the REAL weapon) on hardpoint_08, disabled until the upgrade
    eligible = {}
    for name, (kind, src_hp, shot_s) in SUPPORT_GUNS.items():
        rel = rel_of(name, 'ebps')
        if not rel: log['radio_skipped'].append([name, 'ebps not in mod']); continue
        t = load(rel)
        hps = node(t, 'combat_ext', 'hardpoints')[2]
        if len(hps) >= hp: log['radio_skipped'].append([name, 'already %d hardpoints' % len(hps)]); continue
        wname = child(node(hps[src_hp - 1][2], 'weapon_table')[2][0][2], 'weapon')[2].split(':')[-1]
        wrel = rel_of(wname, 'weapon')
        if not wrel: log['radio_skipped'].append([name, 'weapon %s not in mod' % wname]); continue
        wb0 = child(load(wrel), 'weapon_bag')[2]
        if node(wb0, 'range', 'max')[2] <= 1.0: raise SystemExit('radio source weapon is a dummy: %s %s' % (name, wname))
        radio_w = wname[:-3] + '_vplus_radio_mp' if wname.endswith('_mp') else wname + '_vplus_radio_mp'
        wrel_new = wrel.rsplit('/', 1)[0] + '/' + radio_w + '.rgd'
        if wrel_new not in added:
            wd, _ = rgd.load(os.path.join(ATTR, wrel)); wt = copy.deepcopy(load(wrel))   # after range scaling
            child(wt, 'pbgid')[2] = new_id()
            wb = child(wt, 'weapon_bag')[2]
            pri = child(wb, 'priority')[2]
            for k in ('threat', 'current_target', 'penetration'):
                e = child(pri, k)
                if e: e[2] = RADIO['priority'][k]
            for k, v in RADIO['priority']['distance'].items():
                e = node(pri, 'distance', k)
                if e: e[2] = v
            node(wb, 'behaviour', 'enable_auto_target_search')[2] = True
            for k in ('min', 'max'): node(wb, 'reload', 'duration', k)[2] = shot_s
            cb = node(wb, 'burst', 'can_burst')
            if cb: cb[2] = False
            nm = child(wb, 'name')
            if nm and nm[1] == 3: nm[2] = (nm[2] + ' (Radio Man)')[:120]
            added[wrel_new] = (wd, wt)
            log['radio'].append([wrel_new, 'new weapon', 'copy of %s; auto-target on; one shot / %gs; no burst; priority threat=%g current_target=%g' % (
                wrel, shot_s, RADIO['priority']['threat'], RADIO['priority']['current_target'])])
        pad_src = hps[1] if len(hps) > 1 else hps[0]
        while len(hps) < hp - 1:
            e = copy.deepcopy(pad_src); wt_ = node(e[2], 'weapon_table')[2]; del wt_[1:]
            child(wt_[0][2], 'weapon')[2] = ''; child(e[2], 'receives_attack_commands')[2] = False; hps.append(e)
        e = copy.deepcopy(hps[src_hp - 1]); wt_ = node(e[2], 'weapon_table')[2]; del wt_[1:]
        child(wt_[0][2], 'weapon')[2] = G + radio_w
        child(e[2], 'receives_attack_commands')[2] = False; hps.append(e)
        aae = node(t, 'action_apply_ext', 'actions')
        a = copy.deepcopy(tpl_apply); child(a[2], 0x3251a3ee)[2] = new_action_id()
        child(a[2], 'permanent')[2] = True; child(a[2], 'duration')[2] = 0.0
        child(a[2], 'modifiers')[2] = [modifier(tpl_mod, 'modifiers\\enable_weapon_modifier.lua', -1.0, 'enable', hpname, 'apply_to_weapon')]
        aae[2].append(a)
        eligible[name] = kind
        log['radio'].append([rel, 'gun entity', '%s: %s = %s (off until Radio Man), copied from hardpoint_%02d %s' % (kind, hpname, radio_w, src_hp, wname)])
    # ---- squads that own those guns get the upgrade button
    for f in sorted(glob.glob(os.path.join(ATTR, 'sbps', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); d0, t0 = rgd.load(f)
        types = []
        walk(t0, lambda p, e: types.append(e[2]) if p[-1] == 'type' and len(p) > 2 and p[-3] == 'unit_list' and e[1] == 3 else None)
        guns = [x.split(':')[-1] for x in types if x.split(':')[-1] in eligible]
        if not guns: continue
        kind = eligible[guns[0]]; faction = rel.split('/')[2]
        if kind == 'crew' and faction not in RADIO['observer']: log['radio_skipped'].append([rel, 'faction ' + faction]); continue
        t = load(rel); ups = node(t, 'squad_upgrade_ext', 'upgrades')
        if ups is None: log['radio_skipped'].append([rel, 'no squad_upgrade_ext']); continue
        uname = make_upgrade(kind, faction)
        entry = [H('upgrade'), 3, G + uname]
        if not any(e[2] == entry[2] for e in ups[2]): ups[2].append(entry)
        squad_effects(t, rel, kind, faction, uname)
        log['radio'].append([rel, 'squad', 'Radio Man button (%s, %s)' % (uname, guns[0])])

def no_artillery_sandbags():
    """Kriegspiel leFH 18 / ML-20 / B-4 run scar scripts on placement that build a ring of sandbags and props
    (also when the gun is spawned by cheat / spawner mods). Remove those scripted spawns: the gun is just a unit."""
    for f in sorted(glob.glob(os.path.join(ATTR, 'ebps', '**', 'team_weapons', '**', '*.rgd'), recursive=True)):
        raw = open(f, 'rb').read()
        if not any(fn.encode() in raw for fn in ARTILLERY_SANDBAG_FUNCS): continue
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel)
        oca = node(t, 'construction_ext', 'on_construction_actions')
        if not oca: continue
        def calls(e):
            out = []; walk([e], lambda p, x: out.append(x[2]) if p[-1] == 'function_name' else None); return out
        keep = []
        for e in oca[2]:
            fns = calls(e) if e[1] in (100, 101) else []
            if fns and all(fn in ARTILLERY_SANDBAG_FUNCS for fn in fns):
                log['sandbags'].append([rel, 'construction_ext/on_construction_actions/' + rgd.name(e[0]), ' + '.join(fns)])
            else: keep.append(e)
        oca[2][:] = keep

def locale():
    p = os.path.join(SRC, 'locale', 'english', 'english.ucs')
    txt = open(p, 'rb').read().decode('utf-16')
    lines = txt.rstrip('\r\n').split('\r\n')
    have = {l.split('\t', 1)[0] for l in lines}
    for U in RADIO['upgrades'].values():
        for k, i in zip(('screen_name', 'help_text', 'extra_text'), U['loc']):
            if str(i) in have: raise SystemExit('locale id %d already used' % i)
            lines.append('%d\t%s' % (i, U[k]))
    out = os.path.join(MOD, 'locale', 'english', 'english.ucs'); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(('\r\n'.join(lines) + '\r\n').encode('utf-16'))   # utf-16 with BOM, CRLF like the original

# ======================================================= main
NO_RADIO = os.environ.get('VPLUS_NO_RADIO') == '1'
def main():
    import shutil
    for f in glob.glob(os.path.join(ATTR, '**', '*.rgd'), recursive=True):
        try: _collect(rgd.load(f)[1])
        except Exception: pass
    ref = json.load(open(os.path.join(REP, 'vanilla_gunfire_reference.json')))
    gunfire(ref); ranges(); barrage_abilities(); additive_range_modifiers(); no_forced_retreat(); ai(); perf(); no_artillery_sandbags()
    if not NO_RADIO: radio_man()
    if os.path.isdir(MOD): shutil.rmtree(MOD)
    n_mod = n_add = 0
    for rel, (orig, tab) in changed.items():
        new = rgd.save(orig, tab)
        if new != orig:
            out = os.path.join(MOD, 'attrib', 'attrib', rel); os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, 'wb').write(new); n_mod += 1
    # every action id in a new file must be unique game-wide (Kriegspiel has 0 duplicates)
    def renumber(tab):
        for e in tab:
            if e[0] == 0x3251a3ee and e[1] == 1: e[2] = new_action_id()
            elif e[1] in (100, 101): renumber(e[2])
    for rel in sorted(added): renumber(added[rel][1])
    for rel, (tpl, tab) in added.items():
        out = os.path.join(MOD, 'attrib', 'attrib', rel); os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(rgd.save(tpl, tab)); n_add += 1
    if not NO_RADIO: locale()
    json.dump(sorted(added), open(os.path.join(REP, 'added_files.json'), 'w'), indent=1)
    hdr = {'gunfire': ['file', 'class', 'fx_tracer_name', 'old_projectile', 'new_projectile', 'old_tracer_speed', 'new_tracer_speed', 'old_munition', 'new_munition'],
           'gunfire_new_blueprints': ['file', 'source', 'change'],
           'ranges': ['file', 'name', 'min(kept)', 'old_max', 'new_max', 'old_near', 'new_near', 'old_mid', 'new_mid', 'old_far', 'new_far'],
           'ability_ranges': ['file', 'old', 'new'], 'ai': ['file', 'field', 'old', 'new'], 'perf': ['file', 'field', 'old', 'new', 'why'],
           'radio': ['file', 'what', 'detail'], 'radio_skipped': ['item', 'reason'], 'retreat': ['file', 'removed', 'what'],
           'mg_hitscan': ['file', 'field', 'kriegspiel', 'new (vanilla hit model)'], 'sandbags': ['file', 'removed', 'scripts']}
    for k, h in hdr.items():
        with open(os.path.join(REP, k + '_changes.csv'), 'w', newline='') as fo:
            w = csv.writer(fo); w.writerow(h); w.writerows(log[k])
    print('modified files:', n_mod, ' new files:', n_add, ' + locale')
    for k in hdr: print('  %-24s %d' % (k, len(log[k])))

if __name__ == '__main__':
    main()
