import sys;import rgd
rgd.load_dict()
def flat(tab,pre=''):
    out={}
    for hs,t,v in tab:
        k=pre+'/'+rgd.name(hs)
        if t in(100,101):
            sub=flat(v,k)
            # list entries have same key; disambiguate
            out.update(sub)
        else: out[k]=v
    return out
def flat_idx(tab,pre=''):
    out={};cnt={}
    for hs,t,v in tab:
        n=rgd.name(hs);cnt[n]=cnt.get(n,0)+1
        k=pre+'/'+n+('#%d'%cnt[n] if cnt[n]>1 else '')
        if t in(100,101): out.update(flat_idx(v,k))
        else: out[k]=v
    return out
