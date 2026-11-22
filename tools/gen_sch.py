import math, uuid, re, json, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import kisym
from design import PARTS, POWER_NETS, WIRES, HIDE_VALUE
WIRED = {(a, b) for a, b, *_ in WIRES} | {(c, d) for _, _, c, d, _ in WIRES}
pinpos = {}
PROJ = sys.argv[1]; NAME = sys.argv[2]
U = lambda: str(uuid.uuid4())
NS = uuid.UUID("6f1c2a9e-5d3b-4e7a-9c1d-2b8e4f6a0c11")
ROOT = str(uuid.uuid5(NS, "root"))
f = lambda v: f"{v:.4f}".rstrip('0').rstrip('.')
out = []; libsyms = {}
STUB = 2.54

def transform(px, py, a, X, Y, rot, mir):
    if mir: px, a = -px, (180 - a) % 360
    t = math.radians(rot)
    rx = px*math.cos(t) - py*math.sin(t); ry = px*math.sin(t) + py*math.cos(t)
    return round(X + rx, 2), round(Y - ry, 2), (a + rot) % 360

def eff(hide=False, just=None, size=1.27):
    j = f" (justify {just})" if just else ""
    return f"(effects (font (size {size} {size})){j}{' hide' if hide else ''})"

def prop(name, val, x, y, hide=False, just=None, ang=0):
    return f'    (property "{name}" "{val}" (at {f(x)} {f(y)} {ang}) {eff(hide, just)})'

def need_lib(lib_id):
    if lib_id not in libsyms:
        b = kisym.get_symbol(lib_id)
        name = lib_id.split(':')[1]
        libsyms[lib_id] = b.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)

pwr_n = [0]; ref_inst = []
def symbol(lib_id, ref, value, fp, X, Y, rot=0, mir=False, pins=(), props=None, in_bom="yes", hide_ref=False, hide_val=False):
    need_lib(lib_id)
    uid = str(uuid.uuid5(NS, ref))
    mirror = " (mirror y)" if mir else ""
    s = [f'  (symbol (lib_id "{lib_id}") (at {f(X)} {f(Y)} {rot}){mirror} (unit 1)',
         f'    (in_bom {in_bom}) (on_board yes) (dnp no) (uuid {uid})']
    s += props or []
    s += [f'    (pin "{p}" (uuid {U()}))' for p in pins]
    s += [f'    (instances (project "{NAME}" (path "/{ROOT}" (reference "{ref}") (unit 1))))', '  )']
    out.append("\n".join(s)); return uid

def power(net, x, y):
    pwr_n[0] += 1
    ref = f"#PWR0{pwr_n[0]:02d}"
    up = net != "GND"
    props = [prop("Reference", ref, x, y + (3.81 if not up else 6.35), hide=True),
             prop("Value", net, x, y + (3.81 if not up else -3.81)),
             prop("Footprint", "", x, y, hide=True), prop("Datasheet", "", x, y, hide=True)]
    symbol(f"power:{net}", ref, net, "", x, y, 0, False, ["1"], props, in_bom="no")

def wire(x1, y1, x2, y2):
    out.append(f'  (wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) (stroke (width 0) (type default)) (uuid {U()}))')

def label(net, x, y, ang):
    just = "left" if ang in (0, 90) else "right"
    out.append(f'  (label "{net}" (at {f(x)} {f(y)} {ang}) (fields_autoplaced) {eff(just=just)} (uuid {U()}))')

uuids = {}
for ref, (lib_id, value, fp, (X, Y), rot, mir, pinnets) in PARTS.items():
    pins = kisym.pins(lib_id)
    ys = [transform(p['x'], p['y'], p['a'], X, Y, rot, mir)[1] for p in pins] or [Y]
    xs = [transform(p['x'], p['y'], p['a'], X, Y, rot, mir)[0] for p in pins] or [X]
    if ref.startswith("U"):
        top, bot = min(ys), max(ys)
        rp = (X + 3.81, top + 2.54 + (1.27 if ref == "U2" else 0)); vp = (X + 3.81, bot - 2.54)
        rj = vj = "left"
    elif ref.startswith("D") and rot in (0, 180):
        rp = (X, Y - 3.81); vp = (X, Y + 3.81); rj = vj = None
    elif ref.startswith("H"):
        rp = (X + 3.81, Y - 1.27); vp = (X + 3.81, Y + 1.27); rj = vj = "left"
    elif ref == "J1":
        rp = (X - 2.54, Y - 3.81); vp = (X - 2.54, Y + 6.35); rj = vj = None
    else:
        rp = (X + 3.81 if ref != "RV1" else X - 3.81, Y - 1.27); vp = (rp[0], Y + 1.27)
        rj = vj = "left" if ref != "RV1" else "right"
    fa = (360 - rot) % 360 if rot in (90, 270) else 0
    props = [prop("Reference", ref, *rp, just=rj, ang=fa), prop("Value", value, *vp, just=vj, hide=ref in HIDE_VALUE, ang=fa),
             prop("Footprint", fp, X, Y, hide=True), prop("Datasheet", "~", X, Y, hide=True)]
    uuids[ref] = symbol(lib_id, ref, value, fp, X, Y, rot, mir, [p['num'] for p in pins], props)
    for p in pins:
        if p['num'] not in pinnets: continue
        net = pinnets[p['num']]
        x, y, a = transform(p['x'], p['y'], p['a'], X, Y, rot, mir)
        pinpos[(ref, p['num'])] = (x, y)
        if (ref, p['num']) in WIRED: continue
        if net is None:
            out.append(f'  (no_connect (at {f(x)} {f(y)}) (uuid {U()}))'); continue
        d = (a + 180) % 360  # outward direction (math convention, y up)
        dx, dy = round(math.cos(math.radians(d))), -round(math.sin(math.radians(d)))
        L = 10.16 if (net in POWER_NETS and dy == 0 and net == "VCC") else STUB
        ex, ey = x + dx * L, y + dy * L
        wire(x, y, ex, ey)
        if net in POWER_NETS:
            if net == "GND" and dy < 0:      # pin facing up: put GND below via extra wire? keep symbol at end
                pass
            power(net, ex, ey)
        else:
            label(net, ex, ey, int(d))

