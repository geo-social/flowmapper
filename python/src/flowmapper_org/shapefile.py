"""Dependency-free ESRI shapefile reader, a port of FlowMapper's ``ShapefileReader.js``.

FlowMapper converts a shapefile to GeoJSON in the browser before anything else
happens; this module produces the *same* GeoJSON in Python:

>>> from flowmapper_org.shapefile import read_shapefile
>>> gj = read_shapefile("counties.zip")               # doctest: +SKIP
>>> gj = read_shapefile("counties.shp")               # siblings .shx/.dbf/.prj/.cpg found automatically
>>> gj = read_shapefile(["a.shp", "a.dbf", "a.prj"])  # exactly like selecting files in the browser

What is reproduced from the JavaScript, deliberately including its quirks:

* zip archives are read from the central directory (stored or deflated entries);
  folders, ``__MACOSX/`` and ``._*`` entries are ignored; when the archive holds
  several shapefiles only the first is read (``_shapefileInfo["note"]`` says so);
* records are read at the offsets of the ``.shx`` index when it is present and
  valid, otherwise one after another;
* polygon rings are grouped by orientation (clockwise = outer ring) and each hole
  is given to the first outer ring that contains its first vertex
  (``ringsToPolygon``); rings with fewer than 4 points are dropped;
* ``.dbf`` text is decoded with the ``.cpg`` encoding, else the LDID byte, else
  per field as UTF-8 with a Windows-1252 fallback; numbers follow JavaScript ``+v``;
* coordinates are reprojected to WGS84 longitude/latitude from the ``.prj`` with
  proj4js semantics (see :func:`make_reprojector`);
* the error messages are the ones the web application shows.

The returned FeatureCollection carries ``_shapefileInfo`` (``hasDbf``, ``hasPrj``,
``hasShx``, ``records``, optional ``note``) exactly like ``ShapefileReader.read``.
"""
from __future__ import annotations

import codecs
import json
import math
import re
import struct
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

PathLike = Union[str, Path]

__all__ = ["ShapefileError", "read_shapefile", "read_files", "from_parts", "parse_shp", "parse_dbf",
           "read_zip", "rings_to_polygon", "ring_area", "point_in_ring", "shx_offsets",
           "make_reprojector", "is_shapefile_selection", "SHAPEFILE_EXTENSIONS"]

SHAPEFILE_EXTENSIONS = ("zip", "shp", "dbf", "shx", "prj", "cpg")

# V8's message for DataView reads outside the buffer (what the browser shows for
# truncated files).
DATAVIEW_MSG = "Offset is outside the bounds of the DataView"

MSG_ZIP_DAMAGED = "The .zip file could not be read (it may be damaged)."
MSG_ZIP_METHOD = "The .zip uses an unsupported compression method."
MSG_ZIP_NO_SHP = "The .zip file does not contain a .shp file."
MSG_INVALID_SHP = "The .shp file is not a valid shapefile."
MSG_DAMAGED_SHP = ("The .shp file is damaged (a record runs past the end of the file). Please re-export the "
                   "shapefile, or use GeoJSON.")
MSG_NOT_LONLAT = ("The coordinates are not longitude/latitude and no .prj file was provided. Please include "
                  "the .prj file (select it together with the .shp and .dbf, or use a .zip).")


class ShapefileError(ValueError):
    """A shapefile could not be read; the message is the one FlowMapper.org shows."""


# ====================================================================== JS value helpers
# (shared with flowmapper_org.regions)

# ECMAScript WhiteSpace + LineTerminator (String.prototype.trim, Number(string)).
_JS_WS = ("\u0009\u000a\u000b\u000c\u000d         "
          "         　﻿")
_JS_DEC = re.compile(r"^[+-]?(?:(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|Infinity)$")
_JS_INDEX = re.compile(r"^(?:0|[1-9]\d*)$")


def js_trim(s: str) -> str:
    """``String.prototype.trim``."""
    return s.strip(_JS_WS)


def js_str_to_number(s: str) -> float:
    """``Number(string)`` / unary ``+`` on a string (strict: ``'1_0'`` is NaN, ``'0x1A'`` is 26)."""
    t = js_trim(s)
    if t == "":
        return 0.0
    if _JS_DEC.match(t):
        if t.endswith("Infinity"):
            return -math.inf if t[0] == "-" else math.inf
        return float(t)
    low = t[:2].lower()
    base = {"0x": 16, "0o": 8, "0b": 2}.get(low)
    if base is not None and len(t) > 2:
        try:
            return float(int(t[2:], base))
        except ValueError:
            return math.nan
    return math.nan


