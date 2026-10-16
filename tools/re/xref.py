import pefile,sys,capstone,bisect
pe=pefile.PE(sys.argv[1]); base=pe.OPTIONAL_HEADER.ImageBase
imp={i.address:(i.name.decode() if i.name else '') for e in pe.DIRECTORY_ENTRY_IMPORT for i in e.imports}
want=[a for a,n in imp.items() if n in sys.argv[2].split(',')]
want+= [int(x,16) for x in sys.argv[3:]]
text=[s for s in pe.sections if s.Name.startswith(b'.text')][0]
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
va=base+text.VirtualAddress; code=text.get_data()
# function starts from .pdata
starts=sorted(base+f.struct.BeginAddress for f in pe.DIRECTORY_ENTRY_EXCEPTION)
for ins in md.disasm(code,va):
    for op in ins.operands:
        t=None
        if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP: t=ins.address+ins.size+op.mem.disp
        elif op.type==capstone.x86.X86_OP_IMM: t=op.imm
        if t in want:
            f=starts[bisect.bisect_right(starts,ins.address)-1]
            print(f'{ins.address:x} in func {f:x}: {ins.mnemonic} {ins.op_str} -> {imp.get(t,hex(t))}')
