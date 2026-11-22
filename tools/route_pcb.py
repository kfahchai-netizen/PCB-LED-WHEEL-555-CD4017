import sys, time, math
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import pcbnew
from astar_router import Router
PCB = sys.argv[1]
mm = pcbnew.FromMM
b = pcbnew.LoadBoard(PCB)
for t in list(b.GetTracks()):
    b.Remove(t)
for z in list(b.Zones()):
    b.Remove(z)

widths = {"VCC": 0.7, "VIN": 0.7, "GND": 0.7}
order = ["VIN", "VCC", "CLK"] + [f"Q{i}" for i in range(10)] + ["LEDK", "THR", "DIS", "POT", "CV", "CLKLED", "GND"]
r = Router(b, grid=0.2, clearance=0.3, widths=widths, via_cost=5.0, bend_cost=0.5)
t0 = time.time()
ok = r.route_all(order)
print("routing", "OK" if ok else "INCOMPLETE", f"{time.time() - t0:.1f}s")
r.commit()

# GND pour on both layers, slightly inside the round edge
CX, CY, RZ = 100.0, 100.0, 39.4
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet("GND"))
    ol = z.Outline(); ol.NewOutline()
    for k in range(96):
        a = 2 * math.pi * k / 96
        ol.Append(mm(CX + RZ * math.cos(a)), mm(CY + RZ * math.sin(a)))
    z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.4)); z.SetThermalReliefSpokeWidth(mm(0.5))
    z.SetIsFilled(False); b.Add(z)
for fp in b.GetFootprints():          # pads the DRC flagged as starved: solid connection instead of thermal spokes
    for p in fp.Pads():
        if (fp.GetReference(), p.GetNumber()) in {("C1", "2")}:
            p.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn = b.GetConnectivity()
print("unrouted connections:", conn.GetUnconnectedCount(True))
tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
print("tracks", len(tracks), "vias", len(vias), "length mm", round(sum(pcbnew.ToMM(t.GetLength()) for t in tracks)))
b.Save(PCB)
print("DRC report written:", pcbnew.WriteDRCReport(b, "/tmp/drc.rpt", pcbnew.EDA_UNITS_MILLIMETRES, True))