def js_to_number(v: Any) -> float:
    """Unary ``+v`` for JSON-like values (None means ``null``: 0)."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return js_str_to_number(v)
    return js_str_to_number(js_string(v))


def js_string(v: Any) -> str:
    """``String(v)`` for JSON-like values."""
    from .data import js_number_to_string
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return js_number_to_string(float(v)) if abs(v) >= 2 ** 53 else str(v)
    if isinstance(v, float):
        return js_number_to_string(v)
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return ",".join("" if x is None else js_string(x) for x in v)
    if isinstance(v, dict):
        return "[object Object]"
    return str(v)


def js_object_keys(keys: Iterable[str]) -> List[str]:
    """Property order of a JavaScript object: array-index keys ascending, then insertion order."""
    keys = list(keys)
    idx = [k for k in keys if isinstance(k, str) and _JS_INDEX.match(k) and int(k) < 4294967295]
    if not idx:
        return keys
    sidx = set(idx)
    return sorted(idx, key=int) + [k for k in keys if k not in sidx]


def js_number_value(x: float) -> Union[int, float]:
    """A JS number as the JSON value JavaScript would write (integral -> int)."""
    if isinstance(x, float) and math.isfinite(x) and x == int(x) and abs(x) < 2 ** 53:
        return int(x)
    return x


def _utf16_len(s: str) -> int:
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)


def _utf16_slice(s: str, start: int, end: Optional[int] = None) -> str:
    if all(ord(c) <= 0xFFFF for c in s):
        return s[start:end]
    u = s.encode("utf-16-le", "surrogatepass")
    e = None if end is None else end * 2
    return u[start * 2:e].decode("utf-16-le", "surrogatepass")


# ====================================================================== text decoding (WHATWG)
_CP1252_HIGH = {0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E, 0x85: 0x2026, 0x86: 0x2020,
                0x87: 0x2021, 0x88: 0x02C6, 0x89: 0x2030, 0x8A: 0x0160, 0x8B: 0x2039, 0x8C: 0x0152,
                0x8E: 0x017D, 0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201C, 0x94: 0x201D, 0x95: 0x2022,
                0x96: 0x2013, 0x97: 0x2014, 0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161, 0x9B: 0x203A,
                0x9C: 0x0153, 0x9E: 0x017E, 0x9F: 0x0178}
_CP1252_TABLE = "".join(chr(_CP1252_HIGH.get(b, b)) for b in range(256))


class _Decoder:
    """Minimal ``TextDecoder``: WHATWG semantics for UTF-8 and Windows-1252."""

    def __init__(self, label: str, fatal: bool = False):
        self.label = label
        self.fatal = fatal

    def decode(self, b: bytes) -> str:
        if self.label == "utf-8":
            s = bytes(b).decode("utf-8", "strict" if self.fatal else "replace")
            return s[1:] if s.startswith("﻿") else s   # TextDecoder drops a leading BOM
        if self.label == "windows-1252":
            return bytes(b).decode("latin-1").translate(_CP1252_TRANS)
        if self.label in _SINGLE_BYTE:
            # WHATWG single-byte indexes map the bytes Python's codec lacks to C1 controls
            return bytes(b).decode(self.label, "flowmapper-c1")
        return bytes(b).decode(self.label, "strict" if self.fatal else "replace")


_CP1252_TRANS = {i: ord(_CP1252_TABLE[i]) for i in range(0x80, 0xA0)}


def _c1_errors(err: UnicodeDecodeError):
    bad = err.object[err.start:err.end]
    return ("".join(chr(x) if 0x80 <= x < 0xA0 else "�" for x in bad), err.end)


codecs.register_error("flowmapper-c1", _c1_errors)
_SINGLE_BYTE = {"cp1250", "cp1251", "cp1253", "cp1254", "cp1255", "cp1256", "cp1257", "cp1258", "koi8_r"}

# Encoding labels the browser maps differently from Python's codec of the same name.
_WHATWG_ALIASES = {"iso-8859-1": "windows-1252", "latin1": "windows-1252", "latin-1": "windows-1252",
                   "ascii": "windows-1252", "us-ascii": "windows-1252", "windows-1252": "windows-1252",
                   "cp1252": "windows-1252", "utf-8": "utf-8", "utf8": "utf-8", "gbk": "gb18030",
                   "gb2312": "gb18030", "gb18030": "gb18030", "shift_jis": "cp932", "big5": "big5hkscs",
                   "windows-1250": "cp1250", "windows-1251": "cp1251"}


def _text_decoder(label: str) -> Optional[_Decoder]:
    """``new TextDecoder(label)``; None when the browser would throw (unknown label)."""
    lab = label.strip().lower()
    if lab in _WHATWG_ALIASES:
        return _Decoder(_WHATWG_ALIASES[lab])
    try:
        name = codecs.lookup(lab).name
    except LookupError:
        return None
    if name in ("utf-8",):
        return _Decoder("utf-8")
    if name in ("cp1252", "latin-1", "iso8859-1", "ascii"):
        return _Decoder("windows-1252")
    return _Decoder(name)


def _utf8_text(b: Optional[bytes]) -> Optional[str]:
    """``File.text()`` / ``new TextDecoder("utf-8").decode``. JS: ShapefileReader.js:textOf"""
    return None if b is None else _Decoder("utf-8").decode(b)


# ====================================================================== DataView-like reads
class _View:
    __slots__ = ("b", "n")

    def __init__(self, b: bytes):
        self.b = b
        self.n = len(b)

    def _chk(self, off: int, size: int) -> None:
        if off < 0 or off + size > self.n:
            raise ShapefileError(DATAVIEW_MSG)

    def i32be(self, off: int) -> int:
        self._chk(off, 4)
        return struct.unpack_from(">i", self.b, off)[0]

    def i32le(self, off: int) -> int:
        self._chk(off, 4)
        return struct.unpack_from("<i", self.b, off)[0]

    def u32le(self, off: int) -> int:
        self._chk(off, 4)
        return struct.unpack_from("<I", self.b, off)[0]

    def u16le(self, off: int) -> int:
        self._chk(off, 2)
        return struct.unpack_from("<H", self.b, off)[0]

    def f64le(self, off: int) -> float:
        self._chk(off, 8)
        return struct.unpack_from("<d", self.b, off)[0]

    def points(self, off: int, n: int) -> List[List[float]]:
        """n consecutive (x, y) little-endian doubles starting at ``off``."""
        if n <= 0:
            return []
        self._chk(off, 16 * n)
        v = struct.unpack_from(f"<{2 * n}d", self.b, off)
        return [[v[i], v[i + 1]] for i in range(0, 2 * n, 2)]


# ====================================================================== zip
def _ext(name: str) -> str:
    """Lower-case extension. JS: ShapefileReader.js:ext"""
    m = re.search(r"\.([^./\\]+)$", name or "")
    return m.group(1).lower() if m else ""


def _base_name(name: str) -> str:
    """File name without folder and extension, lower case. JS: ShapefileReader.js:baseName"""
    s = re.sub(r"^.*[/\\]", "", name or "")
    return re.sub(r"\.[^.]+$", "", s).lower()


def _inflate_raw(data: bytes) -> bytes:
    """Raw deflate (zlib instead of the browser's DecompressionStream). JS: ShapefileReader.js:inflateRaw"""
    d = zlib.decompressobj(-15)
    try:
        out = d.decompress(data) + d.flush()
    except zlib.error as e:
        raise ShapefileError(MSG_ZIP_DAMAGED) from e
    if not d.eof:
        raise ShapefileError(MSG_ZIP_DAMAGED)
    return out


def read_zip(buffer: bytes) -> Dict[str, bytes]:
    """Entries of a zip archive (name -> bytes), as ``readZip`` returns them.

    JS: ShapefileReader.js:readZip
    """
    v = _View(buffer)
    n = len(buffer)
    eocd = -1
    i = n - 22
    lo = max(0, n - 65557)
    while i >= lo:
        if v.u32le(i) == 0x06054B50:
            eocd = i
            break
        i -= 1
    if eocd < 0:
        raise ShapefileError(MSG_ZIP_DAMAGED)
    count = v.u16le(eocd + 10)
    offset = v.u32le(eocd + 16)
    entries = []
    for _ in range(count):
        if v.u32le(offset) != 0x02014B50:
            break
        method = v.u16le(offset + 10)
        comp_size = v.u32le(offset + 20)
        name_len = v.u16le(offset + 28)
        extra_len = v.u16le(offset + 30)
        comment_len = v.u16le(offset + 32)
        local_offset = v.u32le(offset + 42)
        name = _Decoder("utf-8").decode(buffer[offset + 46:offset + 46 + name_len])
        entries.append((name, method, comp_size, local_offset))
        offset += 46 + name_len + extra_len + comment_len
    files: Dict[str, bytes] = {}
    for name, method, comp_size, lo_ in entries:
        if name.endswith("/") or re.search(r"(^|/)__MACOSX/", name) or re.search(r"(^|/)\._", name):
            continue
        start = lo_ + 30 + v.u16le(lo_ + 26) + v.u16le(lo_ + 28)
        data = buffer[start:start + comp_size]
        if method == 0:
            files[name] = bytes(data)
        elif method == 8:
            files[name] = _inflate_raw(data)
        else:
            raise ShapefileError(MSG_ZIP_METHOD)
    return files


# ====================================================================== shp
def ring_area(ring: Sequence[Sequence[float]]) -> float:
    """Signed area (shoelace, assumes a closed ring); negative for clockwise rings.

    JS: ShapefileReader.js:ringArea
    """
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return a / 2


def point_in_ring(pt: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    """Even-odd ray casting.

    JS: ShapefileReader.js:pointInRing
    """
    inside = False
    n = len(ring)
    j = n - 1
    px, py = pt[0], pt[1]
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def rings_to_polygon(rings: Sequence[list]) -> dict:
    """Group shapefile rings into a Polygon / MultiPolygon.

    Clockwise rings (area <= 0) are outer rings, the others holes. Rings with
    fewer than 4 points are dropped. When there is no clockwise ring, all rings
    are outer rings. A hole goes to the first outer ring containing its first
    vertex; a hole inside no outer ring becomes its own polygon (reversed).
    Holes keep their (counter-clockwise) orientation.

    JS: ShapefileReader.js:ringsToPolygon
    """
    outers: list = []
    holes: list = []
    for r in rings:
        if len(r) < 4:
            continue
        (outers if ring_area(r) <= 0 else holes).append(r)
    if not outers:
        outers, holes = holes, []
    polys = [[o] for o in outers]
    for h in holes:
        owner = None
        for i, o in enumerate(outers):
            if point_in_ring(h[0], o):
                owner = polys[i]
                break
        if owner is not None:
            owner.append(h)
        else:
            polys.append([h[::-1]])
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def shx_offsets(shx: Optional[bytes]) -> Optional[List[int]]:
    """Record offsets (bytes) from a ``.shx`` index; None when missing or invalid.

    JS: ShapefileReader.js:shxOffsets
    """
    if shx is None or len(shx) < 100:
        return None
    v = _View(shx)
    if v.i32be(0) != 9994:
        return None
    return [v.i32be(p) * 2 for p in range(100, len(shx) - 7, 8)]


def parse_shp(shp: bytes, shx: Optional[bytes] = None) -> List[Optional[dict]]:
    """Geometries of a ``.shp`` file (None for null / unsupported shapes), in record order.

    Point, MultiPoint, PolyLine and Polygon records (and their Z / M variants,
    whose Z and M values are ignored) are read; other types give None.

    JS: ShapefileReader.js:parseShp
    """
    shp = bytes(shp)
    v = _View(shp)
    n = len(shp)
    if n < 100 or v.i32be(0) != 9994:
        raise ShapefileError(MSG_INVALID_SHP)
    file_len = v.i32be(24) * 2
    end = min(file_len, n)
    pos = 100
    geoms: List[Optional[dict]] = []
    offsets = shx_offsets(shx)
    idx = 0
    while (idx < len(offsets)) if offsets is not None else (pos + 8 <= end):
        if offsets is not None:
            pos = offsets[idx]
            idx += 1
            if pos < 100 or pos + 8 > n:
                break
        content_len = v.i32be(pos + 4) * 2
        c = pos + 8
        if c + 4 > n:
            break
        # a zero or negative record length (FlowMapper used to loop forever)
        if not content_len >= 4:
            raise ShapefileError(MSG_DAMAGED_SHP)
        rec_end = min(c + content_len, n)
        typ = v.i32le(c)
        geom: Optional[dict] = None
        if typ in (1, 11, 21):
            if c + 20 > rec_end:
                raise ShapefileError(MSG_DAMAGED_SHP)
            geom = {"type": "Point", "coordinates": [v.f64le(c + 4), v.f64le(c + 12)]}
        elif typ in (8, 18, 28):
            np_ = v.i32le(c + 36) if c + 40 <= rec_end else -1
            if np_ < 0 or c + 40 + np_ * 16 > rec_end:
                raise ShapefileError(MSG_DAMAGED_SHP)
            geom = {"type": "MultiPoint", "coordinates": v.points(c + 40, np_)}
        elif typ in (3, 13, 23, 5, 15, 25):
            if c + 44 > rec_end:
                raise ShapefileError(MSG_DAMAGED_SHP)
            num_parts = v.i32le(c + 36)
            num_points = v.i32le(c + 40)
            parts_at = c + 44
            pts_at = parts_at + num_parts * 4
            if num_parts < 0 or num_points < 0 or pts_at + num_points * 16 > rec_end:
                raise ShapefileError(MSG_DAMAGED_SHP)
            parts = [max(0, min(num_points, v.i32le(parts_at + p * 4))) for p in range(num_parts)]
            parts.append(num_points)
            rings = []
            for q in range(max(num_parts, 0)):
                a, b = parts[q], parts[q + 1]
                rings.append(v.points(pts_at + a * 16, b - a) if b > a else [])
            if typ in (3, 13, 23):
                geom = ({"type": "LineString", "coordinates": rings[0]} if len(rings) == 1
                        else {"type": "MultiLineString", "coordinates": rings})
            else:
                geom = rings_to_polygon(rings)
        geoms.append(geom)
        pos = c + content_len
    return geoms


# ====================================================================== dbf
_CPG_MAP = {"65001": "utf-8", "utf8": "utf-8", "utf-8": "utf-8", "1252": "windows-1252",
            "ansi 1252": "windows-1252", "88591": "iso-8859-1", "8859_1": "iso-8859-1",
            "iso-8859-1": "iso-8859-1", "1250": "windows-1250", "1251": "windows-1251", "936": "gbk",
            "gbk": "gbk", "gb2312": "gbk", "big5": "big5", "950": "big5", "932": "shift_jis",
            "shift_jis": "shift_jis"}


def make_decoder(cpg_text: Optional[str], ldid: Optional[int]) -> Optional[_Decoder]:
    """Decoder chosen from the ``.cpg`` text, else the LDID byte; None = guess per field.

    JS: ShapefileReader.js:makeDecoder
    """
    label = js_trim(cpg_text or "").lower()
    if label and label in _CPG_MAP:
        return _text_decoder(_CPG_MAP[label])
    if label:
        d = _text_decoder(label)
        if d is not None:
            return d
    if ldid in (0x57, 0x03):
        return _Decoder("windows-1252")
    if ldid == 0x4D:
        return _text_decoder("gbk")
    return None


def parse_dbf(dbf: bytes, cpg_text: Optional[str] = None) -> List[dict]:
    """Attribute rows of a ``.dbf`` file (one dict per record, deleted records included).

    N/F fields become numbers (None when blank or not numeric), L fields
    True/False/None, D fields ``YYYY-MM-DD`` when 8 characters long; everything
    else is trimmed text.

    JS: ShapefileReader.js:parseDbf
    """
    b = bytes(dbf)
    v = _View(b)
    num_records = v.u32le(4)
    header_len = v.u16le(8)
    record_len = v.u16le(10)
    decoder = make_decoder(cpg_text, b[29] if len(b) > 29 else None)
    utf8 = _Decoder("utf-8", fatal=True)
    latin = _Decoder("windows-1252")

    def decode(u8: bytes) -> str:
        if decoder is not None:
            return decoder.decode(u8)
        try:
            return utf8.decode(u8)
        except UnicodeDecodeError:
            return latin.decode(u8)

    fields = []
    off = 32
    # (past the end of a truncated header no record can be read, so stopping there is equivalent)
    while off < header_len - 1 and off < len(b) and b[off] != 0x0D:
        name_bytes = b[off:off + 11]
        zero = name_bytes.find(b"\x00")
        fields.append((js_trim(decode(name_bytes[:zero] if zero >= 0 else name_bytes)),
                       chr(b[off + 11]) if off + 11 < len(b) else "\x00",
                       b[off + 16] if off + 16 < len(b) else 0))
        off += 32
    rows = []
    for r in range(num_records):
        rs = header_len + r * record_len
        if rs + record_len > len(b):
            break
        props: dict = {}
        fo = rs + 1   # first byte = deletion flag
        for name, typ, length in fields:
            raw = js_trim(decode(b[fo:fo + length]).replace("\x00", ""))
            if typ in ("N", "F"):
                num = js_str_to_number(raw)
                val: Any = None if raw == "" or math.isnan(num) else js_number_value(num)
            elif typ == "L":
                val = True if re.fullmatch(r"[YyTt]", raw) else (False if re.fullmatch(r"[NnFf]", raw) else None)
            elif typ == "D":
                val = (_utf16_slice(raw, 0, 4) + "-" + _utf16_slice(raw, 4, 6) + "-" + _utf16_slice(raw, 6)
                       if _utf16_len(raw) == 8 else raw)
            else:
                val = raw
            props[name] = val
            fo += length
        rows.append(props)
    return rows


# ====================================================================== projection
# proj4js datum table (proj4.js "Datum" definitions) used for WKT datum codes.
_P4_DATUMS = {
    "wgs84": "0,0,0", "ch1903": "674.374,15.056,405.346", "ggrs87": "-199.87,74.79,246.62", "nad83": "0,0,0",
    "nad27": None, "potsdam": "598.1,73.7,418.2,0.202,0.045,-2.455,6.7", "carthage": "-263.0,6.0,431.0",
    "hermannskogel": "577.326,90.129,463.919,5.137,1.474,5.297,2.4232",
    "militargeographische_institut": "577.326,90.129,463.919,5.137,1.474,5.297,2.4232",
    "osni52": "482.530,-130.596,564.557,-1.042,-0.214,-0.631,8.15",
    "ire65": "482.530,-130.596,564.557,-1.042,-0.214,-0.631,8.15", "rassadiran": "-133.63,-157.5,-158.62",
    "nzgd49": "59.47,-5.04,187.44,0.47,-0.1,1.024,-4.5993",
    "osgb36": "446.448,-125.157,542.060,0.1502,0.2470,0.8421,-20.4894", "s_jtsk": "589,76,480",
    "beduaram": "-106,-87,188", "gunung_segara": "-403,684,41",
    "rnb72": "106.869,-52.2978,103.724,-0.33657,0.456955,-1.84218,1",
}
_P4_NORM = re.compile(r"[\s_\-/()]")
_SEC_TO_RAD = 4.84813681109536e-06
_D2R = 0.017453292519943295
_R2D = 57.29577951308232
_HALF_PI = math.pi / 2
_WGS84_A = 6378137.0
_WGS84_RF = 298.257223563
_DT_WGS84, _DT_3PARAM, _DT_7PARAM = "wgs84", "3param", "7param"


def _wkt_datum(wkt: str) -> dict:
    """Datum code / ellipsoid / TOWGS84 as proj4js's WKT parser derives them."""
    def node(text: str, key: str) -> Optional[str]:
        m = re.search(r'\b' + key + r'\s*[\[(]', text, re.I)
        if not m:
            return None
        depth, i = 0, m.end() - 1
        while i < len(text):
            ch = text[i]
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
                if depth == 0:
                    return text[m.end():i]
            i += 1
        return text[m.end():]

    def name_of(body: Optional[str]) -> str:
        if body is None:
            return ""
        m = re.match(r'\s*"([^"]*)"', body)
        return m.group(1) if m else ""

    geog = wkt if re.match(r"\s*GEOGCS", wkt, re.I) else (node(wkt, "GEOGCS") or "")
    datum = node(geog, "DATUM")
    code = (name_of(datum) if datum is not None else name_of(geog)).lower()
    if code[:2] == "d_":
        code = code[2:]
    if code in ("new_zealand_geodetic_datum_1949", "new_zealand_1949"):
        code = "nzgd49"
    if code in ("wgs_1984", "world_geodetic_system_1984"):
        code = "wgs84"
    if code[-6:] == "_ferro":
        code = code[:-6]
    if code[-8:] == "_jakarta":
        code = code[:-8]
    if "belge" in code:
        code = "rnb72"
    a = rf = None
    params = None
    if datum is not None:
        sph = node(datum, "SPHEROID") or node(datum, "ELLIPSOID")
        if sph is not None:
            nums = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", re.sub(r'"[^"]*"', "", sph))
            if len(nums) >= 2:
                a, rf = float(nums[0]), float(nums[1])
        tw = node(datum, "TOWGS84")
        if tw is not None:
            params = [x.strip() for x in tw.split(",")]
    if "osgb_1936" in code:
        code = "osgb36"
    if "osni_1952" in code:
        code = "osni52"
    if "tm65" in code or "geodetic_datum_of_1965" in code:
        code = "ire65"
    if code == "ch1903+":
        code = "ch1903"
    if "israel" in code:
        code = "isr93"
    return {"code": code, "a": a, "rf": rf, "params": params}


def _p4_datum(code: Optional[str], params: Optional[list], a: float, rf: Optional[float]) -> dict:
    """proj4js ``datum()`` + ``eccentricity()`` for a WKT CRS."""
    if params is None and code:
        key = _P4_NORM.sub("", code.lower())
        for k, tw in _P4_DATUMS.items():
            if _P4_NORM.sub("", k) == key:
                params = tw.split(",") if tw else None
                break
    b = (1 - 1 / rf) * a if rf else a
    if rf == 0 or abs(a - b) < 1e-10:
        b = a
    es = (a * a - b * b) / (a * a)
    d = {"type": _DT_WGS84, "params": None, "a": a, "b": b, "es": es}
    if params:
        p = []
        for x in params:
            m = re.match(r"\s*[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", str(x))
            p.append(float(m.group(0)) if m else math.nan)
        d["params"] = p
        if not (p[0] == 0 and p[1] == 0 and p[2] == 0):
            d["type"] = _DT_3PARAM
        if len(p) > 3 and not (p[3] == 0 and p[4] == 0 and p[5] == 0 and p[6] == 0):
            d["type"] = _DT_7PARAM
            p[3] *= _SEC_TO_RAD
            p[4] *= _SEC_TO_RAD
            p[5] *= _SEC_TO_RAD
            p[6] = p[6] / 1e6 + 1
    return d


_WGS84_DATUM = _p4_datum("WGS84", None, _WGS84_A, _WGS84_RF)


def _same_datum(s: dict, d: dict) -> bool:
    if s["type"] != d["type"] or s["a"] != d["a"] or abs(s["es"] - d["es"]) > 5e-11:
        return False
    if s["type"] == _DT_3PARAM:
        return s["params"][:3] == d["params"][:3]
    if s["type"] == _DT_7PARAM:
        return s["params"][:7] == d["params"][:7]
    return True


def _geodetic_to_geocentric(x: float, y: float, z: float, es: float, a: float):
    if -_HALF_PI > y > -1.001 * _HALF_PI:
        y = -_HALF_PI
    elif _HALF_PI < y < 1.001 * _HALF_PI:
        y = _HALF_PI
    elif y < -_HALF_PI:
        return (-math.inf, -math.inf, z)
    elif y > _HALF_PI:
        return (math.inf, math.inf, z)
    if x > math.pi:
        x -= 2 * math.pi
    sl = math.sin(y)
    cl = math.cos(y)
    s2 = sl * sl
    rn = a / math.sqrt(1 - es * s2)
    return ((rn + z) * cl * math.cos(x), (rn + z) * cl * math.sin(x), (rn * (1 - es) + z) * sl)


def _geocentric_to_geodetic(x: float, y: float, z: float, es: float, a: float, b: float):
    p = math.sqrt(x * x + y * y)
    rr = math.sqrt(x * x + y * y + z * z)
    if p / a < 1e-12:
        lon = 0.0
        if rr / a < 1e-12:
            return (x, y, z)
    else:
        lon = math.atan2(y, x)
    ct = z / rr
    st = p / rr
    rx = 1 / math.sqrt(1 - es * (2 - es) * st * st)
    cphi0 = st * (1 - es) * rx
    sphi0 = ct * rx
    it = 0
    while True:
        it += 1
        rn = a / math.sqrt(1 - es * sphi0 * sphi0)
        height = p * cphi0 + z * sphi0 - rn * (1 - es * sphi0 * sphi0)
        rk = es * rn / (rn + height)
        rx = 1 / math.sqrt(1 - rk * (2 - rk) * st * st)
        cphi = st * (1 - rk) * rx
        sphi = ct * rx
        sdphi = sphi * cphi0 - cphi * sphi0
        cphi0 = cphi
        sphi0 = sphi
        if not (sdphi * sdphi > 1e-24 and it < 30):
            break
    lat = math.atan(sphi / abs(cphi))
    return (lon, lat, height)


def _datum_is_identity(src: dict, dst: dict) -> bool:
    """proj4js ``datum_transform`` returns the point unchanged."""
    if _same_datum(src, dst):
        return True
    return (src["es"] == dst["es"] and src["a"] == dst["a"] and src["type"] == _DT_WGS84
            and dst["type"] == _DT_WGS84)


def _datum_transform(src: dict, dst: dict, lon: float, lat: float) -> tuple:
    """proj4js ``datum_transform`` on radians (no grid shifts); call only when not identity."""
    x, y, z = _geodetic_to_geocentric(lon, lat, 0.0, src["es"], src["a"])
    p = src["params"]
    if src["type"] == _DT_3PARAM:
        x, y, z = x + p[0], y + p[1], z + p[2]
    elif src["type"] == _DT_7PARAM:
        dx, dy, dz, rx, ry, rz, m = p[:7]
        x, y, z = (m * (x - rz * y + ry * z) + dx, m * (rz * x + y - rx * z) + dy, m * (-ry * x + rx * y + z) + dz)
    # destination is WGS84 (no parameters to remove)
    lon2, lat2, _ = _geocentric_to_geodetic(x, y, z, dst["es"], dst["a"], dst["b"])
    return lon2, lat2


def make_reprojector(prj_text: Optional[str], geoms: Sequence[Optional[dict]]) -> Optional[Callable]:
    """Coordinate function to WGS84 lon/lat for a ``.prj``; None when no reprojection is needed.

    Without a ``.prj`` the coordinates must look like longitude/latitude, else a
    :class:`ShapefileError` is raised. A ``GEOGCS`` WKT on WGS84 is used as is.

    The projection itself is inverted with PROJ (pyproj); the datum step follows
    proj4js, which FlowMapper uses: a datum shift is applied only from a WKT
    ``TOWGS84`` node or proj4js's small datum table (e.g. OSGB 1936), and a
    datum with a different ellipsoid but no parameters (e.g. NAD27) is converted
    through geocentric coordinates *without* a shift. This differs from PROJ's
    own datum transformations by up to a few hundred metres for such datums, but
    matches FlowMapper.org to ~1e-12 degrees.

    JS: ShapefileReader.js:makeReprojector
    """
    if prj_text and js_trim(prj_text):
        wkt = js_trim(prj_text)
        if re.match(r"GEOGCS", wkt, re.I) and re.search(r"WGS[_ ]?(19)?84|D_WGS_1984", wkt, re.I):
            return None
        try:
            return _wkt_reprojector(wkt)
        except ShapefileError:
            raise
        except Exception as e:  # pyproj.exceptions.CRSError and friends
            raise ShapefileError(f"The coordinate system in the .prj file is not supported ({e}). Please "
                                 "export the shapefile in WGS84 (EPSG:4326) or as GeoJSON.") from e
    for g in geoms:
        if not g:
            continue
        nums = [abs(x) for x in _flat_coords(g["coordinates"]) if math.isfinite(x)]
        for i in range(0, len(nums), 2):
            if nums[i] > 180 or (i + 1 < len(nums) and nums[i + 1] > 90):
                raise ShapefileError(MSG_NOT_LONLAT)
    return None


def _flat_coords(coords) -> Iterable[float]:
    if not coords:
        return
    if isinstance(coords[0], (int, float)):
        yield from coords
        return
    for c in coords:
        yield from _flat_coords(c)


def _wkt_reprojector(wkt: str) -> Callable:
    from pyproj import CRS, Transformer

    ext = re.search(r'EXTENSION\s*\[\s*"PROJ4"\s*,\s*"([^"]*)"', wkt, re.I)
    if ext:
        crs = CRS.from_proj4(ext.group(1))
    else:
        crs = CRS.from_wkt(wkt)
    if crs.is_bound:
        crs = crs.source_crs
    if crs.is_geocentric or not (crs.is_projected or crs.is_geographic):
        raise ShapefileError(f"The coordinate system in the .prj file is not supported ({crs.name}). Please "
                             "export the shapefile in WGS84 (EPSG:4326) or as GeoJSON.")
    ell = crs.ellipsoid
    a = ell.semi_major_metre
    rf = ell.inverse_flattening
    if ext:
        p4 = ext.group(1)
        if re.search(r"\+nadgrids=@?null", p4):
            src = None   # proj4js: null grid shift -> no datum change
        else:
            tw = re.search(r"\+towgs84=([^\s]+)", p4)
            dm = re.search(r"\+datum=([^\s]+)", p4)
            src = _p4_datum(dm.group(1) if dm else "custom", tw.group(1).split(",") if tw else None, a, rf)
    else:
        info = _wkt_datum(wkt)
        a2 = info["a"] if info["a"] is not None else a
        rf2 = info["rf"] if info["rf"] is not None else rf
        src = _p4_datum(info["code"], info["params"], a2, rf2)
    # inverse projection onto the CRS's own ellipsoid (degrees, Greenwich), no datum change
    tgt = CRS.from_proj4(f"+proj=longlat +a={a!r} +rf={rf!r} +no_defs" if rf else
                         f"+proj=longlat +a={a!r} +b={a!r} +no_defs")
    tr = Transformer.from_crs(crs, tgt, always_xy=True)
    dst = _WGS84_DATUM
    identity = src is None or _datum_is_identity(src, dst)

    def fwd(c: Sequence[float]) -> List[float]:
        x, y = c[0], c[1]
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float)) and math.isfinite(x) and math.isfinite(y)):
            raise ShapefileError("coordinates must be finite numbers")
        lon, lat = tr.transform(x, y)
        if not (math.isfinite(lon) and math.isfinite(lat)):
            return [math.nan, math.nan]
        if identity:
            return [lon, lat]
        lam, phi = _datum_transform(src, dst, lon * _D2R, lat * _D2R)
        return [lam * _R2D, phi * _R2D]
    return fwd


