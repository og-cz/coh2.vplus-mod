"""SGA v7 (CoH2) builder that can ADD files to existing folders.

Uses an existing archive as the template for drives/folders/flags, re-derives
every folder & drive file range, appends new names, recomputes CRC32 and SHA-1
block hashes. With no changes it reproduces the template byte-for-byte.
"""
import struct, zlib, hashlib, time
B = 0x98

def build(tpl_path, out_path, replace=lambda path, i: None, additions=None,
          name_map=lambda b: b, archive_name=None, mtime=None):
    """additions: {'attrib/attrib/upgrade/x.rgd': bytes}  (folder must already exist)"""
    additions = additions or {}
    d = open(tpl_path, 'rb').read()
    toc_size, data_pos, unk = struct.unpack_from('<3I', d, 0x8C)
    dp, dc, fp, fc, ip, ic, np_, nc, hp, blk = struct.unpack_from('<10I', d, B)
    names = bytearray(d[B + np_:B + hp])
    nm = lambda o: bytes(names[o:names.index(b'\0', o)]).decode('latin1')
    drives = [list(struct.unpack_from('<5I', d, B + dp + i * 148 + 128)) for i in range(dc)]
    drive_raw = [d[B + dp + i * 148:B + dp + i * 148 + 128] for i in range(dc)]
    folders = [list(struct.unpack_from('<5I', d, B + fp + i * 20)) for i in range(fc)]
    files = [list(struct.unpack_from('<5I2B2I', d, B + ip + i * 30)) for i in range(ic)]

    # map folder index -> archive path prefix ('attrib/attrib/upgrade')
    fpath = {}
    for di, (f0, f1, _, _, root) in enumerate(drives):
        dn = drive_raw[di][64:128].rstrip(b'\0').decode()
        for fi in range(f0, f1):
            n = nm(folders[fi][0]).replace('\\', '/')
            fpath[fi] = dn + ('/' + n if n else '')
    path_to_folder = {v: k for k, v in fpath.items()}

    # entries per folder: (name, kind, payload)  kind 'old' -> original index, 'new' -> bytes
    per = {fi: [] for fi in range(fc)}
    for fi, f in enumerate(folders):
        for k in range(f[3], f[4]):
            per[fi].append((nm(files[k][0]), 'old', k))
    for p, data in additions.items():
        folder, fname = p.rsplit('/', 1)
        if folder not in path_to_folder: raise ValueError('folder does not exist in template: ' + folder)
        fi = path_to_folder[folder]
        if any(e[0] == fname for e in per[fi]): raise ValueError('already exists: ' + p)
        per[fi].append((fname, 'new', data))
        per[fi].sort(key=lambda e: e[0])           # template keeps files sorted
    # file order: by original file_start of each folder (stable), empty folders keep place
    order = sorted(range(fc), key=lambda fi: (folders[fi][3], fi))
    new_files = []; blobs = []; idx = 0
    for fi in order:
        s = idx
        for fname, kind, pay in per[fi]:
            if kind == 'old':
                f = files[pay][:]
                path = fpath[fi] + '/' + fname
                new = replace(path, pay)
                o = files[pay]; raw = d[data_pos + o[1]:data_pos + o[1] + o[2]]
                if new is None: blob = raw
                else:
                    blob = zlib.compress(new, 9) if f[6] != 0 else new
                    f[2] = len(blob); f[3] = len(new); f[7] = zlib.crc32(blob) & 0xffffffff
            else:
                name_off = len(names); names += fname.encode('latin1') + b'\0'
                blob = zlib.compress(pay, 9)
                f = [name_off, 0, len(blob), len(pay), int(mtime or time.time()), 4, 2, zlib.crc32(blob) & 0xffffffff, 0]
            new_files.append(f); blobs.append((f, blob, files[pay][1] if kind == 'old' else 1 << 62)); idx += 1
        if per[fi] or folders[fi][4] > folders[fi][3]:
            folders[fi][3], folders[fi][4] = s, idx
    for di, dv in enumerate(drives):
        fis = range(dv[0], dv[1])
        nonempty = [fi for fi in fis if folders[fi][4] > folders[fi][3]]
        if nonempty:
            dv[2] = min(folders[fi][3] for fi in nonempty); dv[3] = max(folders[fi][4] for fi in nonempty)
    names = bytearray(name_map(bytes(names)))
    # hash block (entry order)
    hb = bytearray()
    for f, blob, _ in blobs:
        if f[5] == 4:
            f[8] = len(hb)
            for j in range(max(1, (len(blob) + blk - 1) // blk)): hb += hashlib.sha1(blob[j * blk:(j + 1) * blk]).digest()
        else: f[8] = 0
    # data layout: original files keep original relative order, new files appended
    lay = sorted(range(len(blobs)), key=lambda i: (blobs[i][2], i)); pos = 0
    for i in lay: blobs[i][0][1] = pos; pos += len(blobs[i][1])
    nfiles = len(new_files)
    # TOC: header(40) drives folders files names hashes  (same section order as template)
    toc = bytearray(40)
    dp2 = len(toc);
    for i in range(dc): toc += drive_raw[i] + struct.pack('<5I', *drives[i])
    fp2 = len(toc)
    for f in folders: toc += struct.pack('<5I', *f)
    ip2 = len(toc)
    for f in new_files: toc += struct.pack('<5I2B2I', *f)
    np2 = len(toc); toc += names
    hp2 = len(toc); toc += hb
    struct.pack_into('<10I', toc, 0, dp2, dc, fp2, fc, ip2, nfiles, np2, nc + len(additions), hp2, blk)
    head = bytearray(d[:B])
    if archive_name: head[12:140] = archive_name.encode('utf-16-le').ljust(128, b'\0')
    struct.pack_into('<3I', head, 0x8C, len(toc), B + len(toc) + 256, unk)
    with open(out_path, 'wb') as fo:
        fo.write(head); fo.write(toc); fo.write(d[data_pos - 256:data_pos])
        for i in lay: fo.write(blobs[i][1])
        end = max(files[k][1] + files[k][2] for k in range(ic))
        fo.write(d[data_pos + end:])
