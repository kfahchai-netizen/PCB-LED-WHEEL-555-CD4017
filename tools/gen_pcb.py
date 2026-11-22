"""Build the round LED-wheel PCB from design.py (stage 1: placement, nets, outline, silkscreen)."""
import sys, json, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import pcbnew
from design import PARTS
PROJ, NAME = sys.argv[1], sys.argv[2]
FPL = "/usr/share/kicad/footprints/"
mm = pcbnew.FromMM
CX, CY = 100.0, 100.0          # board centre on the KiCad page
R_BOARD = 40.0                 # 80 mm round board
uuids = json.load(open(f"{PROJ}/.sym_uuids.json"))

# placement relative to board centre: ref -> (x, y, rotation_deg)
PLACE = {
    "U2": (3.0, -8.89, 0), "U1": (-12.5, -11.0, 0),
    "R1": (-14.0, 0.5, 0), "R2": (-14.0, 4.0, 0), "RV1": (-15.0, 14.5, 0),
    "C1": (-7.0, 11.0, 0), "C2": (-17.5, -8.0, 90), "C5": (-12.5, -15.0, 0),
    "C4": (3.0, -13.0, 0), "R3": (15.0, 4.0, 90), "C3": (14.0, -12.0, 0),
    "D12": (-9.0, -19.0, 0), "R4": (-3.0, -19.0, 0),
    "J1": (-2.54, 20.5, 0), "D11": (14.16, 12.5, 180),
}
R_LED_K = 32.27                # cathode pad radius; anode pad sits 2.54 mm further in
for i in range(10):
    th = -90 + 36 * i
    PLACE[f"D{i+1}"] = (R_LED_K * math.cos(math.radians(th)), R_LED_K * math.sin(math.radians(th)), 180 - th)
for i, th in enumerate((-36, 36, 144, 216)):
    PLACE[f"H{i+1}"] = (35.5 * math.cos(math.radians(th)), 35.5 * math.sin(math.radians(th)), 0)

board = pcbnew.BOARD()
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name); board.Add(n); nets[name] = n
    return nets[name]

for ref, (lib_id, value, fpid, at, rot, mir, pinnets) in PARTS.items():
    lib, fpname = fpid.split(":")
    fp = pcbnew.FootprintLoad(FPL + lib + ".pretty", fpname)
    fp.SetReference(ref); fp.SetValue(value)
    fp.SetFPID(pcbnew.LIB_ID(lib, fpname))
    fp.SetPath(pcbnew.KIID_PATH("/" + uuids[ref]))
    fp.SetProperty("Sheetname", ""); fp.SetProperty("Sheetfile", f"{NAME}.kicad_sch")
    x, y, r = PLACE[ref]
    board.Add(fp)
    fp.SetPosition(pcbnew.VECTOR2I(mm(CX + x), mm(CY + y)))
    fp.SetOrientationDegrees(r % 360)
    for pad in fp.Pads():
        n = pinnets.get(pad.GetNumber())
        if n: pad.SetNet(net(n))
    if ref.startswith("D") and ref not in ("D11", "D12"):
        fp.Value().SetVisible(False)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))

# tidy reference designators in the crowded centre
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref in ("U1", "U2", "R1", "R2", "R3", "R4"):
        pads = list(fp.Pads())
        cx = sum(p.GetPosition().x for p in pads) / len(pads); cy = sum(p.GetPosition().y for p in pads) / len(pads)
        fp.Reference().SetPosition(pcbnew.VECTOR2I(int(cx), int(cy)))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    if ref == "C5":
        fp.Reference().SetPosition(pcbnew.VECTOR2I(mm(CX - 15.6), mm(CY - 16.6)))

# round outline
c = pcbnew.PCB_SHAPE(board); c.SetShape(pcbnew.SHAPE_T_CIRCLE); c.SetLayer(pcbnew.Edge_Cuts)
c.SetCenter(pcbnew.VECTOR2I(mm(CX), mm(CY))); c.SetEnd(pcbnew.VECTOR2I(mm(CX + R_BOARD), mm(CY)))
c.SetWidth(mm(0.1)); board.Add(c)

def text(s, x, y, size=1.2, layer=pcbnew.F_SilkS, bold=False, angle=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(s); t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm(CX + x), mm(CY + y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    if angle: t.SetTextAngleDegrees(angle)
    if layer == pcbnew.B_SilkS: t.SetMirrored(True)
    board.Add(t)
text("LED WHEEL", 0, -24.2, 1.6, bold=True)
text("SPEED", -15.0, 19.3, 1.0)
text("+", -6.7, 20.5, 1.6, bold=True); text("-", 6.7, 20.5, 1.6, bold=True)
text("5-12V", 0, 26.6, 1.0)
text("LED WHEEL v1.0", 0, -26.6, 1.3, pcbnew.B_SilkS, bold=True)
text("Kean Fah Chai", 0, -24.4, 1.2, pcbnew.B_SilkS, bold=True)
text("Swinburne Sarawak 2026", 0, -22.3, 0.9, pcbnew.B_SilkS)
text("NE555 + CD4017 LED chaser", 0, 23.6, 0.9, pcbnew.B_SilkS)
text("github.com/kfahchai-netizen", 0, 25.6, 0.8, pcbnew.B_SilkS)

out = f"{PROJ}/{NAME}.kicad_pcb"
board.Save(out)
print("saved", out, "footprints", len(board.GetFootprints()), "nets", len(nets))