def _map_coords(coords, fn):
    """Apply ``fn`` to every position. JS: ShapefileReader.js:mapCoords"""
    if coords and isinstance(coords[0], (int, float)):
        return fn(coords)
    return [_map_coords(c, fn) for c in coords]


# ====================================================================== public
def from_parts(shp: Optional[bytes], shx: Optional[bytes] = None, dbf: Optional[bytes] = None,
               prj: Optional[str] = None, cpg: Optional[str] = None, label: Optional[str] = None) -> dict:
    """GeoJSON FeatureCollection from the component files (bytes; ``prj``/``cpg`` as text).

    JS: ShapefileReader.js:fromParts
    """
    if shp is None:
        raise ShapefileError("No .shp file was found" + (" in " + label if label else "") +
                             ". Select the .shp, .shx, .dbf and .prj files together (or one .zip that contains them).")
    geoms = parse_shp(shp, shx)
    rows = parse_dbf(dbf, cpg) if dbf is not None else []
    reproject = make_reprojector(prj, geoms)
    features = []
    for i, g in enumerate(geoms):
        if not g:
            continue
        if reproject is not None:
            g = {"type": g["type"], "coordinates": _map_coords(g["coordinates"], reproject)}
        features.append({"type": "Feature", "properties": rows[i] if i < len(rows) else {}, "geometry": g})
    return {
        "type": "FeatureCollection",
        "features": features,
        "_shapefileInfo": {"hasDbf": dbf is not None, "hasPrj": bool(prj), "hasShx": shx is not None,
                           "records": len(geoms)},
    }


