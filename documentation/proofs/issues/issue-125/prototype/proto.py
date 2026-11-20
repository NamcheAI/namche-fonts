"""Prototype: inner-corner fill by rule instead of fixed radius.
r90 = min(C * stem, RMAX); acute corners: equal ink area -> r = r90*sqrt(f(90)/f(theta)).
Fill built by local morphological closing (keeps convex corners sharp)."""
import sys, math
sys.path.insert(0, "/home/claude/work")
import skia, pathops
from fontTools.pens.recordingPen import RecordingPen
from render import SkPen

C, RMAX, SPACE = 0.6, 55.0, 0.45

def f_theta(th):
    t = math.radians(th); return 1/math.tan(t/2) - (math.pi - t)/2
F90 = f_theta(90)

def pp_to_sk(pp):
    pen = SkPen(); pp.draw(pen); return pen.path

from fontTools.pens.basePen import BasePen
class _SegPen(BasePen):
    def __init__(self):
        super().__init__(None); self.conts = []; self.cur = None
    def _moveTo(self, p): self.cur = {"start": p, "segs": [], "last": p}
    def _lineTo(self, p): self.cur["segs"].append([self.cur["last"], p]); self.cur["last"] = p
    def _qCurveToOne(self, a, p): self.cur["segs"].append([self.cur["last"], a, p]); self.cur["last"] = p
    def _curveToOne(self, a, b, p): self.cur["segs"].append([self.cur["last"], a, b, p]); self.cur["last"] = p
    def _closePath(self):
        c = self.cur
        if c["last"] != c["start"]: c["segs"].append([c["last"], c["start"]])
        self.conts.append(c["segs"]); self.cur = None
    _endPath = _closePath

def corner_list(pp):
    pen = _SegPen(); pp.draw(pen)
    from fontTools.pens.areaPen import AreaPen
    ap = AreaPen(); pp.draw(ap)
    ink_left = ap.value > 0
    out = []
    for segs in pen.conts:
        n = len(segs)
        def tang(a, b):
            v = a[-1]
            pin = next((q for q in reversed(a[:-1]) if math.dist(q, v) > 1e-6), None)
            pout = next((q for q in b[1:] if math.dist(q, v) > 1e-6), None)
            if pin is None or pout is None: return None
            t1 = (v[0]-pin[0], v[1]-pin[1]); t2 = (pout[0]-v[0], pout[1]-v[1])
            l1, l2 = math.hypot(*t1), math.hypot(*t2)
            cr = (t1[0]*t2[1]-t1[1]*t2[0])/(l1*l2); dt = (t1[0]*t2[0]+t1[1]*t2[1])/(l1*l2)
            return t1, t2, l1, l2, math.degrees(math.atan2(cr, dt))
        turns = [tang(segs[i], segs[(i + 1) % n]) for i in range(n)]
        def run_len(i, step):
            # length of smooth outline from vertex i (end of segs[i]) until the next real corner
            total = 0.0; k = (i + 1) % n if step > 0 else i
            for _ in range(n):
                total += math.dist(segs[k][0], segs[k][-1])
                j = k if step > 0 else (k - 1) % n   # vertex index at far end
                tj = turns[j]
                if tj is None or abs(tj[4]) >= 12: break
                k = (k + step) % n
            return total
        for i in range(n):
            tr = turns[i]
            if tr is None: continue
            t1, t2, l1, l2, turn = tr
            if abs(turn) < 12: continue
            v = segs[i][-1]
            if (turn < 0) if ink_left else (turn > 0):
                din = (-t1[0]/l1, -t1[1]/l1); dout = (t2[0]/l2, t2[1]/l2)
                L = min(run_len(i, 1), run_len(i, -1))
                out.append(dict(v=v, theta=180-abs(turn), din=din, dout=dout, L=L))
    return out

def radius(theta, stem, c=C, rmax=RMAX):
    r90 = min(c * stem, rmax)
    r = r90 if theta >= 90 else r90 * math.sqrt(F90 / f_theta(theta))
    return r

