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
    'upgrade_name': 'vplus_radio_man_mp',
    'munition_cost': 60.0,
    'build_time': 20.0,
    'howitzer_reload_seconds': 25.0,     # howitzers have no auto-fire by default; with Radio Man: 1 shell / ~25 s
    'sight_multiplier': 1.2,             # radio spotting bonus for the team
    'radio_hardpoint': 8,                # radio weapon lives on hardpoint_08 on every eligible gun
    # target preference of the radio weapon (Kriegspiel default mortar: threat 1, current_target 2, distance 3/2/1)
    'priority': {'threat': 40.0, 'current_target': 10.0, 'penetration': 2.0,
                 'distance': {'near': 1.0, 'mid': 1.0, 'far': 1.0}},
    'loc': {'screen_name': 'Radio Man',
            'help_text': 'A radio operator joins the crew. The gun picks its own targets by importance: MG teams, AT guns, mortars, vehicles and garrisons first, lone squads only when nothing better is in range. Howitzers gain slow, deliberate auto-fire. Barrages and counter-barrage are unchanged.',
            'extra_text': 'Fire direction: priority targets. +20% sight.'},
    'loc_ids': {'screen_name': 1972, 'help_text': 1973, 'extra_text': 1974},
}
SUPPORT_GUNS = {   # ebps name -> (kind, source hardpoint index of the weapon the radio copy is cloned from)
    'm2_60mm_mortar_mp': ('mortar', 1), 'm1_81mm_mortar_mp': ('mortar', 1), 'm2_107mm_mortar_mp': ('mortar', 1),
    'granatewerfer_36_50mm_mortar_mp': ('mortar', 1), 'granatewerfer_34_81mm_mortar_mp': ('mortar', 1),
    'granatewerfer_42_120mm_mortar_mp': ('mortar', 1), 'rm38_50mm_mortar_mp': ('mortar', 1),
    'pm41_82mm_mortar_mp': ('mortar', 1), 'hm-120_38_mortar_mp': ('mortar', 1),
    'm1_75mm_pack_howitzer_mp': ('infantry_gun', 1), 'le_ig_18_inf_support_gun_mp': ('infantry_gun', 1),
    'howitzer_105mm_le_fh18_mp': ('howitzer', 2), 'm1937_152mm_ml_20_artillery_mp': ('howitzer', 2),
    'm1931_203mm_b-4_howitzer_artillery_mp': ('howitzer', 2),
}

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

# pbgid / action-id allocator (unique against everything in the mod and vanilla reference ranges)
used = set()
def _collect(tab):
    for h_, t, v in tab:
        if t == 1 and h_ in (H('pbgid'), 0x3251a3ee): used.add(v)
        elif t in (100, 101): _collect(v)
_next = [1074500000]
def new_id():
    while _next[0] in used: _next[0] += 1
    used.add(_next[0]); return _next[0]

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