for a, pa, b, pb, lab in WIRES:
    (x1, y1), (x2, y2) = pinpos[(a, pa)], pinpos[(b, pb)]
    assert x1 == x2 or y1 == y2, (a, b)
    wire(x1, y1, x2, y2)
    if lab: label(lab, (x1 + x2) / 2, (y1 + y2) / 2, 0)
# power flags
for net, (x, y) in {"VCC": (60.96, 33.02), "GND": (76.2, 58.42), "VIN": (35.56, 33.02)}.items():
    pwr_n[0] += 1; ref = f"#FLG0{pwr_n[0]:02d}"
    props = [prop("Reference", ref, x, y - 1.905, hide=True), prop("Value", "PWR_FLAG", x, y - 3.81),
             prop("Footprint", "", x, y, hide=True), prop("Datasheet", "~", x, y, hide=True)]
    symbol("power:PWR_FLAG", ref, "PWR_FLAG", "", x, y, 0, False, ["1"], props, in_bom="no")
    wire(x, y, x, y + 5.08)
    if net == "VIN": label("VIN", x, y + 5.08, 270)
    else: power(net, x, y + 5.08)

# block frames and notes
def rect(x1, y1, x2, y2, title):
    out.append(f'  (rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) (stroke (width 0.254) (type dash) (color 72 72 72 1)) (fill (type none)) (uuid {U()}))')
    out.append(f'  (text "{title}" (at {f(x1+1.27)} {f(y1+2.54)} 0) (effects (font (size 1.778 1.778) bold) (justify left)) (uuid {U()}))')
def note(txt, x, y, size=1.27):
    out.append(f'  (text "{txt}" (at {f(x)} {f(y)} 0) (effects (font (size {size} {size})) (justify left)) (uuid {U()}))')
rect(12.7, 22.86, 110.49, 71.12, "POWER INPUT + REVERSE-POLARITY PROTECTION + DECOUPLING")
rect(12.7, 78.74, 127.0, 160.02, "CLOCK: NE555 ASTABLE OSCILLATOR")
rect(139.7, 78.74, 203.2, 147.32, "COUNTER: CD4017 DECADE")
rect(213.36, 48.26, 281.94, 160.02, "LED RING (ONE LED ON AT A TIME)")
note("f = 1.44 / ((R1 + 2(R2 + RV1)) C1)", 15.24, 152.4)
note("RV1 = 0..100k  ->  f = 1.4 Hz .. 14.6 Hz", 15.24, 156.21)
note("Only one LED is on at a time,\\nso one shared R3 sets the current:\\nI <= (9 V - 2 V) / 470 = 15 mA\\n(CD4017 output drive limits it to ~5-10 mA)\\nD1-D10: 5 mm red LEDs", 246.38, 127.0)
note("D11 blocks reverse polarity (0.3 V drop).\\nC4 / C5: 100 nF decoupling next to U1 and U2.", 15.24, 64.77)
rect(12.7, 172.72, 76.2, 195.58, "MECHANICAL")

title = f'''  (title_block
    (title "LED Chaser - NE555 + CD4017 Running Light")
    (date "2026-11-22")
    (rev "1.0")
    (company "Kean Fah Chai")
    (comment 1 "10-LED ring chaser with adjustable speed")
    (comment 2 "Through-hole, 2-layer, beginner friendly")
  )'''
sch = [f'(kicad_sch (version 20230121) (generator eeschema)', f'  (uuid {ROOT})', '  (paper "A4")', title,
       '  (lib_symbols', *["    " + b for b in libsyms.values()], '  )', *out,
       '  (sheet_instances (path "/" (page "1")))', ')']
open(f"{PROJ}/{NAME}.kicad_sch", "w").write("\n".join(sch) + "\n")
json.dump(uuids, open(f"{PROJ}/.sym_uuids.json", "w"))
json.dump({"meta": {"filename": f"{NAME}.kicad_pro", "version": 1}, "sheets": [[ROOT, ""]]}, open(f"{PROJ}/{NAME}.kicad_pro", "w"), indent=2)
print("ok", len(PARTS), "parts")
