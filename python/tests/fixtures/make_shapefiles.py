"""Generate the small binary shapefile fixtures in ``tests/fixtures/shapefiles``.

Pure Python (``struct`` + ``zipfile``); pyproj is used only to compute the
projected coordinates of the UTM / Albers fixtures. Run from the package root::

    .venv\\Scripts\\python tests/fixtures/make_shapefiles.py

The output is deterministic, so the files can be committed and regenerated.
Each fixture exercises one feature of ``ShapefileReader.js``; ``CASES`` at the
bottom of this file documents them and is also used by the tests.
"""
from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

OUT = Path(__file__).resolve().parent / "shapefiles"

NULL, POINT, POLYLINE, POLYGON, MULTIPOINT = 0, 1, 3, 5, 8
POINTZ, POLYLINEZ, POLYGONZ, MULTIPOINTZ = 11, 13, 15, 18
POINTM, POLYLINEM, POLYGONM = 21, 23, 25
MULTIPATCH = 31

PRJ_WGS84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')
PRJ_UTM15N = ('PROJCS["WGS_1984_UTM_Zone_15N",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
              'SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
              'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
              'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],'
              'PARAMETER["Central_Meridian",-93.0],PARAMETER["Scale_Factor",0.9996],'
              'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')
PRJ_ALBERS = ('PROJCS["USA_Contiguous_Albers_Equal_Area_Conic",GEOGCS["GCS_North_American_1983",'
              'DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
              'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Albers"],'
              'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
              'PARAMETER["Central_Meridian",-96.0],PARAMETER["Standard_Parallel_1",29.5],'
              'PARAMETER["Standard_Parallel_2",45.5],PARAMETER["Latitude_Of_Origin",37.5],'
              'UNIT["Meter",1.0]]')
PRJ_GEOG_NAD83 = ('GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
                  'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
                  'UNIT["Degree",0.0174532925199433]]')
# OGC WKT1 (GDAL flavour, with AUTHORITY nodes) for WGS 84 / UTM zone 33N.
PRJ_OGC_UTM33N = ('PROJCS["WGS 84 / UTM zone 33N",GEOGCS["WGS 84",DATUM["WGS_1984",'
                  'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
                  'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
                  'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],'
                  'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],'
                  'PARAMETER["central_meridian",15],PARAMETER["scale_factor",0.9996],'
                  'PARAMETER["false_easting",500000],PARAMETER["false_northing",0],'
                  'UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],'
                  'AUTHORITY["EPSG","32633"]]')
PRJ_MERC_SPHERE = ('PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",GEOGCS["GCS_WGS_1984",'
                   'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
                   'UNIT["Degree",0.0174532925199433]],PROJECTION["Mercator_Auxiliary_Sphere"],'
                   'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
                   'PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],'
                   'PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]')
PRJ_GEOG_NAD27 = ('GEOGCS["GCS_North_American_1927",DATUM["D_North_American_1927",'
                  'SPHEROID["Clarke_1866",6378206.4,294.9786982]],PRIMEM["Greenwich",0.0],'
                  'UNIT["Degree",0.0174532925199433]]')
PRJ_OSGB_7PARAM = ('PROJCS["OSGB 1936 / British National Grid",GEOGCS["OSGB 1936",DATUM["OSGB_1936",'
                   'SPHEROID["Airy 1830",6377563.396,299.3249646],'
                   'TOWGS84[446.448,-125.157,542.06,0.15,0.247,0.842,-20.489]],PRIMEM["Greenwich",0],'
                   'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
                   'PARAMETER["latitude_of_origin",49],PARAMETER["central_meridian",-2],'
                   'PARAMETER["scale_factor",0.9996012717],PARAMETER["false_easting",400000],'
                   'PARAMETER["false_northing",-100000],UNIT["metre",1]]')
PRJ_ED50_3PARAM = ('PROJCS["ED50 / UTM zone 32N",GEOGCS["ED50",DATUM["European_Datum_1950",'
                   'SPHEROID["International 1924",6378388,297],TOWGS84[-87,-98,-121,0,0,0,0]],'
                   'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
                   'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",9],'
                   'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],'
                   'PARAMETER["false_northing",0],UNIT["metre",1]]')
