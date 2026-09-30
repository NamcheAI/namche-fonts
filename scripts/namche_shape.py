#!/usr/bin/env python3
"""Namche Shape: generate the Metaball, Origin, and Skeleton outlines.

Every Namche Shape glyph starts from the pixel grid of the Geist Pixel source
(`sources/NamcheShape.glyphspackage`): each base glyph there is a set of
38-unit `pixel` components. This module turns that grid into outlines:

- Metaball: a full-pixel circle per cell; some orthogonal neighbours melt
  together through a neck half a pixel wide.
- Skeleton: the necks without the circles, a network of half-pixel strokes
  between cell centres.
- Origin: one of three shapes from the original Namche system (square,
  half-round, quarter disc) on every cell, inset like Geist Pixel Grid.

The random choices are seeded from the style and glyph name, so every build
produces identical outlines. `sources/NamcheShape/overrides.yaml` records
hand refinements that replace a random choice for a specific glyph.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import glyphsLib
import pathops
import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sources" / "NamcheShape.glyphspackage"
OVERRIDES = ROOT / "sources" / "NamcheShape" / "overrides.yaml"

P = 38  # grid pitch in font units
R = P / 2  # metaball circle radius
KAPPA = 0.5522847498

STYLES = ("Metaball", "Origin", "Skeleton")

# Style parameters. Keep them here so proofs and builds share one recipe.
METABALL_NECK_HALF = R / 2  # neck half width at the waist
METABALL_FILLET = R / 4  # fillet radius tangent to both circles
METABALL_LINK_P = 0.55  # chance that neighbours along a stroke melt

SKELETON_HALF = R / 2  # stroke half width
SKELETON_INNER = R / 2  # radius of rounded inner corners
SKELETON_LONE = R * 0.7  # radius of a pixel without neighbours
SKELETON_SOLID_MAX = 4  # only 2x2 dots stay solid
SKELETON_ALONG_P = 1.0  # links that continue a stroke (rails stay whole)
SKELETON_ACROSS_P = 0.5  # rungs between parallel strokes

ORIGIN_INSET = 4  # Geist Pixel Grid inset per side
ORIGIN_WEIGHTS = (("square", 0.3), ("bullet", 0.4), ("quarter", 0.3))
# "random": fixed orientation as in the briefing. "structure": round shapes
# turn toward the open side (bullets at stroke edges and ends) or the open
# outer corner (quarter discs), in the spirit of Letterform Variations.
ORIGIN_MODE = "structure"
METABALL_ACROSS_P = 0.2  # necks across a stroke (rungs between parallel columns)


# --------------------------------------------------------------------------
# Source grid


@dataclass
class GlyphGrid:
    name: str
    width: int
    cells: set[tuple[int, int]] = field(default_factory=set)  # lower-left corners
    components: list[tuple[str, tuple]] = field(default_factory=list)  # (ref, transform)


def load_grids(source: Path = SOURCE) -> dict[str, GlyphGrid]:
    font = glyphsLib.GSFont(str(source))
    master = font.masters[0].id
    grids = {}
    for glyph in font.glyphs:
        layer = glyph.layers[master]
        grid = GlyphGrid(glyph.name, int(layer.width))
        for shape in layer.shapes:
            ref = getattr(shape, "name", None)
            if ref is None:
                continue  # paths only occur in the non-exporting pixel glyphs
            if ref == "pixel":
                x, y = shape.position
                grid.cells.add((int(x), int(y)))
            else:
                grid.components.append((ref, tuple(shape.transform)))
        grids[glyph.name] = grid
    return grids


def variant_name(name: str, variant: int = 0) -> str:
    """Seed key of a contextual alternate; variant 0 is the default glyph."""
    return name if variant == 0 else f"{name}#{variant}"


def rule_name(name: str) -> str:
    """Overrides apply to a glyph and all of its alternates."""
    return name.split("#", 1)[0]


def seeded(style: str, name: str, salt: str = "") -> random.Random:
    digest = hashlib.sha256(f"{style}:{name}:{salt}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def orthogonal_links(cells: set[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    links = []
    for x, y in sorted(cells):
        if (x + P, y) in cells:
            links.append(((x, y), (x + P, y)))
        if (x, y + P) in cells:
            links.append(((x, y), (x, y + P)))
    return links


def load_overrides(path: Path = OVERRIDES) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def cell_key(cell) -> str:
    return f"{cell[0] // P},{cell[1] // P}"


def link_key(a, b) -> str:
    return f"{cell_key(a)}-{cell_key(b)}"


# --------------------------------------------------------------------------
# Path primitives (pathops.Path uses a pen protocol)


def circle(path: pathops.Path, cx: float, cy: float, r: float) -> None:
    k = KAPPA * r
    path.moveTo(cx + r, cy)
    path.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    path.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    path.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    path.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    path.close()


def rect(path: pathops.Path, x0, y0, x1, y1) -> None:
    path.moveTo(x0, y0)
    path.lineTo(x1, y0)
    path.lineTo(x1, y1)
    path.lineTo(x0, y1)
    path.close()


def arc_to(path: pathops.Path, cx, cy, r, a0, a1) -> None:
    """Append an arc (angles in radians) from a0 to a1; current point is at a0."""
    sweep = a1 - a0
    n = max(1, math.ceil(abs(sweep) / (math.pi / 2) - 1e-9))
    step = sweep / n
    k = 4 / 3 * math.tan(step / 4) * r
    for i in range(n):
        s0 = a0 + i * step
        s1 = s0 + step
        p0 = (cx + r * math.cos(s0), cy + r * math.sin(s0))
        p3 = (cx + r * math.cos(s1), cy + r * math.sin(s1))
        c1 = (p0[0] - k * math.sin(s0), p0[1] + k * math.cos(s0))
        c2 = (p3[0] + k * math.sin(s1), p3[1] - k * math.cos(s1))
        path.cubicTo(*c1, *c2, *p3)


class Shapes(list):
    """Collects closed shapes; each becomes its own boolean operand."""

    def new(self) -> pathops.Path:
        path = pathops.Path()
        self.append(path)
        return path


def union(shapes) -> pathops.Path:
    operands = []
    for shape in shapes if isinstance(shapes, list) else [shapes]:
        fixed = pathops.Path(shape)
        fixed.simplify(fix_winding=True)
        operands.append(fixed)
    result = pathops.Path()
    pathops.union(operands, result.getPen())
    return result


# --------------------------------------------------------------------------
# Metaball


def metaball_neck(path: pathops.Path, a, b) -> None:
    """Neck between cells a and b (orthogonal neighbours)."""
    (ax, ay), (bx, by) = a, b
    c1 = (ax + R, ay + R)
    c2 = (bx + R, by + R)
    mx, my = (c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2
    dx, dy = (c2[0] - c1[0]) / P, (c2[1] - c1[1]) / P  # unit axis
    nx, ny = -dy, dx  # unit normal
    w, r = METABALL_NECK_HALF, METABALL_FILLET
    side_points = []
    for sign in (1, -1):
        fx, fy = mx + sign * nx * (w + r), my + sign * ny * (w + r)
        t = []
        for c in (c1, c2):
            vx, vy = fx - c[0], fy - c[1]
            d = math.hypot(vx, vy)
            t.append((c[0] + R * vx / d, c[1] + R * vy / d))
        side_points.append(((fx, fy), t))
    # Right side: fillet arc from tangent on c1 to tangent on c2.
    (f1, (t1a, t1b)), (f2, (t2a, t2b)) = side_points
    path.moveTo(*t1a)
    a0 = math.atan2(t1a[1] - f1[1], t1a[0] - f1[0])
    a1 = math.atan2(t1b[1] - f1[1], t1b[0] - f1[0])
    arc_to(path, *f1, r, a0, a0 + _short(a1 - a0))
    path.lineTo(*t2b)
    a0 = math.atan2(t2b[1] - f2[1], t2b[0] - f2[0])
    a1 = math.atan2(t2a[1] - f2[1], t2a[0] - f2[0])
    arc_to(path, *f2, r, a0, a0 + _short(a1 - a0))
    path.close()


def _short(delta: float) -> float:
    while delta > math.pi:
        delta -= 2 * math.pi
    while delta < -math.pi:
        delta += 2 * math.pi
    return delta


def continues(cells, a, b) -> bool:
    """True when link a-b runs along a stroke rather than across it."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return (a[0] - dx, a[1] - dy) in cells or (b[0] + dx, b[1] + dy) in cells


