import re
LIB="/usr/share/kicad/symbols"
def block(text, start):
    d=0
    for i in range(start, len(text)):
        c=text[i]
        if c=='(': d+=1
        elif c==')':
            d-=1
            if d==0: return text[start:i+1]
    raise ValueError
def get_symbol(libsym):
    lib,name=libsym.split(':')
    t=open(f"{LIB}/{lib}.kicad_sym").read()
    i=t.find(f'(symbol "{name}"')
    b=block(t,i)
    return b
pin_re=re.compile(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\)(.*?)\(name "([^"]*)".*?\(number "([^"]*)"', re.S)
def pins(libsym):
    b=get_symbol(libsym)
    out=[]
    for m in pin_re.finditer(b):
        typ,style,x,y,a,L,rest,name,num=m.groups()
        out.append(dict(type=typ,x=float(x),y=float(y),a=float(a),len=float(L),name=name,num=num,hidden='hide' in rest))
    return out