def is_shapefile_selection(names: Iterable[PathLike]) -> bool:
    """True when any of the file names is a .zip or a shapefile component.

    JS: ShapefileReader.js:isShapefileSelection
    """
    return any(re.fullmatch(r"zip|shp|dbf|shx|prj|cpg", _ext(str(n))) for n in names)


def read_files(files: Sequence[Union[PathLike, tuple]]) -> dict:
    """Read a selection of files exactly like ``ShapefileReader.read`` does.

    ``files`` are paths, or ``(name, bytes)`` pairs. A .zip among them wins;
    otherwise the last file of each extension is used.

    JS: ShapefileReader.js:read
    """
    items = []
    for f in files:
        if isinstance(f, tuple):
            items.append((str(f[0]), f[1]))
        else:
            items.append((Path(f).name, Path(f)))

    def data(x) -> bytes:
        return x.read_bytes() if isinstance(x, Path) else bytes(x)

    zips = [it for it in items if _ext(it[0]) == "zip"]
    if zips:
        zname, zsrc = zips[0]
        entries = read_zip(data(zsrc))
        names = list(entries)
        shp_names = [n for n in names if _ext(n) == "shp"]
        if not shp_names:
            raise ShapefileError(MSG_ZIP_NO_SHP)
        stem = _base_name(shp_names[0])

        def pick(e: str) -> Optional[bytes]:
            same = [x for x in names if _ext(x) == e and _base_name(x) == stem]
            anyx = [x for x in names if _ext(x) == e]
            n = same[0] if same else (anyx[0] if anyx else None)
            return entries[n] if n is not None else None
        gj = from_parts(pick("shp"), pick("shx"), pick("dbf"), _utf8_text(pick("prj")), _utf8_text(pick("cpg")),
                        label=zname)
        if len(shp_names) > 1:
            gj["_shapefileInfo"]["note"] = (f"The .zip contains {len(shp_names)} shapefiles; only "
                                            f"{shp_names[0]} was loaded.")
        return gj
    by_ext = {}
    for name, src in items:
        by_ext[_ext(name)] = src
    get = lambda e: data(by_ext[e]) if e in by_ext else None  # noqa: E731
    return from_parts(get("shp"), get("shx"), get("dbf"), _utf8_text(get("prj")), _utf8_text(get("cpg")))


