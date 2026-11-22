import json, sys
PROJ, NAME = sys.argv[1], sys.argv[2]
p = f"{PROJ}/{NAME}.kicad_pro"
d = json.load(open(p))
def cls(name, tw, clr):
    return {"name": name, "clearance": clr, "track_width": tw, "via_diameter": 0.8, "via_drill": 0.4,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.2, "line_style": 0, "wire_width": 6, "bus_width": 12,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"}
d["net_settings"] = {"classes": [cls("Default", 0.4, 0.25), cls("Power", 0.7, 0.3)], "meta": {"version": 3},
                     "net_colors": None, "netclass_assignments": None,
                     "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in ("GND", "VCC", "VIN")]}
d["board"] = {"design_settings": {"rules": {"min_clearance": 0.2, "min_track_width": 0.2, "min_via_diameter": 0.6,
              "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.5, "min_hole_clearance": 0.25,
              "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0, "min_text_height": 0.8}}}
json.dump(d, open(p, "w"), indent=2)
print("pro ok")
