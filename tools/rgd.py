import struct,zlib,os
_D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'dict')+os.sep
def _mix(a,b,c):
    M=0xffffffff
    a=(a-b-c)&M;a^=c>>13
    b=(b-c-a)&M;b^=(a<<8)&M
    c=(c-a-b)&M;c^=b>>13
    a=(a-b-c)&M;a^=c>>12
    b=(b-c-a)&M;b^=(a<<16)&M
    c=(c-a-b)&M;c^=b>>5
    a=(a-b-c)&M;a^=c>>3
    b=(b-c-a)&M;b^=(a<<10)&M
    c=(c-a-b)&M;c^=b>>15
    return a,b,c
def h(s,init=0):
    k=s.encode() if isinstance(s,str) else s
    n=len(k);a=b=0x9e3779b9;c=init;i=0
    while n-i>=12:
        a=(a+struct.unpack_from('<I',k,i)[0])&0xffffffff
        b=(b+struct.unpack_from('<I',k,i+4)[0])&0xffffffff
        c=(c+struct.unpack_from('<I',k,i+8)[0])&0xffffffff
        a,b,c=_mix(a,b,c);i+=12
    c=(c+n)&0xffffffff;r=k[i:]
    for j,x in enumerate(r):
        if j<4:a=(a+(x<<(8*j)))&0xffffffff
        elif j<8:b=(b+(x<<(8*(j-4))))&0xffffffff
        else:c=(c+(x<<(8*(j-8+1))))&0xffffffff
    a,b,c=_mix(a,b,c);return c

DICT={}
def name(hs): return DICT.get(hs,'0x%08x'%hs)
def parse_table(b,o):
    n=struct.unpack_from('<I',b,o)[0]; ents=[struct.unpack_from('<3I',b,o+4+12*i) for i in range(n)]
    base=o+4+12*n; out=[]
    for hs,t,off in ents:
        p=base+off
        if t==0: v=struct.unpack_from('<f',b,p)[0]
        elif t==1: v=struct.unpack_from('<i',b,p)[0]
        elif t==2: v=bool(b[p])
        elif t==3:
            v=b[p:b.index(b'\0',p)].decode('latin1')
        elif t==4:
            e=p
            while b[e:e+2]!=b'\0\0': e+=2
            v=b[p:e].decode('utf-16-le')
        elif t in (100,101): v=parse_table(b,p)
        else: v=('?',t)
        out.append([hs,t,v])
    return out
def load(path):
    d=open(path,'rb').read(); sz=struct.unpack_from('<I',d,68)[0]
    return d,parse_table(d[72:72+sz],0)
def dump(tab,ind=0,f=None):
    for hs,t,v in tab:
        if t in(100,101): print(' '*ind+name(hs)+(' [list]' if t==101 else '')+':',file=f); dump(v,ind+2,f)
        else: print(' '*ind+name(hs)+' = '+repr(v),file=f)

def load_dict(paths=(''+_D+'hash_dict-old.txt',''+_D+'hash_dict.txt')):
  for path in paths:
    for line in open(path,encoding='latin1'):
        line=line.strip()
        if '=' in line and line.startswith('0x'):
            k,v=line.split('=',1)
            try: DICT[int(k,16)]=v
            except: pass
    for extra in ['ai_squad_bag','tactics','ai_ability_bag','weapon_bag','range','min','max','mid','distant','long','medium','short','near','far']:
        DICT.setdefault(h(extra),extra)

def ser_table(tab):
    ents=list(tab)
    n=len(ents); out=bytearray(); offs=[]
    for hs,t,v in ents:
        if t in (0,1,100,101):
            while len(out)%4: out+=b'\0'
        offs.append(len(out))
        if t==0: out+=struct.pack('<f',v)
        elif t==1: out+=struct.pack('<i',v)
        elif t==2: out+=bytes([1 if v else 0])
        elif t==3: out+=v.encode('latin1')+b'\0'
        elif t==4: out+=v.encode('utf-16-le')+b'\0\0'
        elif t in (100,101): out+=ser_table(v)
        else: raise ValueError(t)
    hdr=struct.pack('<I',n)+b''.join(struct.pack('<3I',hs,t,o) for (hs,t,v),o in zip(ents,offs))
    return hdr+bytes(out)
def save(orig_bytes,tab,path=None):
    body=ser_table(tab)
    head=bytearray(orig_bytes[:72])
    struct.pack_into('<I',head,64,zlib.crc32(body)&0xffffffff)
    struct.pack_into('<I',head,68,len(body))
    struct.pack_into('<I',head,48,len(body)+8)  # chunk size = crc+size+body
    data=bytes(head)+body
    if path: open(path,'wb').write(data)
    return data
