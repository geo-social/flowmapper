"""Exporting maps: PNG, JPG, TIF, SVG and PDF on a white page (Export.js).

Like FlowMapper's export (``Export.js:renderMapToCanvas``), raster images start
from an opaque background (white, or the dark page colour in dark mode) so that
viewers never show transparent pixels as black; JPG and TIF are real JPEG and
TIFF files (Pillow, which matplotlib requires). ``dpi`` is relative to the
browser's 96 px per inch: ``dpi=96`` writes one pixel per FlowMapper pixel,
``dpi=192`` a 2x image, like an export from a Retina screen.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Union

__all__ = ["EXPORT_FORMATS", "save_figure", "save_map", "format_from_path"]

#: format -> (matplotlib format, file extension)
EXPORT_FORMATS = {"png": ("png", ".png"), "jpg": ("jpg", ".jpg"), "jpeg": ("jpg", ".jpg"),
                  "tif": ("tiff", ".tif"), "tiff": ("tiff", ".tif"), "svg": ("svg", ".svg"),
                  "pdf": ("pdf", ".pdf")}


def format_from_path(path: Union[str, Path], format: Optional[str] = None) -> str:
    """The export format of ``format`` or of the file extension (default png)."""
    if format:
        f = format.lower().lstrip(".")
    else:
        f = Path(str(path)).suffix.lower().lstrip(".") or "png"
    if f not in EXPORT_FORMATS:
        raise ValueError(f"unsupported export format {f!r}; use one of png, jpg, tif, svg, pdf")
    return f


def save_figure(fig, path: Union[str, Path, io.IOBase], format: Optional[str] = None, dpi: float = 96,
                background: str = "#ffffff", **kwargs: Any):
    """Save a rendered map figure with an opaque page background.

    JS: Export.js:exportRaster
    JS: Export.js:exportSVG
    """
    is_file = hasattr(path, "write")
    fmt = format_from_path("x." + format if (is_file and format) else ("x.png" if is_file else path), format)
    mfmt = EXPORT_FORMATS[fmt][0]
    opts = dict(format=mfmt, dpi=dpi, facecolor=background, edgecolor="none")
    if mfmt == "jpg":
        opts["pil_kwargs"] = {"quality": 95}
    if mfmt == "tiff":
        opts["pil_kwargs"] = {"dpi": (dpi, dpi)}
    opts.update(kwargs)
    old = fig.get_facecolor()
    fig.set_facecolor(background)
    try:
        fig.savefig(path, **opts)
    finally:
        fig.set_facecolor(old)
    return path if is_file else Path(path)


def save_map(project, path: Union[str, Path], format: Optional[str] = None, *, dpi: float = 96,
             close: bool = True, **render_kwargs: Any) -> Path:
    """Render ``project`` and write it to ``path`` (PNG, JPG, TIF, SVG or PDF).

    ``render_kwargs`` go to :func:`flowmapper_org.render.render` (``width``,
    ``height``, ``extent``, ``scale``, ``dark``, ``legend`` ...).
    """
    from .core import render
    res = render(project, dpi=dpi, **render_kwargs)
    try:
        return res.save(path, format=format, dpi=dpi)
    finally:
        if close:
            res.close()
