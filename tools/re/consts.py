import dnfile,sys
pe=dnfile.dnPE(sys.argv[1]); md=pe.net.mdtables
want=set(sys.argv[2:])
fields={}
for i,td in enumerate(md.TypeDef.rows):
    full=(td.TypeNamespace.value+'.' if td.TypeNamespace.value else '')+td.TypeName.value
    for f in td.FieldList: fields[f.row_index]=(full,f.row.Name.value)
for c in md.Constant.rows:
    p=c.Parent
    if p.table.name!='Field': continue
    t,n=fields.get(p.row_index,('?','?'))
    if t in want:
        v=int.from_bytes(c.Value.value,'little',signed=False)
        print(f'{t}.{n} = {v} ({v:#x})')
