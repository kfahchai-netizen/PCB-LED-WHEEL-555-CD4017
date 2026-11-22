import os, sys, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design import PARTS
groups = collections.OrderedDict()
for ref, (lib, val, fp, *_r) in sorted(PARTS.items(), key=lambda kv: (kv[0].rstrip("0123456789"), int("".join(c for c in kv[0] if c.isdigit())))):
    if ref.startswith("H"):
        continue
    groups.setdefault((val, fp), []).append(ref)
w = csv.writer(sys.stdout)
w.writerow(["Qty", "References", "Value", "Footprint"])
for (val, fp), refs in groups.items():
    w.writerow([len(refs), " ".join(refs), val, fp.split(":")[1]])
