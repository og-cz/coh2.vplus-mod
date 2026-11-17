"""
Pack Vanilla+ into a CoH2 tuning-pack archive (SGA v7).

Template = the original Kriegspiel V5 archive (same drives/folders). Files from
modified/ replace their originals; files in modified/ that the template lacks are
added. Vanilla+ gets its own GUID so it never collides with Kriegspiel V5.

Run:  python tools/pack.py        ->  output/VanillaPlus.sga
"""
import os, sys, struct, zlib, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sga7b, sga7w

OLD_GUID = '3f698c4a5048428d9fdb675aa488f596'
ID = json.load(open(os.path.join(HERE, 'vplus_identity.json')))
NEW_GUID = ID['guid']; assert len(NEW_GUID) == len(OLD_GUID)
TPL = os.path.join(ROOT, 'original_backup', 'Kriegspiel_V5_2162940169.sga')
MOD = os.path.join(ROOT, 'modified')
OUT = os.path.join(ROOT, 'output', 'VanillaPlus.sga')

DESCRIPTION = (
    "Vanilla+ v%s - built on Kriegspiel V5 - Realism Overhaul by RebelSoldier.\\n\\n"
    "Keeps Kriegspiel's gameplay and damage model (physical bullets, criticals, morale, AI), and adds:\\n"
    "- Cleaner, vanilla-style gunfire: infantry rifles/SMGs fire subtle rounds, machine guns keep heavy tracers\\n"
    "- Vanilla impact effects instead of the phosphorus/custom ones\\n"
    "- Weapon ranges -20%% (less extreme engagement distances)\\n"
    "- Aggressive AI that keeps attacking fortified lines, flanks and uses smoke/artillery\\n"
    "- Radio Man: optional 60 munition upgrade for mortars, infantry guns and howitzers (smart target priority)\\n"
    "- Performance pass for big battles (no terrain crater per bullet / shrapnel fragment)\\n\\n"
    "Credits: Kriegspiel V5 - Realism Overhaul (c) RebelSoldier - https://steamcommunity.com/sharedfiles/filedetails/?id=2162940169\\n"
    "Company of Heroes 2 (c) Relic Entertainment / SEGA."
) % ID['version']

def guid_swap(b):
    return (b.replace(OLD_GUID.encode(), NEW_GUID.encode())
             .replace(OLD_GUID.encode('utf-16-le'), NEW_GUID.encode('utf-16-le')))
def fix_rgd_crc(b):
    if b[:12] == b'Relic Chunky' and b[36:44] == b'DATAAEGD':
        sz = struct.unpack_from('<I', b, 68)[0]; b = bytearray(b)
        struct.pack_into('<I', b, 64, zlib.crc32(bytes(b[72:72 + sz])) & 0xffffffff); b = bytes(b)
    return b
def info_file(b):
    t = b.decode('latin1')
    s = t.index('name = "') + 8; e = t.index('"', s); t = t[:s] + ID['name'] + t[e:]
    s = t.index('description = "') + 15; e = t.index('"\r\ndependencies'); t = t[:s] + DESCRIPTION + t[e:]
    return t.encode('latin1')

A = sga7w.read(TPL); tpl_paths = set(A['paths'])
def replace(path, i):
    local = os.path.join(MOD, *path.split('/'))
    data = open(local, 'rb').read() if os.path.exists(local) else sga7w.content(A, i)
    new = guid_swap(data)
    if path.startswith('info/') and path.endswith('.info'): new = info_file(new)
    if new == data and not os.path.exists(local): return None
    return fix_rgd_crc(new)
additions = {}
for r, ds, fs in os.walk(MOD):
    for f in fs:
        p = os.path.relpath(os.path.join(r, f), MOD).replace('\\', '/')
        if p not in tpl_paths: additions[p] = fix_rgd_crc(guid_swap(open(os.path.join(r, f), 'rb').read()))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
sga7b.build(TPL, OUT, replace=replace, additions=additions, name_map=guid_swap, archive_name=NEW_GUID)
print('written', OUT, os.path.getsize(OUT), 'bytes;', len(additions), 'new files')
