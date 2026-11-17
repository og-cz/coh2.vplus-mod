"""Compare every typed table ($REF) in modified/ against the key sets the game itself uses for that $REF
(collected from vanilla + original Kriegspiel). Extra keys, missing keys or wrong value types are reported."""
import sys, os, glob, collections, pickle
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import rgd; rgd.load_dict()
SRC = [sys.argv[1] if len(sys.argv) > 1 else '/home/claude/vanilla/out/attribdata/attrib', os.path.join(ROOT, 'extracted_assets', 'attrib', 'attrib')]
cache = os.path.join(ROOT, 'reports', '.schema_cache.pkl')
def walk(tab, acc):
    ref = [x for x in tab if x[0] == rgd.h('$REF')]
    if ref and isinstance(ref[0][2], str):
        acc[ref[0][2].lower()].append({x[0]: x[1] for x in tab})
    for h, t, v in tab:
        if t in (100, 101): walk(v, acc)
if os.path.exists(cache): known = pickle.load(open(cache, 'rb'))
else:
    known = collections.defaultdict(list)
    for root in SRC:
        for f in glob.glob(os.path.join(root, '**', '*.rgd'), recursive=True):
            try: walk(rgd.load(f)[1], known)
            except Exception: pass
    known = {k: v for k, v in known.items()}
    pickle.dump(known, open(cache, 'wb'))
keysets = {k: [frozenset(d) for d in v] for k, v in known.items()}
types = {k: collections.defaultdict(set) for k in known}
for k, v in known.items():
    for d in v:
        for kk, t in d.items(): types[k][kk].add(t)
problems = []
for f in sorted(glob.glob(os.path.join(ROOT, 'modified', '**', '*.rgd'), recursive=True)):
    acc = collections.defaultdict(list); walk(rgd.load(f)[1], acc)
    for ref, tabs in acc.items():
        if ref not in keysets: problems.append((f, ref, 'unknown $REF')); continue
        allk = set().union(*keysets[ref])
        for d in tabs:
            ks = frozenset(d)
            extra = ks - allk
            if extra: problems.append((f, ref, 'extra keys ' + ','.join(rgd.name(x) for x in extra)))
            if ks not in keysets[ref] and not extra:
                # missing keys vs every known shape
                best = min(keysets[ref], key=lambda s: len(s ^ ks))
                problems.append((f, ref, 'shape differs: missing ' + ','.join(rgd.name(x) for x in best - ks)))
            for kk, t in d.items():
                if kk in types[ref] and t not in types[ref][kk]:
                    problems.append((f, ref, 'type of %s = %d, game uses %s' % (rgd.name(kk), t, sorted(types[ref][kk]))))
for p in problems: print(os.path.relpath(p[0], ROOT), '|', p[1], '|', p[2])
print(len(problems), 'problem(s)')