PRJ_STATEPLANE_FT = ('PROJCS["NAD_1983_StatePlane_Iowa_North_FIPS_1401_Feet",GEOGCS["GCS_North_American_1983",'
                     'DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
                     'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
                     'PROJECTION["Lambert_Conformal_Conic"],PARAMETER["False_Easting",4921250.0],'
                     'PARAMETER["False_Northing",3280833.333333333],PARAMETER["Central_Meridian",-93.5],'
                     'PARAMETER["Standard_Parallel_1",42.06666666666667],'
                     'PARAMETER["Standard_Parallel_2",43.26666666666667],'
                     'PARAMETER["Latitude_Of_Origin",41.5],UNIT["Foot_US",0.3048006096012192]]')
PRJ_BAD ='PROJCS["nonsense",GEOGCS["x",DATUM["y",SPHEROID["z",1,0]]],PROJECTION["No_Such_Projection"]]'


# ---------------------------------------------------------------------- geometry helpers
def square(x0: float, y0: float, w: float, h: float, cw: bool = True) -> list:
    """Closed rectangle ring; clockwise (shapefile outer ring) unless cw=False."""
    pts = [(x0, y0), (x0, y0 + h), (x0 + w, y0 + h), (x0 + w, y0), (x0, y0)]
    return pts if cw else pts[::-1]


def _bbox(points: Sequence) -> tuple:
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def record_content(shape_type: int, geom) -> bytes:
    """Bytes of one record's content (after the 8-byte record header)."""
    if geom is None or shape_type == NULL:
        return struct.pack("<i", 0)
    t = shape_type
    if t in (POINT, POINTZ, POINTM):
        x, y = geom
        out = struct.pack("<idd", t, x, y)
        if t == POINTZ:
            out += struct.pack("<dd", 100.5, 0.0)   # z, m
        elif t == POINTM:
            out += struct.pack("<d", 7.0)           # m
        return out
    if t in (MULTIPOINT, MULTIPOINTZ):
        pts = list(geom)
        out = struct.pack("<i4di", t, *_bbox(pts), len(pts))
        for x, y in pts:
            out += struct.pack("<dd", x, y)
        if t == MULTIPOINTZ:
            out += struct.pack("<dd", 0.0, 1.0) + b"".join(struct.pack("<d", float(i)) for i in range(len(pts)))
            out += struct.pack("<dd", 0.0, 1.0) + b"".join(struct.pack("<d", float(i)) for i in range(len(pts)))
        return out
    if t == MULTIPATCH:
        # A minimal multipatch record: the reader does not support the type.
        parts = list(geom)
        pts = [p for part in parts for p in part]
        out = struct.pack("<i4dii", t, *_bbox(pts), len(parts), len(pts))
        idx = 0
        for part in parts:
            out += struct.pack("<i", idx)
            idx += len(part)
        out += b"".join(struct.pack("<i", 0) for _ in parts)  # part types
        for x, y in pts:
            out += struct.pack("<dd", x, y)
        return out
    # polyline / polygon (+ Z / M)
    parts = [list(r) for r in geom]
    pts = [p for r in parts for p in r]
    out = struct.pack("<i4dii", t, *_bbox(pts), len(parts), len(pts))
    idx = 0
    for r in parts:
        out += struct.pack("<i", idx)
        idx += len(r)
    for x, y in pts:
        out += struct.pack("<dd", x, y)
    n = len(pts)
    if t in (POLYLINEZ, POLYGONZ):
        out += struct.pack("<dd", 1.0, float(n)) + b"".join(struct.pack("<d", float(i + 1)) for i in range(n))
        out += struct.pack("<dd", 0.0, 0.0) + b"".join(struct.pack("<d", 0.0) for _ in range(n))
    elif t in (POLYLINEM, POLYGONM):
        out += struct.pack("<dd", 0.0, float(n)) + b"".join(struct.pack("<d", float(i)) for i in range(n))
    return out