def choose_links(style, name, cells, probability, overrides):
    """probability is a number or a callable (a, b) -> number."""
    rng = seeded(style, name, "links")
    rules = overrides.get(style, {}).get(rule_name(name), {})
    forced_on = set(rules.get("link", []))
    forced_off = set(rules.get("unlink", []))
    chosen = []
    for a, b in orthogonal_links(cells):
        key = link_key(a, b)
        p = probability(a, b) if callable(probability) else probability
        keep = rng.random() < p
        if key in forced_on:
            keep = True
        if key in forced_off:
            keep = False
        if keep:
            chosen.append((a, b))
    return chosen


def draw_metaball(name, cells, overrides) -> pathops.Path:
    shapes = Shapes()
    for x, y in sorted(cells):
        circle(shapes.new(), x + R, y + R, R)
    def probability(a, b):
        if METABALL_ACROSS_P is not None and not continues(cells, a, b):
            return METABALL_ACROSS_P
        return METABALL_LINK_P

    for a, b in choose_links("Metaball", name, cells, probability, overrides):
        metaball_neck(shapes.new(), a, b)
    return union(shapes)


# --------------------------------------------------------------------------
# Skeleton


def _components(cells):
    todo, parts = set(cells), []
    while todo:
        stack = [todo.pop()]
        part = set(stack)
        while stack:
            x, y = stack.pop()
            for dx in (-P, 0, P):
                for dy in (-P, 0, P):
                    n = (x + dx, y + dy)
                    if n in todo:
                        todo.remove(n)
                        part.add(n)
                        stack.append(n)
        parts.append(part)
    return parts


