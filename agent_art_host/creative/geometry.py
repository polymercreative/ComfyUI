"""SVG paths are source geometry; masks and fill trajectories are derived."""
import math
from xml.sax.saxutils import quoteattr

import numpy as np
import skia
from scipy.interpolate import CubicSpline
from shapely import affinity
from shapely.geometry import LineString, Polygon, GeometryCollection
from svgpathtools import parse_path


def coverage(path, width, height):
    parse_path(path)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><path d={quoteattr(path)} fill="white" fill-rule="evenodd"/></svg>'
    shape = skia.SVGDOM.MakeFromStream(skia.MemoryStream(svg.encode()))
    if shape is None:
        raise ValueError("Invalid SVG path")
    surface = skia.Surface(width, height)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    shape.render(surface.getCanvas())
    return surface.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)[..., 3].astype(np.float32) / 255


def region(path, tolerance=0.5):
    result = GeometryCollection()
    for contour in parse_path(path).continuous_subpaths():
        if not contour.isclosed():
            raise ValueError("Fill regions require closed contours")
        points = []
        for segment in contour:
            count = max(2, math.ceil(segment.length() / tolerance))
            points.extend((p.real, p.imag) for p in (segment.point(t) for t in np.linspace(0, 1, count)))
        polygon = Polygon(points)
        if not polygon.is_valid:
            raise ValueError("Fill contours must not self-intersect; resolve Boolean geometry first")
        result = result.symmetric_difference(polygon)
    return result


def fill_strokes(path, style):
    """Intersect seeded brush lanes with the actual region, including holes/islands."""
    rng = np.random.default_rng(style.get("seed", 1))
    angle = style.get("angle", -18)
    shape = affinity.rotate(region(path), -angle, origin=(0, 0))
    if shape.is_empty:
        return []
    x0, y0, x1, y1 = shape.bounds
    size = float(style.get("size", 18))
    spacing = float(style.get("spacing", size * 0.55))
    if size <= 0 or spacing <= 0:
        raise ValueError("Brush size and fill spacing must be positive")
    strokes = []
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    for y in np.arange(y0, y1 + spacing, spacing):
        offset = rng.uniform(-0.15, 0.15) * spacing
        pieces = shape.intersection(LineString([(x0 - size, y + offset), (x1 + size, y + offset)]))
        lines = list(pieces.geoms) if hasattr(pieces, "geoms") else [pieces]
        for line in lines:
            if line.geom_type != "LineString" or line.length < 0.1:
                continue
            start, end = np.array(line.coords[0]), np.array(line.coords[-1])
            points = []
            for t in np.linspace(0, 1, max(3, math.ceil(line.length / 55))):
                x, yy = start * (1 - t) + end * t
                yy += rng.uniform(-1, 1) * style.get("jitter", 2)
                points.append({"x": float(x * ca - yy * sa), "y": float(x * sa + yy * ca),
                               "size": size * float(rng.uniform(0.75, 1.2)),
                               "pressure": float(rng.uniform(0.5, 0.95)),
                               "flow": style.get("flow", 0.55), "opacity": 1,
                               "rotation": angle})
            strokes.append({"mode": "auto", "points": points,
                            "value_shift": float(rng.uniform(-1, 1) * style.get("variation", 0.12))})
    return strokes


def sample_stroke(stroke, step=1.5):
    points = stroke["points"]
    if len(points) < 2:
        raise ValueError("A stroke needs at least two control points")
    xy = np.array([[p["x"], p["y"]] for p in points], dtype=float)
    knots = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    if np.any(np.diff(knots) <= 0):
        raise ValueError("Consecutive stroke points must differ")
    mode = stroke.get("mode", "auto")
    defaults = {"size": 16, "pressure": 0.8, "flow": 1, "opacity": 1, "rotation": 0, "speed": 220}
    curve = CubicSpline(knots, xy, bc_type="natural") if mode == "auto" else None
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        handle_a = np.array(a.get("out", xy[i]))
        handle_b = np.array(b.get("in", xy[i + 1]))
        length = knots[i + 1] - knots[i]
        if mode == "cubic":
            length = np.linalg.norm(handle_a - xy[i]) + np.linalg.norm(handle_b - handle_a) + np.linalg.norm(xy[i + 1] - handle_b)
        count = max(2, math.ceil(length / step))
        for t in np.linspace(0, 1, count, endpoint=(i == len(points) - 2)):
            if mode == "auto":
                pos = curve(knots[i] + t * (knots[i + 1] - knots[i]))
            elif mode == "linear":
                pos = xy[i] * (1 - t) + xy[i + 1] * t
            elif mode == "cubic":
                pos = (1-t)**3*xy[i] + 3*(1-t)**2*t*handle_a + 3*(1-t)*t*t*handle_b + t**3*xy[i+1]
            elif mode == "quadratic":
                pos = (1-t)**2*xy[i] + 2*(1-t)*t*handle_a + t*t*xy[i+1]
            else:
                raise ValueError(f"Unknown interpolation: {mode}")
            sample = {k: a.get(k, v)*(1-t) + b.get(k, v)*t for k, v in defaults.items()}
            rotation_a = a.get("rotation", 0)
            sample["rotation"] = rotation_a + ((b.get("rotation", 0)-rotation_a+180)%360-180)*t
            yield float(pos[0]), float(pos[1]), sample
