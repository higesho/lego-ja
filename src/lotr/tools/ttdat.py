import struct,sys
class Dat:
    def __init__(s,path):
        s.path=path; f=open(path,'rb'); s.f=f
        off,sz=struct.unpack('<II',f.read(8))
        if off&0x80000000: off=((off^0xffffffff)<<8)+0x100
        f.seek(off); info=f.read(sz); s.info=info
        ver,n=struct.unpack_from('<iI',info,0)
        s.ents=[struct.unpack_from('<IIII',info,8+i*16) for i in range(n)]
        p=8+n*16
        cnt=struct.unpack_from('<I',info,p)[0]
        s.recs=[struct.unpack_from('<hhII',info,p+4+i*12) for i in range(cnt)]
        pool=p+4+cnt*12+4
        s.names=[]
        for r in s.recs:
            e=info.index(b'\0',pool+r[2]); s.names.append(info[pool+r[2]:e].decode('latin1'))
        s.files={}  # fileindex -> recidx
        for i,r in enumerate(s.recs):
            if r[0]<=0 and i>0: s.files[-r[0]]=i
    def entry(s,idx):
        o,z,u,fl=s.ents[idx]; return (o<<8),z,u,fl
    def raw(s,idx):
        o,z,u,fl=s.entry(idx); s.f.seek(o); return s.f.read(z)