def _siblings(path: Path) -> List[Path]:
    """The shapefile components next to ``path`` (same stem, any case)."""
    stem = path.stem.lower() if _ext(path.name) in SHAPEFILE_EXTENSIONS else path.name.lower()
    folder = path.parent
    out = []
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            if p.is_file() and _ext(p.name) in ("shp", "shx", "dbf", "prj", "cpg") and p.stem.lower() == stem:
                out.append(p)
    return out


def read_shapefile(source: Union[PathLike, Sequence[PathLike], bytes]) -> dict:
    """Read a shapefile into a GeoJSON FeatureCollection (WGS84 lon/lat).

    Parameters
    ----------
    source
        * a ``.zip`` path (or the zip's bytes);
        * a ``.shp`` path (or any component, or the path without extension): the
          ``.shx``, ``.dbf``, ``.prj`` and ``.cpg`` with the same name are used;
        * a list of paths: read exactly like a browser file selection.

    Returns
    -------
    dict
        ``{"type": "FeatureCollection", "features": [...], "_shapefileInfo": {...}}``

    Raises
    ------
    ShapefileError
        with FlowMapper.org's message.

    JS: ShapefileReader.js:read
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        return read_files([("upload.zip", bytes(source))])
    if isinstance(source, (list, tuple)):
        return read_files(list(source))
    p = Path(source)
    if _ext(p.name) == "zip":
        if not p.is_file():
            raise FileNotFoundError(str(p))
        return read_files([p])
    files = _siblings(p)
    if not files:
        if not p.exists():
            raise FileNotFoundError(str(p))
        files = [p]
    return read_files(files)
