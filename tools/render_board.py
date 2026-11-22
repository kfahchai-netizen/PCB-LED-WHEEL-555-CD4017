"""Photo-style board renders (front/back) + animated LED-chase GIF, composited from KiCad layer exports."""
import subprocess, sys, math, io
import numpy as np, cairosvg, pcbnew
from PIL import Image, ImageDraw, ImageFilter
PCB, OUT = sys.argv[1], sys.argv[2]
W = 1400
b = pcbnew.LoadBoard(PCB)
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
SPAN = pcbnew.ToMM(bb.GetWidth())
S = W / SPAN

def layer_mask(layers, mirror=False):
    svg = "/tmp/_layer.svg"
    cmd = ["kicad-cli", "pcb", "export", "svg", "--layers", layers + ",Edge.Cuts", "--black-and-white",
           "--page-size-mode", "2", "--exclude-drawing-sheet", "-o", svg, PCB]
    if mirror: cmd.insert(4, "--mirror")
    subprocess.run(cmd, check=True, capture_output=True)
    png = cairosvg.svg2png(url=svg, output_width=W, output_height=W, background_color="white")
    return np.array(Image.open(io.BytesIO(png)).convert("L")) < 128

def px(x, y, mirror=False):
    u = (x - X0) * S
    return (W - u if mirror else u), (y - Y0) * S

def render(side):
    mir = side == "back"
    cu = layer_mask("F.Cu" if not mir else "B.Cu", mir)
    mask_open = layer_mask("F.Mask" if not mir else "B.Mask", mir)
    silk = layer_mask("F.SilkS" if not mir else "B.SilkS", mir)
    img = np.zeros((W, W, 3), np.uint8); img[:] = (236, 239, 242)
    yy, xx = np.mgrid[0:W, 0:W]
    inside = (xx - W / 2) ** 2 + (yy - W / 2) ** 2 <= (W / 2 - 2) ** 2
    img[inside] = (22, 92, 52)                          # FR4 under solder mask
    img[inside & cu] = (38, 128, 70)                    # copper under mask
    img[inside & cu & mask_open] = (214, 176, 72)       # exposed ENIG pads
    img[inside & silk & ~mask_open] = (246, 246, 240)   # silkscreen
    im = Image.fromarray(img); d = ImageDraw.Draw(im)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetDrillSize().x > 0:
                x, y = px(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), mir)
                r = pcbnew.ToMM(p.GetDrillSize().x) / 2 * S
                d.ellipse([x - r, y - r, x + r, y + r], fill=(236, 239, 242) if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else (40, 40, 40))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            x, y = px(pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y), mir)
            r = pcbnew.ToMM(t.GetDrillValue()) / 2 * S
            d.ellipse([x - r, y - r, x + r, y + r], fill=(30, 30, 30))
    return im

front, back = render("front"), render("back")
front.save(f"{OUT}/pcb_front.png"); back.save(f"{OUT}/pcb_back.png")
combo = Image.new("RGB", (W * 2 + 40, W), (236, 239, 242)); combo.paste(front, (0, 0)); combo.paste(back, (W + 40, 0))
combo.resize((combo.width // 2, combo.height // 2), Image.LANCZOS).save(f"{OUT}/pcb_front_back.png")

# ---- LED chase animation ----
leds = []
for i in range(1, 11):
    fp = b.FindFootprintByReference(f"D{i}")
    ps = [p.GetPosition() for p in fp.Pads()]
    leds.append(px(pcbnew.ToMM(sum(p.x for p in ps) / 2), pcbnew.ToMM(sum(p.y for p in ps) / 2)))
clk = b.FindFootprintByReference("D12"); cps = [p.GetPosition() for p in clk.Pads()]
clk_xy = px(pcbnew.ToMM(sum(p.x for p in cps) / 2), pcbnew.ToMM(sum(p.y for p in cps) / 2))
R = 2.5 * S
frames = []
small = 700
for k in range(20):
    active = (k // 2) % 10
    base = front.copy().convert("RGBA")
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0)); l = ImageDraw.Draw(lay)
    for i, (x, y) in enumerate(leds):
        on = i == active
        if on:
            g.ellipse([x - R * 3.2, y - R * 3.2, x + R * 3.2, y + R * 3.2], fill=(255, 40, 30, 170))
        l.ellipse([x - R, y - R, x + R, y + R], fill=(255, 70, 60, 255) if on else (120, 20, 20, 235), outline=(60, 0, 0, 255), width=3)
        l.ellipse([x - R * 0.45, y - R * 0.6, x - R * 0.05, y - R * 0.2], fill=(255, 220, 220, 200 if on else 70))
    rc = 1.5 * S; cx, cy = clk_xy
    l.ellipse([cx - rc, cy - rc, cx + rc, cy + rc], fill=(90, 255, 120, 255) if k % 2 == 0 else (20, 90, 40, 235), outline=(0, 50, 0, 255), width=2)
    if k % 2 == 0:
        g.ellipse([cx - rc * 3, cy - rc * 3, cx + rc * 3, cy + rc * 3], fill=(60, 255, 100, 140))
    glow = glow.filter(ImageFilter.GaussianBlur(R * 1.2))
    fr = Image.alpha_composite(Image.alpha_composite(base, glow), lay).convert("RGB").resize((small, small), Image.LANCZOS)
    frames.append(fr.convert("P", palette=Image.ADAPTIVE, colors=128))
frames[0].save(f"{OUT}/led_wheel_animation.gif", save_all=True, append_images=frames[1:], duration=110, loop=0, optimize=True)
print("renders ok")
