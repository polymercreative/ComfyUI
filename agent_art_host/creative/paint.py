"""Thin libmypaint binding: native brush dynamics, dabs and tiled compositing."""
import colorsys
import ctypes as C
import ctypes.util
import math
import os
from pathlib import Path

import numpy as np

from .geometry import coverage, fill_strokes, sample_stroke


class TileRequest(C.Structure):
    _fields_ = [("tx", C.c_int), ("ty", C.c_int), ("readonly", C.c_int),
                ("buffer", C.POINTER(C.c_uint16)), ("context", C.c_void_p),
                ("thread_id", C.c_int), ("mipmap_level", C.c_int)]


def library_path():
    configured = os.environ.get("AGENT_ART_MYPAINT")
    if configured:
        return Path(configured)
    if os.name == "nt":
        installed = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Krita (x64)/bin/libmypaint.dll"
        if installed.is_file():
            return installed
    found = ctypes.util.find_library("mypaint")
    if not found:
        raise RuntimeError("Install libmypaint or set AGENT_ART_MYPAINT to its shared library")
    return Path(found)


class NativePaint:
    def __init__(self, width, height):
        path = library_path()
        self.directory = os.add_dll_directory(str(path.parent)) if os.name == "nt" else None
        self.lib = C.CDLL(str(path))
        p, i, f = C.c_void_p, C.c_int, C.c_float
        signatures = {
            "fixed_tiled_surface_new": (p, [i, i]), "surface_unref": (None, [p]),
            "tile_request_init": (None, [C.POINTER(TileRequest), i, i, i, i]),
            "tiled_surface_tile_request_start": (None, [p, C.POINTER(TileRequest)]),
            "tiled_surface_tile_request_end": (None, [p, C.POINTER(TileRequest)]),
            "surface_begin_atomic": (None, [p]), "surface_end_atomic": (None, [p, p]),
            "brush_new": (p, []), "brush_unref": (None, [p]),
            "brush_from_defaults": (None, [p]), "brush_from_string": (i, [p, C.c_char_p]),
            "brush_setting_from_cname": (i, [C.c_char_p]), "brush_set_base_value": (None, [p, i, f]),
            "brush_get_base_value": (f, [p, i]),
            "brush_reset": (None, [p]), "brush_new_stroke": (None, [p]),
            "brush_stroke_to": (i, [p, p, f, f, f, f, f, C.c_double]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.lib, "mypaint_" + name)
            function.restype, function.argtypes = result, args
            setattr(self, name, function)
        self.width, self.height = width, height
        self.surface = self.fixed_tiled_surface_new(width, height)
        if not self.surface:
            raise MemoryError("libmypaint could not allocate the surface")
        self.tiles = []
        for ty in range(math.ceil(height / 64)):
            for tx in range(math.ceil(width / 64)):
                request = TileRequest()
                self.tile_request_init(C.byref(request), 0, tx, ty, 0)
                self.tiled_surface_tile_request_start(self.surface, C.byref(request))
                tile = np.ctypeslib.as_array(request.buffer, shape=(64*64*4,)).reshape(64, 64, 4)
                tile.fill(0)
                self.tiled_surface_tile_request_end(self.surface, C.byref(request))
                self.tiles.append((tx, ty))

    def close(self):
        if self.surface:
            self.surface_unref(self.surface)
            self.surface = None
        if self.directory:
            self.directory.close()
            self.directory = None

    def render(self, strokes, preset, color, check=lambda: None):
        brush = self.brush_new()
        try:
            self.brush_from_defaults(brush)
            if preset and not self.brush_from_string(brush, preset.encode("utf-8")):
                raise ValueError("libmypaint rejected the native brush preset")
            native_opacity = self.brush_get_base_value(brush, self.brush_setting_from_cname(b"opaque"))
            def setting(name, value):
                key = self.brush_setting_from_cname(name.encode())
                if key < 0:
                    raise ValueError(f"Unsupported libmypaint setting: {name}")
                self.brush_set_base_value(brush, key, value)
            for stroke in strokes:
                check()
                self.brush_reset(brush)
                self.brush_new_stroke(brush)
                rgb = np.clip(np.array(stroke.get("color", color)) + stroke.get("value_shift", 0), 0, 1)
                for name, value in zip(("color_h", "color_s", "color_v"), colorsys.rgb_to_hsv(*rgb)):
                    setting(name, value)
                self.surface_begin_atomic(self.surface)
                try:
                    previous = None
                    for index, (x, y, attributes) in enumerate(sample_stroke(stroke)):
                        if index % 64 == 0:
                            check()
                        if attributes["size"] <= 0 or attributes["speed"] <= 0:
                            raise ValueError("Stroke size and speed must be positive")
                        setting("radius_logarithmic", math.log(attributes["size"] / 2))
                        setting("opaque", native_opacity * attributes["flow"] * attributes["opacity"])
                        setting("elliptical_dab_angle", attributes["rotation"])
                        if previous is None:
                            self.brush_stroke_to(brush, self.surface, x, y, 0, 0, 0, 1)
                            dt = 0.01
                        else:
                            dt = max(0.0001, math.hypot(x-previous[0], y-previous[1])/attributes["speed"])
                        self.brush_stroke_to(brush, self.surface, x, y, attributes["pressure"], 0, 0, dt)
                        previous = (x, y)
                finally:
                    roi = (C.c_int * 4)()
                    self.surface_end_atomic(self.surface, C.byref(roi))
        finally:
            self.brush_unref(brush)

    def pixels(self):
        output = np.zeros((self.height, self.width, 4), np.float32)
        for tx, ty in self.tiles:
            request = TileRequest()
            self.tile_request_init(C.byref(request), 0, tx, ty, 1)
            self.tiled_surface_tile_request_start(self.surface, C.byref(request))
            try:
                tile = np.ctypeslib.as_array(request.buffer, shape=(64*64*4,)).reshape(64, 64, 4)
                h, w = min(64, self.height-ty*64), min(64, self.width-tx*64)
                output[ty*64:ty*64+h, tx*64:tx*64+w] = tile[:h, :w] / 32768.0
            finally:
                self.tiled_surface_tile_request_end(self.surface, C.byref(request))
        np.divide(output[..., :3], output[..., 3:], out=output[..., :3], where=output[..., 3:] > 0)
        return output


def paint_region(path, width, height, style, preset, check=lambda: None):
    mask = coverage(path, width, height)
    strokes = fill_strokes(path, style) if style.get("fill", True) else []
    strokes.extend(style.get("strokes", []))
    surface = NativePaint(width, height)
    try:
        surface.render(strokes, preset, style.get("color", [0.2, 0.5, 0.5]), check)
        painted = surface.pixels()
    finally:
        surface.close()
    base_alpha = style.get("base", 0.4 if style.get("fill", True) else 0)
    alpha = painted[..., 3:] + base_alpha * (1-painted[..., 3:])
    rgb = painted[..., :3]*painted[..., 3:] + np.array(style.get("color", [0.2, 0.5, 0.5]))*base_alpha*(1-painted[..., 3:])
    np.divide(rgb, alpha, out=rgb, where=alpha > 0)
    output = np.concatenate((rgb, alpha*mask[..., None]), axis=2).astype(np.float32)
    output[output[..., 3] == 0, :3] = 0
    output.flags.writeable = False
    return output, mask, strokes
