import struct,sys,zlib,os
d=open(sys.argv[1],'rb').read(); out=sys.argv[2]
B=0x98
dp,dc,fp,fc,ip,ic,np_,nc=struct.unpack_from('<8I',d,B)
data_pos=struct.unpack_from('<I',d,0x90)[0]
nm=lambda o: d[B+np_+o:d.index(b'\0',B+np_+o)].decode('latin1')
folders=[struct.unpack_from('<5I',d,B+fp+i*20) for i in range(fc)]
files=[d[B+ip+i*30:B+ip+i*30+30] for i in range(ic)]
if sys.argv[3:]==['probe']:
    for f in folders[:5]: print(f,repr(nm(f[0])))
    for f in files[:5]: print(struct.unpack('<5I2B2I',f) if len(f)==30 else f)
    sys.exit()
drives=[]
for i in range(dc):
    o=B+dp+i*148; drives.append((d[o:o+64].rstrip(b'\0').decode(),d[o+64:o+128].rstrip(b'\0').decode(),struct.unpack_from('<5I',d,o+128)))
n=0;bad=0
for alias,name,(f0,f1,_,_,root) in drives:
  for fi in range(f0,f1):
    fn,sf,ef,s,e=folders[fi]; path=nm(fn).replace('\\','/')
    for k in range(s,e):
        no,off,cs,ds,mod,ver,st,h1,h2=struct.unpack('<5I2B2I',files[k])
        raw=d[data_pos+off:data_pos+off+cs]
        if st!=0:
            try: raw=zlib.decompress(raw)
            except Exception: bad+=1
        p=os.path.join(out,name,path,nm(no)); os.makedirs(os.path.dirname(p),exist_ok=True)
        open(p,'wb').write(raw); n+=1
print('files',n,'bad',bad,'drives',[(a,b) for a,b,_ in drives])
