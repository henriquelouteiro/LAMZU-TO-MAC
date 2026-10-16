import struct,sys,hashlib,os
exe,out=sys.argv[1],sys.argv[2]
b=open(exe,'rb').read()
pe=struct.unpack_from('<I',b,0x3c)[0]
nsec=struct.unpack_from('<H',b,pe+6)[0]; opt=struct.unpack_from('<H',b,pe+20)[0]
secs=[]
o=pe+24+opt
for i in range(nsec):
    name,vs,va,rs,ro=struct.unpack_from('<8sIIII',b,o+40*i)[:5]; secs.append((va,vs,ro))
def r2o(rva):
    for va,vs,ro in secs:
        if va<=rva<va+vs: return rva-va+ro
res=r2o(278168)
for name,off,ln in [('hidusb32.dll',2216051,114688),('hidusb.dll',4041315,145408)]:
    p=res+off; L=struct.unpack_from('<I',b,p)[0]; assert L==ln,(L,ln)
    d=b[p+4:p+4+L]; open(os.path.join(out,name),'wb').write(d)
    print(name,L,hashlib.sha256(d).hexdigest(),d[:2])