def skeleton_links(name, cells, overrides):
    """Connected trace: a random spanning tree plus random extra links.

    The tree keeps every stroke continuous, so letters stay legible; the
    extra links add the loops and round holes of the Skeleton texture.
    Diagonal links join cells that only touch at a corner.
    """
    rng = seeded("Skeleton", name, "links")
    rules = overrides.get("Skeleton", {}).get(rule_name(name), {})
    forced_on = set(rules.get("link", []))
    forced_off = set(rules.get("unlink", []))
    ortho = orthogonal_links(cells)
    diag = []
    for x, y in sorted(cells):
        for dx in (P, -P):
            b = (x + dx, y + P)
            if b in cells and (x + dx, y) not in cells and (x, y + P) not in cells:
                diag.append(((x, y), b))
    candidates = ortho + diag
    # Kruskal with random weights; strokes are preferred over rungs.
    weighted = []
    for a, b in candidates:
        along = continues(cells, a, b) if (a, b) in ortho else True
        weighted.append((rng.random() * (1.0 if along else 3.0), a, b))
    weighted.sort()
    parent = {c: c for c in cells}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c

    chosen = []
    extra = []
    for _, a, b in weighted:
        if link_key(a, b) in forced_off:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            chosen.append((a, b))
        else:
            extra.append((a, b))
    small = {c for part in _components(cells) if len(part) <= SKELETON_SOLID_MAX for c in part}
    for a, b in extra:
        p = SKELETON_ALONG_P if continues(cells, a, b) else SKELETON_ACROSS_P
        if a in small or rng.random() < p or link_key(a, b) in forced_on:
            chosen.append((a, b))
    return chosen, small