def gunfire(ref):
    inf_variant = {}                       # bullet name -> infantry variant name
    for f in sorted(glob.glob(os.path.join(ATTR, 'weapon', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/')
        t = load(rel); wb = child(t, 'weapon_bag')
        pr = node(wb[2], 'projectile', 'projectile')
        if not pr or ':bullet_' not in pr[2]: continue
        cls = weapon_class(rel)
        tr = child(wb[2], 'fx_tracer_name'); sp = child(wb[2], 'fx_tracer_speed'); mu = child(wb[2], 'fx_munition_name')
        v = ref.get(tr[2] if tr else '', {'fx_tracer_speed': 120.0, 'fx_munition_name': 'bullet'})
        bullet = pr[2].split(':', 1)[1]
        new_proj = pr[2]
        if cls == 'infantry':
            inf_variant.setdefault(bullet, bullet.replace('_mp', '') + '_inf_mp')
            new_proj = G + inf_variant[bullet]
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
    for bullet, var in sorted(inf_variant.items()):
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
AI_NO_RETREAT = {('fallback', 'retreat_health_ratio'): 0.0, ('fallback', 'retreat_combat_rating_ratio'): 0.0,
                 ('fallback', 'retreat_capacity_ratio'): 0.0, ('fallback', 'fallback_combat_rating_ratio'): 0.0,
                 ('fallback', 'fallback_capacity_ratio'): 0.0, ('fallback', 'fallback_squad_health_ratio'): 0.0,
                 ('fallback', 'fallback_vehicle_health_ratio'): 0.0, ('fallback', 'retreat_on_pinned'): False,
                 ('fallback', 'retreat_on_suppression'): False}
def ai():
    for f in sorted(glob.glob(os.path.join(ATTR, 'ai_settings', '*.rgd'))):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); t = load(rel); bag = child(t, 'ai_settings_bag')[2]
        ct = node(bag, 'combat_ratings', 'cover_table')
        for cov, val in COVER_RATING.items():
            e = node(ct[2], cov, 'class_rating_multiplier')
            if e and e[2] != val: log['ai'].append([rel, 'cover_table/%s/class_rating_multiplier' % cov, e[2], val]); e[2] = val
        for path, val in list(AI_SETTINGS.items()) + list(AI_NO_RETREAT.items()):
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
        if 'smoke' in lr or 'wp_grenade' in lr or 'no_77' in lr or 'Smoke' in filt: new = 300.0
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

def radio_man():
    hp = RADIO['radio_hardpoint']; hpname = 'hardpoint_%02d' % hp
    tpl_d, tpl_t = rgd.load(VANILLA_UPGRADE_TEMPLATE)
    tpl_apply = copy.deepcopy(node(tpl_t, 'upgrade_bag', 'actions')[2][1])          # apply_modifiers_action
    tpl_mod = copy.deepcopy(child(tpl_apply[2], 'modifiers')[2][1])                 # a modifier entry (weapon form)
    # ---- the upgrade itself
    up = copy.deepcopy(tpl_t); bag = child(up, 'upgrade_bag')[2]
    child(up, 'pbgid')[2] = new_id()
    ui = child(bag, 'ui_info')[2]
    for k in ('screen_name', 'help_text', 'extra_text'):
        e = child(ui, k); e[1] = 3; e[2] = '$' + G + str(RADIO['loc_ids'][k])
    child(ui, 'icon_name')[2] = 'Icons_commander_cmdr_soviet_radio_intercept'
    child(ui, 'hotkey_name')[2] = 'R'
    act = copy.deepcopy(tpl_apply); child(act[2], 0x3251a3ee)[2] = new_id()
    child(act[2], 'permanent')[2] = True; child(act[2], 'duration')[2] = 0.0
    child(act[2], 'modifiers')[2] = [
        modifier(tpl_mod, 'modifiers\\enable_weapon_modifier.lua', 1.0, 'enable', hpname, 'apply_to_weapon'),
        modifier(tpl_mod, 'modifiers\\auto_target_enable_weapon_modifier.lua', -1.0, 'enable', 'hardpoint_01', 'apply_to_weapon'),
        modifier(tpl_mod, 'modifiers\\sight_radius_modifier.lua', RADIO['sight_multiplier'], 'multiplication', '', 'apply_to_entity'),
    ]
    child(bag, 'actions')[2] = [act]
    cost = node(bag, 'time_cost', 'cost')[2]
    for k in ('popcap', 'action', 'fuel', 'command', 'manpower'): child(cost, k)[2] = 0.0
    child(cost, 'munition')[2] = RADIO['munition_cost']
    node(bag, 'time_cost', 'time_seconds')[2] = RADIO['build_time']
    child(bag, 'requirements')[2] = []            # buyable anywhere, once per squad
    child(bag, 'local_max_limit')[2] = 1.0
    for k in ('code_1', 'code_2', 'code_3'):
        e = node(bag, 'speech_code_3', k)
        if e: e[2] = ''
    added['upgrade/%s.rgd' % RADIO['upgrade_name']] = (tpl_d, up)
    log['radio'].append(['upgrade/%s.rgd' % RADIO['upgrade_name'], 'new upgrade', f"{RADIO['munition_cost']} munitions, {RADIO['build_time']} s, once per squad"])

    # ---- per gun: radio weapon copy + hardpoint_08 (disabled until the upgrade)
    eligible_ebps = {}
    for name, (kind, src_hp) in SUPPORT_GUNS.items():
        rel = rel_of(name, 'ebps')
        if not rel: log['radio_skipped'].append([name, 'ebps not in mod']); continue
        t = load(rel)
        hps = node(t, 'combat_ext', 'hardpoints')[2]
        if len(hps) >= hp: log['radio_skipped'].append([name, 'already %d hardpoints' % len(hps)]); continue
        wname = node(hps[src_hp - 1][2], 'weapon_table')[2][0][2]
        wname = child(wname, 'weapon')[2].split(':')[-1]
        wrel = rel_of(wname, 'weapon')
        if not wrel: log['radio_skipped'].append([name, 'weapon %s not in mod' % wname]); continue
        # radio weapon = exact copy of the gun's own weapon (same projectile, damage, range, scatter) + target preference
        radio_w = wname.replace('_mp', '') + '_vplus_radio_mp'
        wrel_new = wrel.rsplit('/', 1)[0] + '/' + radio_w + '.rgd'
        if wrel_new not in added:
            wd, _ = rgd.load(os.path.join(ATTR, wrel)); wt = copy.deepcopy(load(wrel))   # after range scaling
            child(wt, 'pbgid')[2] = new_id()
            wb = child(wt, 'weapon_bag')[2]
            pri = child(wb, 'priority')[2]
            for k in ('threat', 'current_target', 'penetration'):
                e = child(pri, k);
                if e: e[2] = RADIO['priority'][k]
            for k, v in RADIO['priority']['distance'].items():
                e = node(pri, 'distance', k)
                if e: e[2] = v
            at = node(wb, 'behaviour', 'enable_auto_target_search')
            if at: at[2] = True
            if kind == 'howitzer':
                for k in ('min', 'max'):
                    e = node(wb, 'reload', 'duration', k)
                    if e: e[2] = RADIO['howitzer_reload_seconds']
                cb = node(wb, 'burst', 'can_burst')
                if cb: cb[2] = False
            nm = child(wb, 'name')
            if nm and nm[1] == 3: nm[2] = (nm[2] + ' (Radio Man)')[:120]
            added[wrel_new] = (wd, wt)
            log['radio'].append([wrel_new, 'new weapon', 'copy of %s; priority threat=%g current_target=%g distance=1/1/1%s' % (
                wrel, RADIO['priority']['threat'], RADIO['priority']['current_target'],
                '; reload %gs, no burst' % RADIO['howitzer_reload_seconds'] if kind == 'howitzer' else '; same reload as the gun')])
        # hardpoints: pad with empty slots up to 7, radio weapon on 8
        pad_src = hps[1] if len(hps) > 1 else hps[0]
        while len(hps) < hp - 1:
            e = copy.deepcopy(pad_src); child(node(e[2], 'weapon_table')[2][0][2], 'weapon')[2] = ''
            child(e[2], 'receives_attack_commands')[2] = False; hps.append(e)
        e = copy.deepcopy(hps[src_hp - 1]); child(node(e[2], 'weapon_table')[2][0][2], 'weapon')[2] = G + radio_w
        child(e[2], 'receives_attack_commands')[2] = False; hps.append(e)
        # start disabled: entity spawn action  enable_weapon_modifier -1 on hardpoint_08
        aae = node(t, 'action_apply_ext', 'actions')
        a = copy.deepcopy(tpl_apply); child(a[2], 0x3251a3ee)[2] = new_id()
        child(a[2], 'permanent')[2] = True; child(a[2], 'duration')[2] = 0.0
        child(a[2], 'modifiers')[2] = [modifier(tpl_mod, 'modifiers\\enable_weapon_modifier.lua', -1.0, 'enable', hpname, 'apply_to_weapon')]
        aae[2].append(a)
        eligible_ebps[name] = kind
        log['radio'].append([rel, 'gun entity', '%s: %s = %s (disabled until Radio Man), source hardpoint_%02d %s' % (kind, hpname, radio_w, src_hp, wname)])
    # ---- squads that crew those guns get the upgrade button
    for f in sorted(glob.glob(os.path.join(ATTR, 'sbps', '**', '*.rgd'), recursive=True)):
        rel = os.path.relpath(f, ATTR).replace('\\', '/'); d0, t0 = rgd.load(f)
        types = []
        walk(t0, lambda p, e: types.append(e[2]) if p[-1] == 'type' and len(p) > 2 and p[-3] == 'unit_list' and e[1] == 3 else None)
        guns = [x.split(':')[-1] for x in types if x.split(':')[-1] in eligible_ebps]
        if not guns: continue
        t = load(rel); ups = node(t, 'squad_upgrade_ext', 'upgrades')
        if ups is None: log['radio_skipped'].append([rel, 'no squad_upgrade_ext']); continue
        entry = [H('upgrade'), 3, G + RADIO['upgrade_name']]
        if not any(e[2] == entry[2] for e in ups[2]): ups[2].append(entry)
        log['radio'].append([rel, 'squad', 'Radio Man upgrade button added (%s)' % guns[0]])

def locale():
    p = os.path.join(SRC, 'locale', 'english', 'english.ucs')
    txt = open(p, 'rb').read().decode('utf-16')
    lines = txt.rstrip('\r\n').split('\r\n')
    have = {l.split('\t', 1)[0] for l in lines}
    for k, i in RADIO['loc_ids'].items():
        if str(i) in have: raise SystemExit('locale id %d already used' % i)
        lines.append('%d\t%s' % (i, RADIO['loc'][k]))
    out = os.path.join(MOD, 'locale', 'english', 'english.ucs'); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(('\r\n'.join(lines) + '\r\n').encode('utf-16'))   # utf-16 with BOM, CRLF like the original

# ======================================================= main
def main():
    import shutil
    for f in glob.glob(os.path.join(ATTR, '**', '*.rgd'), recursive=True):
        try: _collect(rgd.load(f)[1])
        except Exception: pass
    ref = json.load(open(os.path.join(REP, 'vanilla_gunfire_reference.json')))
    gunfire(ref); ranges(); barrage_abilities(); additive_range_modifiers(); no_forced_retreat(); ai(); perf(); radio_man()
    if os.path.isdir(MOD): shutil.rmtree(MOD)
    n_mod = n_add = 0
    for rel, (orig, tab) in changed.items():
        new = rgd.save(orig, tab)
        if new != orig:
            out = os.path.join(MOD, 'attrib', 'attrib', rel); os.makedirs(os.path.dirname(out), exist_ok=True)
            open(out, 'wb').write(new); n_mod += 1
    for rel, (tpl, tab) in added.items():
        out = os.path.join(MOD, 'attrib', 'attrib', rel); os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(rgd.save(tpl, tab)); n_add += 1
    locale()
    json.dump(sorted(added), open(os.path.join(REP, 'added_files.json'), 'w'), indent=1)
    hdr = {'gunfire': ['file', 'class', 'fx_tracer_name', 'old_projectile', 'new_projectile', 'old_tracer_speed', 'new_tracer_speed', 'old_munition', 'new_munition'],
           'gunfire_new_blueprints': ['file', 'source', 'change'],
           'ranges': ['file', 'name', 'min(kept)', 'old_max', 'new_max', 'old_near', 'new_near', 'old_mid', 'new_mid', 'old_far', 'new_far'],
           'ability_ranges': ['file', 'old', 'new'], 'ai': ['file', 'field', 'old', 'new'], 'perf': ['file', 'field', 'old', 'new', 'why'],
           'radio': ['file', 'what', 'detail'], 'radio_skipped': ['item', 'reason'], 'retreat': ['file', 'removed', 'what']}
    for k, h in hdr.items():
        with open(os.path.join(REP, k + '_changes.csv'), 'w', newline='') as fo:
            w = csv.writer(fo); w.writerow(h); w.writerows(log[k])
    print('modified files:', n_mod, ' new files:', n_add, ' + locale')
    for k in hdr: print('  %-24s %d' % (k, len(log[k])))

if __name__ == '__main__':
    main()