def _header(shape_type: int, file_len_bytes: int, bbox: tuple) -> bytes:
    h = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, file_len_bytes // 2)
    h += struct.pack("<2i", 1000, shape_type)
    h += struct.pack("<8d", *bbox, 0.0, 0.0, 0.0, 0.0)
    assert len(h) == 100
    return h


def build_shp(shape_type: int, geoms: Sequence, padding: int = 0) -> tuple:
    """Return (shp_bytes, shx_bytes). ``padding`` zero bytes are put between records."""
    body = b""
    index = []
    allpts = []
    for i, g in enumerate(geoms):
        rec_type = shape_type if g is not None else NULL
        content = record_content(rec_type, g)
        offset = 100 + len(body)
        index.append((offset, len(content)))
        body += struct.pack(">2i", i + 1, len(content) // 2) + content
        if padding and i < len(geoms) - 1:
            body += b"\x00" * padding
        if g is not None:
            if shape_type in (POINT, POINTZ, POINTM):
                allpts.append(g)
            elif shape_type in (MULTIPOINT, MULTIPOINTZ):
                allpts.extend(g)
            else:
                allpts.extend(p for r in g for p in r)
    bbox = _bbox(allpts)
    shp = _header(shape_type, 100 + len(body), bbox) + body
    shx = _header(shape_type, 100 + 8 * len(index), bbox)
    for off, ln in index:
        shx += struct.pack(">2i", off // 2, ln // 2)
    return shp, shx


# ---------------------------------------------------------------------- dbf
def build_dbf(fields: Sequence[tuple], rows: Sequence[Sequence], *, encoding: str = "utf-8",
              ldid: int = 0, deleted: Iterable[int] = (), raw_cells: Optional[dict] = None) -> bytes:
    """fields: (name, type, length, decimals). rows: python values (None -> blank).

    ``raw_cells`` maps (row, col) to pre-encoded bytes (e.g. invalid UTF-8).
    """
    deleted = set(deleted)
    raw_cells = raw_cells or {}
    nf = len(fields)
    header_len = 32 + 32 * nf + 1
    record_len = 1 + sum(f[2] for f in fields)
    out = struct.pack("<B3BIHH", 0x03, 126, 11, 15, len(rows), header_len, record_len)
    out += b"\x00" * 17 + bytes([ldid]) + b"\x00" * 2
    assert len(out) == 32
    for name, typ, length, dec in fields:
        nb = name.encode(encoding)[:11]
        out += nb + b"\x00" * (11 - len(nb)) + typ.encode("ascii") + b"\x00" * 4
        out += bytes([length, dec]) + b"\x00" * 14
    out += b"\x0d"
    for r, row in enumerate(rows):
        out += b"*" if r in deleted else b" "
        for c, ((name, typ, length, dec), v) in enumerate(zip(fields, row)):
            if (r, c) in raw_cells:
                cell = raw_cells[(r, c)]
            elif v is None:
                cell = b""
            elif typ == "C":
                cell = str(v).encode(encoding)
            elif typ in ("N", "F"):
                s = v if isinstance(v, str) else (f"{v:.{dec}f}" if dec else str(int(v)))
                cell = s.rjust(length).encode("ascii")
            elif typ == "L":
                cell = (v if isinstance(v, str) else ("T" if v else "F")).encode("ascii")
            elif typ == "D":
                cell = str(v).encode("ascii")
            else:
                cell = str(v).encode(encoding)
            cell = cell[:length]
            if typ in ("N", "F") and v is not None and (r, c) not in raw_cells:
                out += cell.rjust(length, b" ")
            else:
                out += cell.ljust(length, b" ")
    out += b"\x1a"
    return out


# ---------------------------------------------------------------------- writing
def write(stem: str, shape_type: int, geoms: Sequence, *, dbf: Optional[bytes] = None, prj: Optional[str] = None,
          cpg: Optional[str] = None, shx: bool = True, padding: int = 0, folder: Path = OUT) -> dict:
    shp_b, shx_b = build_shp(shape_type, geoms, padding)
    files = {f"{stem}.shp": shp_b}
    if shx:
        files[f"{stem}.shx"] = shx_b
    if dbf is not None:
        files[f"{stem}.dbf"] = dbf
    if prj is not None:
        files[f"{stem}.prj"] = prj.encode("utf-8")
    if cpg is not None:
        files[f"{stem}.cpg"] = cpg.encode("utf-8")
    folder.mkdir(parents=True, exist_ok=True)
    for name, b in files.items():
        (folder / name).write_bytes(b)
    return files


def _zip(path: Path, entries: Sequence[tuple], method: int = zipfile.ZIP_DEFLATED) -> None:
    """entries: (name, bytes or None for a directory entry)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=method) as z:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 15, 12, 0, 0))
            info.compress_type = method
            info.external_attr = 0o644 << 16
            if data is None:
                info.external_attr = (0o755 << 16) | 0x10
                z.writestr(info, b"")
            else:
                z.writestr(info, data)
    path.write_bytes(buf.getvalue())


# ---------------------------------------------------------------------- the fixtures
POLY_FIELDS = [("NAME", "C", 30, 0), ("CODE", "N", 6, 0), ("RATE", "N", 12, 4), ("FLAG", "L", 1, 0),
               ("DATE", "D", 8, 0), ("EMPTY", "N", 8, 0), ("ZERO", "N", 4, 0), ("NOTE", "C", 12, 0),
               ("2010", "N", 6, 0)]


def poly_geoms() -> list:
    lon, lat = -93.123456789, 41.987654321
    return [
        # 0: a clockwise square (outer ring)
        [square(lon, lat, 1.25, 0.75)],
        # 1: outer ring with a counter-clockwise hole inside it
        [square(lon + 2, lat, 2.0, 2.0), square(lon + 2.5, lat + 0.5, 0.5, 0.5, cw=False)],
        # 2: multipart: hole listed first, then two outers; the hole is inside the 2nd outer
        [square(lon + 6.2, lat + 0.2, 0.3, 0.3, cw=False), square(lon + 5, lat, 0.5, 0.5),
         square(lon + 6, lat, 1.0, 1.0)],
        # 3: null shape (skipped, and so is its .dbf row)
        None,
        # 4: only counter-clockwise rings: they become the outer rings
        [square(lon, lat + 3, 0.5, 0.5, cw=False), square(lon + 1, lat + 3, 0.5, 0.5, cw=False)],
        # 5: a hole that is in no outer ring becomes its own (reversed) polygon
        [square(lon + 3, lat + 3, 0.5, 0.5), square(lon + 5, lat + 3, 0.25, 0.25, cw=False)],
        # 6: a degenerate 3-point ring is dropped
        [[(lon, lat + 5), (lon + 1, lat + 5), (lon, lat + 5)], square(lon + 2, lat + 5, 0.5, 0.5)],
        # 7: a polygon with no parts
        [],
        # 8: two holes in one outer + one separate island
        [square(lon + 8, lat, 3.0, 3.0), square(lon + 8.5, lat + 0.5, 0.5, 0.5, cw=False),
         square(lon + 9.5, lat + 1.5, 0.5, 0.5, cw=False), square(lon + 12, lat, 0.5, 0.5)],
    ]


def poly_rows() -> list:
    return [
        ["São Paulo", 1, 0.5, True, "20240131", None, 0, "1.5", 2010],
        ["Zürich", 22, -3.25, False, "19991231", None, 0, "abc", 2011],
        ["北京市", 333, 1234.5678, "Y", "2026", None, 0, "", 2012],
        ["null shape row", 4, 4.0, "?", "", None, 0, "x", 2013],
        ["Kraków", 5, 0.0, "n", "20000101", None, 0, " pad ", 2014],
        ["Ærø", 6, 6.125, "t", "20201010", None, 0, "6", 2015],
        ["İstanbul", 7, 7.0, "f", "20201011", None, 0, "-7", 2016],
        ["Empty", 8, 8.0, None, None, None, 0, None, 2017],
        ["Löwenzahn €", 9, 9.9999, "T", "20211212", None, 0, "9e2", 2018],
    ]


def utm_geoms(prj_epsg: str, origin=(-93.6, 41.6)) -> list:
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", prj_epsg, always_xy=True)
    lon, lat = origin

    def ring(x0, y0, w, h, cw=True):
        return [tuple(tr.transform(x, y)) for x, y in square(x0, y0, w, h, cw)]
    return [
        [ring(lon, lat, 0.4, 0.3)],
        [ring(lon + 0.5, lat, 1.0, 0.8), ring(lon + 0.7, lat + 0.2, 0.2, 0.2, cw=False)],
        [ring(lon - 1.0, lat - 1.0, 0.3, 0.3), ring(lon - 0.5, lat - 1.0, 0.3, 0.3)],
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        p.unlink()

    geoms = poly_geoms()
    rows = poly_rows()
    dbf_utf8 = build_dbf(POLY_FIELDS, rows, encoding="utf-8", deleted=[5])
    poly = write("poly_wgs84", POLYGON, geoms, dbf=dbf_utf8, prj=PRJ_WGS84, cpg="UTF-8")

    # Windows-1252 text announced only by the LDID byte (0x57), no .cpg, no .prj
    cp_fields = [("NAME", "C", 20, 0), ("AÑO", "N", 4, 0)]
    cp_rows = [["Bogotá", 1999], ["Œuvre € naïve", 2000], ["Façade “quoted”", 2001]]
    write("poly_cp1252", POLYGON, geoms[:3], dbf=build_dbf(cp_fields, cp_rows, encoding="cp1252", ldid=0x57))

    # .cpg says 1252 (with stray whitespace); LDID 0
    write("poly_cpg1252", POLYGON, geoms[:3], dbf=build_dbf(cp_fields, cp_rows, encoding="cp1252"),
          prj=PRJ_WGS84, cpg=" 1252\r\n")

    # No .cpg and LDID 0: every field is tried as UTF-8 and falls back to Windows-1252
    guess_rows = [["Zürich", 1], ["Café", 2], ["plain", 3]]
    write("poly_guess", POLYGON, geoms[:3],
          dbf=build_dbf(cp_fields, guess_rows, encoding="utf-8", raw_cells={(1, 0): "Café".encode("cp1252")}),
          prj=PRJ_WGS84)

    # A .cpg with an encoding name the reader maps (GBK); LDID 0x4d would also say GBK
    write("poly_gbk", POLYGON, geoms[:2],
          dbf=build_dbf([("NAME", "C", 20, 0)], [["北京"], ["上海"]], encoding="gbk", ldid=0x4d))

    # Projected coordinates
    utm_fields = [("ID", "N", 4, 0), ("LABEL", "C", 10, 0)]
    utm_rows = [[1, "a"], [2, "b"], [3, "c"]]
    write("utm15n", POLYGON, utm_geoms("EPSG:32615"), dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_UTM15N)
    write("albers_nad83", POLYGON, utm_geoms("ESRI:102003"), dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_ALBERS)
    write("ogc_utm33n", POLYGON, utm_geoms("EPSG:32633", origin=(14.2, 50.1)),
          dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_OGC_UTM33N)
    write("webmerc", POLYGON, utm_geoms("EPSG:3857"), dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_MERC_SPHERE)
    write("geog_nad83", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_GEOG_NAD83)
    write("geog_nad27", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_GEOG_NAD27)
    write("osgb_7param", POLYGON, utm_geoms(PRJ_OSGB_7PARAM, origin=(-2.3, 52.4)),
          dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_OSGB_7PARAM)
    write("ed50_3param", POLYGON, utm_geoms(PRJ_ED50_3PARAM, origin=(9.1, 45.4)),
          dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_ED50_3PARAM)
    write("stateplane_ft", POLYGON, utm_geoms(PRJ_STATEPLANE_FT, origin=(-93.9, 42.5)),
          dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_STATEPLANE_FT)
    write("noprj_projected", POLYGON, utm_geoms("EPSG:32615"), dbf=build_dbf(utm_fields, utm_rows))
    write("badprj", POLYGON, utm_geoms("EPSG:32615"), dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_BAD)

    # .shx variants
    write("noshx", POLYGON, geoms, dbf=dbf_utf8, prj=PRJ_WGS84, cpg="UTF-8", shx=False)
    write("padded", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_WGS84, padding=16)
    write("padded_noshx", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_WGS84,
          padding=16, shx=False)
    # .shx with a bad magic number: records are read in file order
    b = write("badshx", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_WGS84)
    (OUT / "badshx.shx").write_bytes(b"\x00\x00\x00\x01" + b["badshx.shx"][4:])
    # .shx whose last offset points past the end of the .shp
    b = write("shx_overrun", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows), prj=PRJ_WGS84)
    (OUT / "shx_overrun.shx").write_bytes(b["shx_overrun.shx"] + struct.pack(">2i", 10_000_000, 10))

    # Other shape types
    pts = [(-93.5, 41.6), (-87.6, 41.9), (-95.4, 29.8)]
    pt_dbf = build_dbf([("CITY", "C", 12, 0)], [["Des Moines"], ["Chicago"], ["Houston"]])
    write("points", POINT, pts, dbf=pt_dbf, prj=PRJ_WGS84)
    write("pointz", POINTZ, pts, dbf=pt_dbf)
    write("pointm", POINTM, pts, dbf=pt_dbf)
    write("multipoint", MULTIPOINT, [pts, pts[:1], []], dbf=pt_dbf)
    write("multipointz", MULTIPOINTZ, [pts, pts[:2], pts[1:]], dbf=pt_dbf)
    lines = [[pts], [pts[:2], pts[1:]], [[(-90.0, 40.0), (-89.0, 40.5)]]]
    write("polyline", POLYLINE, lines, dbf=pt_dbf)
    write("polylinez", POLYLINEZ, lines, dbf=pt_dbf)
    write("polygonz", POLYGONZ, geoms[:3], dbf=build_dbf(utm_fields, utm_rows))
    write("polygonm", POLYGONM, geoms[:3], dbf=build_dbf(utm_fields, utm_rows))
    write("multipatch", MULTIPATCH, [[square(0, 0, 1, 1)], [square(2, 2, 1, 1)]],
          dbf=build_dbf([("ID", "N", 4, 0)], [[1], [2]]))
    write("nodbf", POLYGON, geoms[:3], prj=PRJ_WGS84)
    # .dbf with fewer rows than shapes
    write("short_dbf", POLYGON, geoms[:3], dbf=build_dbf(utm_fields, utm_rows[:1]), prj=PRJ_WGS84)

    # Malformed files
    full = poly["poly_wgs84.shp"]
    (OUT / "truncated.shp").write_bytes(full[:100 + 8 + 60])           # stops inside record 1
    (OUT / "truncated.shx").write_bytes(poly["poly_wgs84.shx"])
    (OUT / "truncated_noshx.shp").write_bytes(full[:100 + 8 + 60])
    (OUT / "notashp.shp").write_bytes(b"GIF89a" + b"\x00" * 200)
    (OUT / "tiny.shp").write_bytes(full[:50])
    (OUT / "truncated.dbf").write_bytes(dbf_utf8[:20])
    (OUT / "empty.dbf").write_bytes(b"")

    # Zip archives
    def entries(stem, prefix=""):
        return [(prefix + n, d) for n, d in sorted(poly.items())] if stem == "poly_wgs84" else []
    _zip(OUT / "poly_wgs84.zip", entries("poly_wgs84"))
    _zip(OUT / "poly_wgs84_stored.zip", entries("poly_wgs84"), method=zipfile.ZIP_STORED)
    pt_files = {n: (OUT / n).read_bytes() for n in ("points.shp", "points.shx", "points.dbf", "points.prj")}
    nested = [("Data/", None), ("Data/Regions/", None)] + entries("poly_wgs84", "Data/Regions/")
    nested += [("__MACOSX/Data/Regions/._poly_wgs84.shp", b"\x00\x05\x16\x07junk"),
               ("Data/Regions/._poly_wgs84.dbf", b"junk"),
               ("Data/Regions/readme.txt", b"region polygons"),
               ("Data/Other/", None)] + [("Data/Other/" + n, d) for n, d in sorted(pt_files.items())]
    _zip(OUT / "nested.zip", nested)
    # stems differ in case; the .dbf only exists in another folder -> fallback pick by extension
    mixed = [("A/POLY.SHP", poly["poly_wgs84.shp"]), ("A/poly.Shx", poly["poly_wgs84.shx"]),
             ("B/attributes.DBF", poly["poly_wgs84.dbf"]), ("A/Poly.PRJ", poly["poly_wgs84.prj"]),
             ("A/poly.cpg", poly["poly_wgs84.cpg"])]
    _zip(OUT / "mixedcase.zip", mixed)
    _zip(OUT / "noshp.zip", [("poly_wgs84.dbf", poly["poly_wgs84.dbf"])])
    utm_files = sorted((n, (OUT / n).read_bytes()) for n in
                       ("utm15n.shp", "utm15n.shx", "utm15n.dbf", "utm15n.prj"))
    _zip(OUT / "utm15n.zip", utm_files)
    (OUT / "bad.zip").write_bytes(b"PK\x03\x04 this is not really a zip file " * 3)
    # unsupported compression method: a stored zip with the method fields patched to 12 (bzip2)
    _zip(OUT / "bzip2.zip", entries("poly_wgs84"), method=zipfile.ZIP_STORED)
    raw = bytearray((OUT / "bzip2.zip").read_bytes())
    i = 0
    while True:
        i = raw.find(b"PK\x03\x04", i)
        if i < 0:
            break
        raw[i + 8:i + 10] = struct.pack("<H", 12)
        i += 4
    i = 0
    while True:
        i = raw.find(b"PK\x01\x02", i)
        if i < 0:
            break
        raw[i + 10:i + 12] = struct.pack("<H", 12)
        i += 4
    (OUT / "bzip2.zip").write_bytes(bytes(raw))
    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")


# name -> how a test reads it (list of files, relative to OUT) and what to expect
CASES = {
    "poly_wgs84": ["poly_wgs84.shp", "poly_wgs84.shx", "poly_wgs84.dbf", "poly_wgs84.prj", "poly_wgs84.cpg"],
    "poly_cp1252": ["poly_cp1252.shp", "poly_cp1252.shx", "poly_cp1252.dbf"],
    "poly_cpg1252": ["poly_cpg1252.shp", "poly_cpg1252.shx", "poly_cpg1252.dbf", "poly_cpg1252.prj",
                     "poly_cpg1252.cpg"],
    "poly_guess": ["poly_guess.shp", "poly_guess.shx", "poly_guess.dbf", "poly_guess.prj"],
    "utm15n": ["utm15n.shp", "utm15n.shx", "utm15n.dbf", "utm15n.prj"],
    "albers_nad83": ["albers_nad83.shp", "albers_nad83.shx", "albers_nad83.dbf", "albers_nad83.prj"],
    "ogc_utm33n": ["ogc_utm33n.shp", "ogc_utm33n.shx", "ogc_utm33n.dbf", "ogc_utm33n.prj"],
    "webmerc": ["webmerc.shp", "webmerc.shx", "webmerc.dbf", "webmerc.prj"],
    "geog_nad83": ["geog_nad83.shp", "geog_nad83.shx", "geog_nad83.dbf", "geog_nad83.prj"],
    "geog_nad27": ["geog_nad27.shp", "geog_nad27.shx", "geog_nad27.dbf", "geog_nad27.prj"],
    "osgb_7param": ["osgb_7param.shp", "osgb_7param.shx", "osgb_7param.dbf", "osgb_7param.prj"],
    "ed50_3param": ["ed50_3param.shp", "ed50_3param.shx", "ed50_3param.dbf", "ed50_3param.prj"],
    "stateplane_ft": ["stateplane_ft.shp", "stateplane_ft.shx", "stateplane_ft.dbf", "stateplane_ft.prj"],
    "noshx": ["noshx.shp", "noshx.dbf", "noshx.prj", "noshx.cpg"],
    "padded": ["padded.shp", "padded.shx", "padded.dbf", "padded.prj"],
    "badshx": ["badshx.shp", "badshx.shx", "badshx.dbf", "badshx.prj"],
    "shx_overrun": ["shx_overrun.shp", "shx_overrun.shx", "shx_overrun.dbf", "shx_overrun.prj"],
    "points": ["points.shp", "points.shx", "points.dbf", "points.prj"],
    "pointz": ["pointz.shp", "pointz.shx", "pointz.dbf"],
    "pointm": ["pointm.shp", "pointm.shx", "pointm.dbf"],
    "multipoint": ["multipoint.shp", "multipoint.shx", "multipoint.dbf"],
    "multipointz": ["multipointz.shp", "multipointz.shx", "multipointz.dbf"],
    "polyline": ["polyline.shp", "polyline.shx", "polyline.dbf"],
    "polylinez": ["polylinez.shp", "polylinez.shx", "polylinez.dbf"],
    "polygonz": ["polygonz.shp", "polygonz.shx", "polygonz.dbf"],
    "polygonm": ["polygonm.shp", "polygonm.shx", "polygonm.dbf"],
    "multipatch": ["multipatch.shp", "multipatch.shx", "multipatch.dbf"],
    "nodbf": ["nodbf.shp", "nodbf.shx", "nodbf.prj"],
    "short_dbf": ["short_dbf.shp", "short_dbf.shx", "short_dbf.dbf", "short_dbf.prj"],
    "zip_deflated": ["poly_wgs84.zip"],
    "zip_stored": ["poly_wgs84_stored.zip"],
    "zip_nested": ["nested.zip"],
    "zip_mixedcase": ["mixedcase.zip"],
    "zip_utm": ["utm15n.zip"],
    # zip wins over the other files in a selection
    "zip_plus_files": ["points.shp", "poly_wgs84.zip", "points.dbf"],
    # a .dbf cut inside its header: no rows can be read, features get no attributes
    "truncated_dbf": ["poly_wgs84.shp", "poly_wgs84.shx", "truncated.dbf"],
    "poly_gbk_ldid": ["poly_gbk.shp", "poly_gbk.shx", "poly_gbk.dbf"],
}
# CASES whose .dbf uses an encoding the V8 TextDecoder shim does not implement
NO_PARITY = {"poly_gbk_ldid"}

# name -> files; reading must fail with an error message starting with the given text
ERROR_CASES = {
    "noprj_projected": (["noprj_projected.shp", "noprj_projected.shx", "noprj_projected.dbf"],
                        "The coordinates are not longitude/latitude and no .prj file was provided."),
    "badprj": (["badprj.shp", "badprj.shx", "badprj.dbf", "badprj.prj"],
               "The coordinate system in the .prj file is not supported"),
    "notashp": (["notashp.shp"], "The .shp file is not a valid shapefile."),
    "tiny": (["tiny.shp"], "The .shp file is not a valid shapefile."),
    "truncated_noshx": (["truncated_noshx.shp"], "The .shp file is damaged (a record runs past the end of the file)."),
    "empty_dbf": (["poly_wgs84.shp", "poly_wgs84.shx", "empty.dbf"],
                  "Offset is outside the bounds of the DataView"),
    "noshp": (["poly_wgs84.dbf", "poly_wgs84.prj"], "No .shp file was found."),
    "zip_noshp": (["noshp.zip"], "The .zip file does not contain a .shp file."),
    "zip_bad": (["bad.zip"], "The .zip file could not be read (it may be damaged)."),
    "zip_bzip2": (["bzip2.zip"], "The .zip uses an unsupported compression method."),
    "truncated": (["truncated.shp", "truncated.shx"], "The .shp file is damaged (a record runs past the end of the file)."),
    # padding between records without the .shx: a zero record length
    "padded_noshx": (["padded_noshx.shp", "padded_noshx.dbf", "padded_noshx.prj"], "The .shp file is damaged (a record runs past the end of the file)."),
    # the last file of each extension wins: points.shx indexes poly_wgs84.shp at wrong offsets
    "two_shps": (["points.shp", "points.shx", "poly_wgs84.shp", "points.dbf"], "The .shp file is damaged (a record runs past the end of the file)."),
}


if __name__ == "__main__":
    main()
