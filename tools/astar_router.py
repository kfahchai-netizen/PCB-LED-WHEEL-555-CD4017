"""
Tiny 2-layer A* autorouter for KiCad 7 boards (pcbnew Python API).

* Rasterises copper of *other* nets (pads, tracks, vias) on a fine grid, inflated by
  clearance + half the track width, so any free cell is a legal track centre.
* Routes each multi-pin net as a growing tree: multi-source A* from the tree to the
  next-nearest pad, 8-direction moves (45-degree routing), bend and via penalties.
* Rip-up-and-retry: if a net fails, it is moved to the front of the queue and the
  whole board is re-routed.
"""
import heapq, math
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
import pcbnew

mm, to_mm = pcbnew.FromMM, pcbnew.ToMM
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Router:
    def __init__(self, board, grid=0.2, clearance=0.25, via_d=0.8, via_drill=0.4,
                 edge_clear=0.6, via_cost=6.0, bend_cost=0.6, widths=None):
        self.b, self.g, self.clr = board, grid, clearance
        self.via_r, self.via_drill = via_d / 2, via_drill
        self.edge_clear, self.via_cost, self.bend_cost = edge_clear, via_cost, bend_cost
        self.widths = widths or {}
        bb = board.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = to_mm(bb.GetLeft()) - 1, to_mm(bb.GetTop()) - 1
        self.nx = int((to_mm(bb.GetWidth()) + 2) / grid) + 1
        self.ny = int((to_mm(bb.GetHeight()) + 2) / grid) + 1
        self.board_poly = self._edge_poly()
        self.pads = []                       # (netname, shapely poly, footprint ref)
        self.holes = []                      # NPTH
        for fp in board.GetFootprints():
            for p in fp.Pads():
                poly = self._pad_poly(p)
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    self.holes.append(poly)
                    continue
                # pads without a net (e.g. unused IC pins) are obstacles for every net: name "" never matches
                self.pads.append((p.GetNetname(), poly, fp.GetReference(), p.GetNumber()))
        self.routed = {}                     # net -> list of (layer_idx, LineString/Point, width) copper
        self.paths = {}                      # net -> list of cell paths

    # ---------- geometry ----------
    def _edge_poly(self):
        polys = []
        for d in self.b.GetDrawings():
            if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_CIRCLE:
                c = d.GetCenter()
                return Point(to_mm(c.x), to_mm(c.y)).buffer(to_mm(d.GetRadius()), 128)
        raise ValueError("only circular outlines supported")

    def _pad_poly(self, pad):
        sps = pad.GetEffectivePolygon()
        out = sps.Outline(0)
        pts = [(to_mm(out.CPoint(i).x), to_mm(out.CPoint(i).y)) for i in range(out.PointCount())]
        return Polygon(pts) if len(pts) >= 3 else Point(to_mm(pad.GetPosition().x), to_mm(pad.GetPosition().y)).buffer(0.8)

    def cell(self, x, y):
        return int(round((x - self.x0) / self.g)), int(round((y - self.y0) / self.g))

    def xy(self, i, j):
        return self.x0 + i * self.g, self.y0 + j * self.g

    def _raster(self, geoms):
        img = Image.new("1", (self.nx, self.ny), 0)
        dr = ImageDraw.Draw(img)
        for gm in geoms:
            if gm.is_empty:
                continue
            for poly in getattr(gm, "geoms", [gm]):
                pts = [((x - self.x0) / self.g, (y - self.y0) / self.g) for x, y in poly.exterior.coords]
                dr.polygon(pts, fill=1, outline=1)
        return np.array(img, dtype=bool)          # [j, i]

    def _blocked(self, net, half):
        """Per-layer masks of forbidden track centres for `net` with half-width `half`."""
        infl = self.clr + half
        masks = []
        for li in range(2):
            geoms = [poly.buffer(infl, 8) for n, poly, *_ in self.pads if n != net]
            geoms += [h.buffer(infl, 8) for h in self.holes]
            for n, items in self.routed.items():
                if n == net:
                    continue
                for l, g, w in items:
                    if l == li or l == 2:
                        geoms.append(g.buffer(w / 2 + infl, 8))
            m = self._raster(geoms)
            masks.append(m)
        outside = ~self._raster([self.board_poly.buffer(-(self.edge_clear + half), 64)])
        return [m | outside for m in masks]

    # ---------- search ----------
    def _astar(self, sources, target_cells, goal_xy, blk, vblk):
        tset = target_cells
        gx, gy = goal_xy
        def h(i, j):
            dx, dy = abs(i - gx), abs(j - gy)
            return (max(dx, dy) - min(dx, dy)) + 1.41421 * min(dx, dy)
        openq, best, parent = [], {}, {}
        for s in sources:
            l, i, j = s
            st = (l, i, j, -1)
            best[st] = 0.0
            heapq.heappush(openq, (h(i, j), 0.0, st))
        vc = self.via_cost / self.g
        while openq:
            f, gcost, st = heapq.heappop(openq)
            if best.get(st, 1e18) < gcost - 1e-9:
                continue
            l, i, j, d = st
            if (l, i, j) in tset:
                path = [st]
                while st in parent:
                    st = parent[st]; path.append(st)
                return [(p[0], p[1], p[2]) for p in reversed(path)]
            for k, (di, dj) in enumerate(DIRS):
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.nx and 0 <= nj < self.ny) or blk[l][nj, ni]:
                    continue
                if di and dj and (blk[l][j, ni] or blk[l][nj, i]):
                    continue                       # don't cut corners
                c = gcost + (1.41421 if di and dj else 1.0) + (self.bend_cost if d not in (-1, k) else 0)
                ns = (l, ni, nj, k)
                if c < best.get(ns, 1e18):
                    best[ns] = c; parent[ns] = st
                    heapq.heappush(openq, (c + h(ni, nj), c, ns))
            if not vblk[0][j, i] and not vblk[1][j, i]:
                ns = (1 - l, i, j, -1)
                c = gcost + vc
                if c < best.get(ns, 1e18):
                    best[ns] = c; parent[ns] = st
                    heapq.heappush(openq, (c + h(i, j), c, ns))
        return None

    def _pad_cells(self, poly, blk):
        cells = set()
        minx, miny, maxx, maxy = poly.bounds
        i0, j0 = self.cell(minx, miny); i1, j1 = self.cell(maxx, maxy)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                if poly.contains(Point(*self.xy(i, j))):
                    for l in range(2):
                        if not blk[l][j, i]:
                            cells.add((l, i, j))
        return cells

    def route_net(self, net):
        w = self.widths.get(net, 0.4)
        blk = self._blocked(net, w / 2)
        vblk = self._blocked(net, self.via_r)
        pads = [(poly, ref, num) for n, poly, ref, num in self.pads if n == net]
        if len(pads) < 2:
            return True
        cells = [self._pad_cells(p, blk) for p, *_ in pads]
        if any(not c for c in cells):
            return False
        tree = set(cells[0]); done = {0}; paths = []
        while len(done) < len(pads):
            # pick nearest unconnected pad to the tree (by centroid distance)
            tpts = np.array([[c[1], c[2]] for c in tree])
            best_k, best_d = None, 1e18
            for k in range(len(pads)):
                if k in done:
                    continue
                c = pads[k][0].centroid
                ci, cj = self.cell(c.x, c.y)
                dd = np.min(np.hypot(tpts[:, 0] - ci, tpts[:, 1] - cj))
                if dd < best_d:
                    best_k, best_d = k, dd
            c = pads[best_k][0].centroid
            goal = self.cell(c.x, c.y)
            # route from the new pad (sources) to the tree (targets): the heuristic aims at the nearest tree cell
            ti = int(np.argmin(np.hypot(tpts[:, 0] - goal[0], tpts[:, 1] - goal[1])))
            path = self._astar(list(cells[best_k]), tree, tuple(tpts[ti]), blk, vblk)
            if path is None:
                return False
            paths.append(path)
            tree |= set(path) | {(1 - l, i, j) for l, i, j in path if (1 - l, i, j) in cells[best_k]}
            tree |= cells[best_k]
            done.add(best_k)
        self.paths[net] = paths
        self.routed[net] = self._copper(paths, w)
        return True

    def _copper(self, paths, w):
        items = []
        for path in paths:
            for (l1, i1, j1), (l2, i2, j2) in zip(path, path[1:]):
                if l1 != l2:
                    items.append((2, Point(*self.xy(i1, j1)), self.via_r * 2))
                else:
                    items.append((l1, LineString([self.xy(i1, j1), self.xy(i2, j2)]), w))
        return items

    def route_all(self, order, max_attempts=12, log=print):
        order = list(order)
        for attempt in range(max_attempts):
            self.routed, self.paths = {}, {}
            failed = [n for n in order if not self.route_net(n)]
            log(f"attempt {attempt + 1}: routed {len(order) - len(failed)}/{len(order)} failed={failed}")
            if not failed:
                return True
            order = failed + [n for n in order if n not in failed]
        return False

    # ---------- write back to KiCad ----------
    def commit(self):
        for net, paths in self.paths.items():
            ni = self.b.FindNet(net)
            w = mm(self.widths.get(net, 0.4))
            for path in paths:
                segs = self._simplify(path)
                for kind, a, b, l in segs:
                    if kind == "via":
                        v = pcbnew.PCB_VIA(self.b); v.SetPosition(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
                        v.SetDrill(mm(self.via_drill)); v.SetWidth(mm(self.via_r * 2)); v.SetNet(ni)
                        self.b.Add(v)
                    else:
                        t = pcbnew.PCB_TRACK(self.b)
                        t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
                        t.SetWidth(w); t.SetLayer(LAYERS[l]); t.SetNet(ni); self.b.Add(t)

    def _simplify(self, path):
        """Split at layer changes (vias); merge collinear steps into straight segments."""
        out, runs, cur = [], [], [path[0]]
        for a, b in zip(path, path[1:]):
            if a[0] != b[0]:
                runs.append(cur); out_via = self.xy(b[1], b[2]); runs.append(("via", out_via)); cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        for r in runs:
            if isinstance(r, tuple):
                out.append(("via", r[1], None, None)); continue
            if len(r) < 2:
                continue
            verts = [r[0]]
            for k in range(1, len(r) - 1):
                d1 = (r[k][1] - r[k-1][1], r[k][2] - r[k-1][2]); d2 = (r[k+1][1] - r[k][1], r[k+1][2] - r[k][2])
                if d1 != d2:
                    verts.append(r[k])
            verts.append(r[-1])
            for a, b in zip(verts, verts[1:]):
                out.append(("seg", self.xy(a[1], a[2]), self.xy(b[1], b[2]), a[0]))
        return out