def draw_skeleton(name, cells, overrides) -> pathops.Path:
    links, small = skeleton_links(name, cells, overrides)
    h, ri = SKELETON_HALF, SKELETON_INNER
    shapes = Shapes()
    diagonal = Shapes()
    adjacency: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for a, b in links:
        (ax, ay), (bx, by) = a, b
        if ax != bx and ay != by:
            # Diagonal link: a capsule between the two cell centres.
            ux, uy = (bx - ax) / (P * math.sqrt(2)), (by - ay) / (P * math.sqrt(2))
            nx, ny = -uy * h, ux * h
            cap = diagonal.new()
            cap.moveTo(ax + R + nx, ay + R + ny)
            cap.lineTo(bx + R + nx, by + R + ny)
            cap.lineTo(bx + R - nx, by + R - ny)
            cap.lineTo(ax + R - nx, ay + R - ny)
            cap.close()
            circle(diagonal.new(), ax + R, ay + R, h)
            circle(diagonal.new(), bx + R, by + R, h)
            continue
        adjacency.setdefault(a, set()).add((bx - ax, by - ay))
        adjacency.setdefault(b, set()).add((ax - bx, ay - by))
        rect(shapes.new(), min(ax, bx) + R - h, min(ay, by) + R - h, max(ax, bx) + R + h, max(ay, by) + R + h)
    for x, y in sorted(cells):
        if (x, y) not in adjacency:
            # Node for a diagonal joint, or a visible dot for a lone pixel.
            lone = not any((x + dx, y + dy) in cells for dx in (-P, 0, P) for dy in (-P, 0, P) if dx or dy)
            circle(shapes.new(), x + R, y + R, SKELETON_LONE if lone else h)
    # Small marks (dots, accents) keep their counters closed.
    for x, y in sorted(small):
        if all(c in small for c in ((x + P, y), (x, y + P), (x + P, y + P))):
            rect(shapes.new(), x + R, y + R, x + R + P, y + R + P)
    body = union(shapes) if shapes else pathops.Path()
    # Round every outer corner by carving, then fill inner corners.
    carve = Shapes()
    fill = Shapes()
    for (x, y), dirs in adjacency.items():
        cx, cy = x + R, y + R
        for sx in (1, -1):
            for sy in (1, -1):
                hx, hy = (sx * P, 0) in dirs, (0, sy * P) in dirs
                if not hx and not hy:
                    ox, oy = cx + sx * h, cy + sy * h
                    corner = pathops.Path()
                    rect(corner, min(ox, cx), min(oy, cy), max(ox, cx), max(oy, cy))
                    keep = pathops.Path()
                    circle(keep, cx, cy, h)
                    pathops.difference([corner], [keep], carve.new().getPen())
                elif hx and hy:
                    ix, iy = cx + sx * h, cy + sy * h
                    qx, qy = ix + sx * ri, iy + sy * ri
                    patch = pathops.Path()
                    rect(patch, min(ix, qx), min(iy, qy), max(ix, qx), max(iy, qy))
                    cut = pathops.Path()
                    circle(cut, qx, qy, ri)
                    pathops.difference([patch], [cut], fill.new().getPen())
    carved = pathops.Path()
    pathops.difference([body], [union(carve)] if carve else [], carved.getPen())
    return union([carved, *fill, *diagonal])


# --------------------------------------------------------------------------
# Origin


def origin_shape(path, kind, x, y) -> None:
    i = ORIGIN_INSET
    x0, y0, x1, y1 = x + i, y + i, x + P - i, y + P - i
    s = x1 - x0
    if kind == "square":
        rect(path, x0, y0, x1, y1)
    elif kind == "quarter":
        # Square corner bottom left, arc bulging to the top right.
        path.moveTo(x0, y0)
        path.lineTo(x1, y0)
        arc_to(path, x0, y0, s, 0, math.pi / 2)
        path.close()
    elif kind == "bullet":
        # Flat top, straight sides, semicircle bottom reaching into the gap.
        r = s / 2
        straight = 0.65 * s
        path.moveTo(x0, y1)
        path.lineTo(x0, y1 - straight)
        arc_to(path, x0 + r, y1 - straight, r, math.pi, 2 * math.pi)
        path.lineTo(x1, y1)
        path.close()
    else:
        raise ValueError(kind)


_SIDES = {"N": (0, P), "E": (P, 0), "S": (0, -P), "W": (-P, 0)}
# Quarter turns (counter-clockwise) from the canonical orientation.
_BULLET_TURNS = {"S": 0, "E": 1, "N": 2, "W": 3}  # direction of the round end
_QUARTER_TURNS = {"NE": 0, "NW": 1, "SW": 2, "SE": 3}  # corner the arc faces


def _rotated(path: pathops.Path, cell, turns: int) -> pathops.Path:
    if turns % 4 == 0:
        return path
    cx, cy = cell[0] + R, cell[1] + R
    angle = turns * math.pi / 2
    c, s = round(math.cos(angle)), round(math.sin(angle))
    out = pathops.Path()
    path.draw(_TransformPen(out.getPen(), (c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)))
    return out


