import pefile,sys,capstone
pe=pefile.PE(sys.argv[1]); base=pe.OPTIONAL_HEADER.ImageBase
img=pe.get_memory_mapped_image()
imp={i.address:(e.dll.decode()+'!'+(i.name.decode() if i.name else str(i.ordinal))) for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports}
exp={base+s.address:s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
byname={s.name.decode():base+s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def name(a):
    if a in imp: return imp[a]
    if a in exp: return exp[a]
    return None
def dis(addr,maxn=1500):
    out=[]; n=0; hi=addr
    code=img[addr-base:addr-base+0x2000]
    for ins in md.disasm(code,addr):
        cmt=''
        for op in ins.operands:
            if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP:
                t=ins.address+ins.size+op.mem.disp; nm=name(t)
                cmt=f' ; [{hex(t)}] {nm or ""}'
                if not nm:
                    try:
                        s=pe.get_string_at_rva(t-base,64)
                        if s and len(s)>3 and all(32<=c<127 for c in s): cmt+=f' "{s.decode()}"'
                    except Exception: pass
            if op.type==capstone.x86.X86_OP_IMM and ins.mnemonic in('call','jmp') and name(op.imm): cmt=' ; '+name(op.imm)
        out.append(f'{ins.address:x}: {ins.mnemonic} {ins.op_str}{cmt}')
        n+=1
        if ins.mnemonic.startswith('j') and ins.operands and ins.operands[0].type==capstone.x86.X86_OP_IMM:
            t=ins.operands[0].imm
            if addr<=t<addr+0x2000 and not name(t): hi=max(hi,t)
        if ins.mnemonic in('ret','int3','jmp') and ins.address>=hi or n>=maxn: break
    return out
for f in sys.argv[2:]:
    a=byname.get(f) or int(f,16)
    print(f'===== {f} @ {a:x}'); print('\n'.join(dis(a)))
