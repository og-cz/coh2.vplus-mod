"""SGA v7 (CoH2) archive rewriter.
Rebuilds an archive using an existing archive's TOC as the template.
replace(path)->None (keep original bytes) or new decompressed bytes."""
import struct,zlib,hashlib
B=0x98
def read(path):
    d=open(path,'rb').read()
    toc_size,data_pos,unk=struct.unpack_from('<3I',d,0x8C)
    hdr=struct.unpack_from('<10I',d,B)
    dp,dc,fp,fc,ip,ic,np_,nc,hp,blk=hdr
    files=[list(struct.unpack_from('<5I2B2I',d,B+ip+i*30)) for i in range(ic)]
    folders=[struct.unpack_from('<5I',d,B+fp+i*20) for i in range(fc)]
    names=d[B+np_:B+hp]
    nm=lambda o: names[o:names.index(b'\0',o)].decode('latin1')
    paths=[None]*ic
    drives=[]
    for i in range(dc):
        o=B+dp+i*148; drives.append((d[o:o+64],d[o+64:o+128],struct.unpack_from('<5I',d,o+128)))
    for alias,name,(f0,f1,_,_,_) in drives:
        dn=name.rstrip(b'\0').decode()
        for fi in range(f0,f1):
            fn,sf,ef,s,e=folders[fi]
            for k in range(s,e): paths[k]=dn+'/'+(nm(fn)+'/' if nm(fn) else '').replace('\\','/')+nm(files[k][0])
    return dict(d=d,toc_size=toc_size,data_pos=data_pos,unk=unk,hdr=hdr,files=files,paths=paths,names=names)
def raw_of(a,i):
    no,off,cs,ds,mod,ver,st,h1,h2=a['files'][i]; p=a['data_pos']+off
    return a['d'][p:p+cs]
def content(a,i):
    r=raw_of(a,i); st=a['files'][i][6]
    return zlib.decompress(r) if st!=0 else r
def write(a,out,replace=lambda p,i:None,name_map=lambda b:b,archive_name=None):
    d=a['d'];dp,dc,fp,fc,ip,ic,np_,nc,hp,blk=a['hdr']
    # order data by original offset to reproduce layout
    order=sorted(range(ic),key=lambda i:a['files'][i][1])
    blobs={};newfiles=[f[:] for f in a['files']]
    for i in order:
        new=replace(a['paths'][i],i)
        if new is None: blobs[i]=raw_of(a,i)
        else:
            st=newfiles[i][6]
            comp=zlib.compress(new,9) if st!=0 else new
            blobs[i]=comp; newfiles[i][2]=len(comp); newfiles[i][3]=len(new); newfiles[i][7]=zlib.crc32(comp)&0xffffffff
    # hash block in entry order (original assigns sequentially)
    hb=bytearray()
    for i in range(ic):
        f=newfiles[i]
        if f[5]==4:
            f[8]=len(hb); c=blobs[i]
            for j in range(max(1,(len(c)+blk-1)//blk)): hb+=hashlib.sha1(c[j*blk:(j+1)*blk]).digest()
        else: f[8]=0
    toc=bytearray(d[B:B+hp])
    toc[np_:hp]=name_map(bytes(toc[np_:hp]))
    for i,f in enumerate(newfiles): struct.pack_into('<5I2B2I',toc,ip+i*30,*f)
    toc+=hb
    toc_size=len(toc); data_pos=B+toc_size+256
    pos=0
    for i in order:
        newfiles[i][1]=pos; pos+=len(blobs[i])
    for i,f in enumerate(newfiles): struct.pack_into('<5I2B2I',toc,ip+i*30,*f)
    head=bytearray(d[:B])
    if archive_name: head[12:140]=archive_name.encode('utf-16-le').ljust(128,b'\0')
    struct.pack_into('<3I',head,0x8C,toc_size,data_pos,a['unk'])
    with open(out,'wb') as fo:
        fo.write(head);fo.write(toc);fo.write(d[a['data_pos']-256:a['data_pos']])
        for i in order: fo.write(blobs[i])
        fo.write(d[a['data_pos']+max(a['files'][i][1]+a['files'][i][2] for i in range(ic)):]) # trailing bytes