def stroke_fill(path, w):
    p = pathops.Path(); p.addPath(path)
    p.stroke(w, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    p.convertConicsToQuads(); return p

def op(a, b, kind):
    try:
        return pathops.op(a, b, kind, fix_winding=True)
    except pathops.PathOpsError:
        a2 = pathops.Path(); a2.addPath(a); a2.simplify(fix_winding=True)
        b2 = pathops.Path(); b2.addPath(b); b2.simplify(fix_winding=True)
        return pathops.op(a2, b2, kind, fix_winding=True)
U, D_, I = pathops.PathOp.UNION, pathops.PathOp.DIFFERENCE, pathops.PathOp.INTERSECTION

def closing(P, r):
    D = op(P, stroke_fill(P, 2*r), U)
    return op(D, stroke_fill(D, 2*r), D_)

def cone_mask(cn, R, widen=25):
    v = cn["v"]; a1 = math.atan2(cn["din"][1], cn["din"][0]); a2 = math.atan2(cn["dout"][1], cn["dout"][0])
    # sweep the short way (the white wedge), widened
    d = (a2 - a1 + math.pi) % (2*math.pi) - math.pi
    lo, hi = (a1, a1 + d) if d > 0 else (a1 + d, a1)
    lo -= math.radians(widen); hi += math.radians(widen)
    m = pathops.Path(); m.moveTo(*v)
    k = 24
    for i in range(k + 1):
        a = lo + (hi - lo) * i / k; m.lineTo(v[0] + R*math.cos(a), v[1] + R*math.sin(a))
    m.close(); return m

def fill_corners(pp, stem, c=C, rmax=RMAX, space=SPACE, log=None, as_skia=True):
    """Every inner corner receives the same ink area A* = F90 * r90^2, r90 = min(c*stem, rmax).
    Radius per corner is solved so the actual filled area hits A* (handles curves and
    near-tangent joins), limited by the space cap along the adjacent segments."""
    P = pathops.Path(); P.addPath(pp)
    cache = {}
    def clos(r):
        k = round(r * 4) / 4
        if k not in cache:
            cache[k] = None
            for jitter in (0, 0.07, -0.11, 0.19):
                try: cache[k] = closing(P, k + jitter); break
                except pathops.PathOpsError: pass
        return cache[k]
    def fill_for(cn, r, th):
        Cl = clos(r)
        if Cl is None: return None, 0.0
        t = r / math.tan(math.radians(min(th, 179))/2) if th < 179 else r
        mask = cone_mask(cn, 1.35 * max(t, r) + 2, widen=40)
        for other in cl:
            if other is cn: continue
            vx, vy = cn["v"]; ox, oy = other["v"]
            d = math.dist((vx, vy), (ox, oy))
            if d < 1e-6 or d > 2 * (1.35 * max(t, r) + 2): continue
            # half-plane closer to this corner than to the other (Voronoi cell)
            mx, my = (vx + ox) / 2, (vy + oy) / 2; nx, ny = (vx - ox) / d, (vy - oy) / d
            tx, ty = -ny, nx; B = 5000
            hp = pathops.Path()
            hp.moveTo(mx + tx*B, my + ty*B); hp.lineTo(mx + tx*B + nx*B, my + ty*B + ny*B)
            hp.lineTo(mx - tx*B + nx*B, my - ty*B + ny*B); hp.lineTo(mx - tx*B, my - ty*B); hp.close()
            try: mask = op(mask, hp, I)
            except pathops.PathOpsError: pass
        try: f = op(op(Cl, mask, I), P, D_)
        except pathops.PathOpsError: return None, 0.0
        return f, abs(f.area)
    r90 = min(c * stem, rmax); target = F90 * r90 * r90
    out = P
    cl = corner_list(pp)
    for cn in cl:
        th = cn["theta"]
        r_cap = space * cn["L"] * math.tan(math.radians(min(th, 90))/2)
        r0 = min(radius(th, stem, c, rmax), r_cap)
        if r0 < 1.0: continue
        f, A = fill_for(cn, r0, th)
        if f is None: continue
        if th < 90:   # solve r so that A == target (bisection on log scale)
            lo, hi = 0.5, r_cap
            if A > target: hi = r0
            else: lo = r0
            best = (abs(A - target), f, A, r0)
            for _ in range(7):
                if hi - lo < 0.5: break
                r = math.sqrt(lo * hi)
                f2, A2 = fill_for(cn, r, th)
                if f2 is None: break
                if abs(A2 - target) < best[0]: best = (abs(A2 - target), f2, A2, r)
                if A2 > target: hi = r
                else: lo = r
            _, f, A, r0 = best
        if A > 3 * target + 60:
            if log is not None: log.append((th, round(r0, 1), "skipped", round(A)))
            continue
        try: out = op(out, f, U)
        except pathops.PathOpsError:
            if log is not None: log.append((th, r0, "union-failed")); continue
        if log is not None: log.append((th, round(r0, 1), round(A)))
    try:   # heal hairline gaps where neighbouring corner fills meet
        heal = op(closing(out, 2.0), out, D_)
        if abs(heal.area) < 8 * len(cl) + 40:   # only hairlines, never a counter
            out = op(out, heal, U)
    except pathops.PathOpsError:
        pass
    return pp_to_sk(out) if as_skia else out
