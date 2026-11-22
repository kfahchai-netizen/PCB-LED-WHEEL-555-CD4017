#!/usr/bin/env bash
# Rebuild the whole LED Wheel design from tools/design.py (needs KiCad 7+ with its Python module).
#   pip install shapely numpy pillow cairosvg
set -euo pipefail
cd "$(dirname "$0")"
K=kicad; N=led_chaser; T=tools
python3 $T/gen_sch.py $K $N                                   # schematic from design.py
python3 $T/gen_pcb.py $K $N                                   # footprints, nets, outline, silkscreen
python3 $T/write_pro.py $K $N                                 # net classes + design rules
python3 $T/route_pcb.py $K/$N.kicad_pcb                       # A* autorouter + GND pours + DRC
mkdir -p fabrication/gerbers docs/images
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask -o fabrication/gerbers/ $K/$N.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map \
  --map-format gerberx2 -o fabrication/gerbers/ $K/$N.kicad_pcb
(cd fabrication/gerbers && rm -f ../${N}_gerbers_jlcpcb.zip && zip -q ../${N}_gerbers_jlcpcb.zip *)
kicad-cli sch export pdf -o docs/${N}_schematic.pdf $K/$N.kicad_sch
kicad-cli sch export svg -o docs/ $K/$N.kicad_sch
kicad-cli pcb export pdf --layers F.Cu,B.Cu,F.SilkS,Edge.Cuts -o docs/${N}_pcb.pdf $K/$N.kicad_pcb
python3 -c "import cairosvg; cairosvg.svg2png(url='docs/$N.svg', write_to='docs/images/schematic.png', output_width=2400, background_color='white')"
python3 $T/render_board.py $K/$N.kicad_pcb docs/images         # photo-style renders + GIF
python3 $T/make_bom.py > fabrication/bom.csv
echo "Build complete."