def origin_options(cells, cell):
    """Structure-aware choices: (kind, turns, weight)."""
    x, y = cell
    open_ = {d for d, (dx, dy) in _SIDES.items() if (x + dx, y + dy) not in cells}
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    options = [("square", 0, dict(ORIGIN_WEIGHTS)["square"])]
    bullets = [d for d in _SIDES if d in open_ and opposite[d] not in open_]
    quarters = [c for c in _QUARTER_TURNS if set(c) <= open_]
    for d in bullets:
        options.append(("bullet", _BULLET_TURNS[d], dict(ORIGIN_WEIGHTS)["bullet"] / len(bullets)))
    for c in quarters:
        options.append(("quarter", _QUARTER_TURNS[c], dict(ORIGIN_WEIGHTS)["quarter"] / len(quarters)))
    return options


def draw_origin(name, cells, overrides) -> pathops.Path:
    rng = seeded("Origin", name, "shapes")
    rules = overrides.get("Origin", {}).get(rule_name(name), {})
    fixed = rules.get("cells", {})
    kinds = [k for k, _ in ORIGIN_WEIGHTS]
    weights = [w for _, w in ORIGIN_WEIGHTS]
    shapes = Shapes()
    for cell in sorted(cells):
        if ORIGIN_MODE == "structure":
            options = origin_options(cells, cell)
            kind, turns, _ = rng.choices(options, [o[2] for o in options])[0]
        else:
            kind, turns = rng.choices(kinds, weights)[0], 0
        choice = fixed.get(cell_key(cell))
        if choice:
            kind, _, turn_name = str(choice).partition(":")
            turns = {**_BULLET_TURNS, **_QUARTER_TURNS}.get(turn_name, 0)
        shape = pathops.Path()
        origin_shape(shape, kind, *cell)
        shapes.append(_rotated(shape, cell, turns))
    return union(shapes)


DRAW = {"Metaball": draw_metaball, "Origin": draw_origin, "Skeleton": draw_skeleton}


def base_outline(style: str, grid: GlyphGrid, overrides: dict, variant: int = 0) -> pathops.Path:
    if not grid.cells:
        return pathops.Path()
    return DRAW[style](variant_name(grid.name, variant), grid.cells, overrides)


def glyph_outline(style, name, grids, overrides, cache, variant=0) -> pathops.Path:
    """Full outline of a glyph, decomposing components recursively."""
    key = (style, name, variant)
    if key in cache:
        return cache[key]
    grid = grids[name]
    parts = [base_outline(style, grid, overrides, variant)]
    for ref, transform in grid.components:
        sub = glyph_outline(style, ref, grids, overrides, cache, variant)
        moved = pathops.Path()
        sub.draw(_TransformPen(moved.getPen(), tuple(transform)))
        parts.append(moved)
    path = union(parts) if len(parts) > 1 else parts[0]
    cache[key] = path
    return path


def _part_outlines(style, name, grids, overrides, cache, variant=0):
    grid = grids[name]
    parts = [base_outline(style, grid, overrides, variant)] if grid.cells else []
    for ref, transform in grid.components:
        sub = glyph_outline(style, ref, grids, overrides, cache, variant)
        moved = pathops.Path()
        sub.draw(_TransformPen(moved.getPen(), tuple(transform)))
        parts.append(moved)
    return parts


def parts_overlap(style, name, grids, overrides, cache, variant=0) -> bool:
    """True when two parts of a composite glyph share any area."""
    parts = _part_outlines(style, name, grids, overrides, cache, variant)
    for i, a in enumerate(parts):
        for b in parts[i + 1 :]:
            common = pathops.Path()
            pathops.intersection([a], [b], common.getPen())
            if abs(common.area) > 1e-3:
                return True
    return False


class _TransformPen:
    def __init__(self, pen, t):
        self.pen, self.t = pen, t

    def _p(self, pt):
        a, b, c, d, e, f = self.t
        x, y = pt
        return (a * x + c * y + e, b * x + d * y + f)

    def moveTo(self, p):
        self.pen.moveTo(self._p(p))

    def lineTo(self, p):
        self.pen.lineTo(self._p(p))

    def curveTo(self, *pts):
        self.pen.curveTo(*[self._p(p) for p in pts])

    def qCurveTo(self, *pts):
        self.pen.qCurveTo(*[self._p(p) if p is not None else None for p in pts])

    def closePath(self):
        self.pen.closePath()

    def endPath(self):
        self.pen.endPath()
