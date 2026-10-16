import sys; sys.stdout.reconfigure(encoding="utf-8")
import dnfile,sys,re
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.clr.token import Token,StringToken,InvalidToken
from dncil.cil.error import MethodBodyFormatError
pe=dnfile.dnPE(sys.argv[1]); md=pe.net.mdtables
class R(CilMethodBodyReaderBase):
    def __init__(s,rva): s.off=pe.get_offset_from_rva(rva)
    def read(s,n): d=pe.get_data(pe.get_rva_from_offset(s.off),n); s.off+=n; return d
    def tell(s): return s.off
    def seek(s,o): s.off=o; return o
def tname(tbl,idx):
    try:
        r=getattr(md,tbl).rows[idx-1]
        if tbl=='MethodDef': return meth_owner.get(idx,'?')+'::'+r.Name.value
        if tbl=='Field': return fld_owner.get(idx,'?')+'::'+r.Name.value
        if tbl=='MemberRef':
            c=r.Class; cn=''
            try: cn=c.row.TypeName.value
            except Exception: pass
            return cn+'::'+r.Name.value
        if tbl in('TypeRef','TypeDef'): return r.TypeName.value
    except Exception as e: return f'{tbl}#{idx}'
    return f'{tbl}#{idx}'
meth_owner={}; fld_owner={}
for td in md.TypeDef.rows:
    full=(td.TypeNamespace.value+'.' if td.TypeNamespace.value else '')+td.TypeName.value
    for m in td.MethodList: meth_owner[m.row_index]=full
    for f in td.FieldList: fld_owner[f.row_index]=full
TB={0x06:'MethodDef',0x0a:'MemberRef',0x04:'Field',0x01:'TypeRef',0x02:'TypeDef',0x2b:'MethodSpec',0x1b:'TypeSpec'}
pat=re.compile(sys.argv[2])
for i,m in enumerate(md.MethodDef.rows,1):
    full=meth_owner.get(i,'?')+'::'+m.Name.value
    if not pat.search(full) or not m.Rva: continue
    print('=====',full)
    try: body=CilMethodBody(R(m.Rva))
    except Exception as e: print('  err',e); continue
    for ins in body.instructions:
        op=ins.operand
        if isinstance(op,StringToken):
            s=pe.net.user_strings.get(op.rid); op='"'+(s.value if s else '?')+'"'
        elif isinstance(op,Token): op=tname(TB.get(op.table,'?'),op.rid)
        print(f'  {ins.offset:04x} {ins.opcode.name} {op if op is not None else ""}')
