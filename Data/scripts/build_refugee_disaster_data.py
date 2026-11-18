"""Build the Refugees and DisasterMigration datasets and their FlowMapper project files.

Writes into Data/Refugees/{Ukraine,Syria} and Data/DisasterMigration/{Katrina,CampFire} of this repository.

Requirements: the flowmapper Python package (the Python companion to FlowMapper.org; it
writes the project files and preview maps), pandas, shapely, and xlrd for the 2004-2008 IRS .xls files.

    python Data/scripts/build_refugee_disaster_data.py DOWNLOAD_DIR

DOWNLOAD_DIR must hold the raw downloads (all public, no login):

  unhcr_{ukr,syr}_{year}.json   UNHCR Refugee Data Finder API
                                https://api.unhcr.org/population/v1/population/?limit=1000&yearFrom=Y&yearTo=Y&coo=UKR&coa_all=true
  wb_{indicator}.json           World Bank WDI API, indicators SP.POP.TOTL, NY.GDP.PCAP.CD, NY.GDP.MKTP.CD, SM.POP.TOTL.ZS
                                https://api.worldbank.org/v2/country/all/indicator/IND?format=json&per_page=20000&date=2015:2025
  ne_50m_countries.geojson      Natural Earth 1:50m admin-0 countries (github.com/nvkelso/natural-earth-vector)
  irs/co{0405,0506,0607,0708}/  IRS SOI county-to-county migration, LA and MS in/out .xls (irs.gov/pub/irs-soi/county0506.zip ...)
  irs/countyoutflow{1718,1819,1920}.csv   IRS SOI county outflows (irs.gov/pub/irs-soi/countyoutflow1819.csv ...)
  gaz/g2010/Gaz_counties_national.txt, gaz/g2019/2019_Gaz_counties_national.txt   Census Gazetteer county centroids
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from shapely.geometry import mapping, shape

import flowmapper as fm

DL = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[1]                      # the repository's Data folder
US_STATES = OUT.parent / "Code" / "WebContent" / "assets" / "js" / "support" / "us-states.json"

STATE_FIPS = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California", "08": "Colorado",
    "09": "Connecticut", "10": "Delaware", "11": "District of Columbia", "12": "Florida", "13": "Georgia",
    "15": "Hawaii", "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa", "20": "Kansas",
    "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland", "25": "Massachusetts", "26": "Michigan",
    "27": "Minnesota", "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada",
    "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico", "36": "New York", "37": "North Carolina",
    "38": "North Dakota", "39": "Ohio", "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
    "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont",
    "51": "Virginia", "53": "Washington", "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming",
}


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  wrote {path.relative_to(OUT)} ({len(df)} rows)")


# ======================================================================================
# Part 1. Refugee flows from Ukraine (and Syria) with receiving-country attributes
# ======================================================================================
NE_FIX = {"KOS": "XKX"}  # Natural Earth code -> code used by UNHCR / World Bank


def load_countries(clip=None):
    """Country label points (all countries) and polygons (clipped to `clip` = (W, S, E, N) when given).

    Clipping the polygons to the study area makes FlowMapper zoom to it when the project opens.
    """
    from shapely.geometry import box
    window = box(*clip) if clip else None
    ne = json.loads((DL / "ne_50m_countries.geojson").read_text(encoding="utf-8"))
    rows, feats = [], []
    for f in ne["features"]:
        p = f["properties"]
        code = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
        code = NE_FIX.get(code, code)
        if code in (None, "-99") or any(r["iso3"] == code for r in rows):
            continue
        rows.append({"iso3": code, "country": p["NAME"], "continent": p["CONTINENT"], "subregion": p["SUBREGION"],
                     "lon": round(p["LABEL_X"], 4), "lat": round(p["LABEL_Y"], 4)})
        g = shape(f["geometry"]).simplify(0.03, preserve_topology=True)
        if window is not None:
            g = g.intersection(window)
            if g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon"):
                continue
        gj = json.loads(json.dumps(mapping(g)), parse_float=lambda s: round(float(s), 3))
        feats.append({"type": "Feature", "properties": {"iso3": code, "name": p["NAME"]}, "geometry": gj})
    return pd.DataFrame(rows), {"type": "FeatureCollection", "features": feats}


def world_bank(ind: str, year: int = 2024) -> pd.Series:
    """Value for `year`, or the latest earlier year available (2015 or later)."""
    j = json.loads((DL / f"wb_{ind}.json").read_text(encoding="utf-8-sig"))[1]
    df = pd.DataFrame([{"iso3": r["countryiso3code"], "year": int(r["date"]), "v": r["value"]} for r in j])
    df = df[(df.v.notna()) & (df.year <= year) & (df.iso3 != "")].sort_values("year")
    return df.groupby("iso3").v.last()


def unhcr(coo: str, year: int) -> pd.DataFrame:
    j = json.loads((DL / f"unhcr_{coo.lower()}_{year}.json").read_text(encoding="utf-8-sig"))
    df = pd.DataFrame(j["items"])
    for c in ("refugees", "asylum_seekers"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df[["coa_iso", "coa_name", "refugees", "asylum_seekers"]].rename(columns={"coa_iso": "iso3"})


def refugee_case(coo: str, coo_name: str, years: list, main_year: int, folder: str, proj: dict) -> None:
    """Files: flows_<name>_refugees_<year>.csv, nodes_countries.csv (also the region attribute table),
    regions_<area>.geojson, table_receiving_countries_<year>.csv, flowmapper_<name>_refugees_<year>.json/.png"""
    print(f"\n== {coo_name} refugees -> {folder}/")
    slug = coo_name.lower()
    countries, regions = load_countries(proj.get("clip"))
    attrs = countries.copy()
    attrs["population_2024"] = attrs.iso3.map(world_bank("SP.POP.TOTL")).round(0)
    attrs["gdp_per_capita_usd_2024"] = attrs.iso3.map(world_bank("NY.GDP.PCAP.CD")).round(0)
    attrs["gdp_billion_usd_2024"] = (attrs.iso3.map(world_bank("NY.GDP.MKTP.CD")) / 1e9).round(1)
    attrs["migrant_stock_pct_2024"] = attrs.iso3.map(world_bank("SM.POP.TOTL.ZS")).round(1)
    known = set(countries.iso3)
    for y in years:
        u = unhcr(coo, y)
        missing = u[~u.iso3.isin(known)]
        if len(missing):
            print(f"  {y}: no map location for {missing.coa_name.tolist()} ({missing.refugees.sum()} refugees) - left out")
        u = u[u.iso3.isin(known) & (u.iso3 != coo)]
        attrs[f"refugees_{y}"] = attrs.iso3.map(u.set_index("iso3").refugees)
        flows = u[u.refugees > 0].copy()
        flows.insert(0, "origin", coo)
        flows = flows.rename(columns={"iso3": "destination", "coa_name": "destination_name"})
        flows = flows[["origin", "destination", "destination_name", "refugees", "asylum_seekers"]]
        write_csv(flows.sort_values("refugees", ascending=False), OUT / folder / f"flows_{slug}_refugees_{y}.csv")
    m = f"refugees_{main_year}"
    attrs[f"refugees_per_1000_pop_{main_year}"] = (attrs[m] / attrs.population_2024 * 1000).round(2)
    attrs[f"share_of_all_{coo.lower()}_refugees_pct_{main_year}"] = (attrs[m] / attrs[m].sum() * 100).round(2)
    for c in ["population_2024", "gdp_per_capita_usd_2024"] + [f"refugees_{y}" for y in years]:
        attrs[c] = attrs[c].round(0).astype("Int64")  # whole numbers in the CSV, blanks for missing
    attrs = attrs.astype(object).where(attrs.notna(), "")
    write_csv(attrs, OUT / folder / "nodes_countries.csv")
    (OUT / folder / f"regions_{proj['region_name']}.geojson").write_text(json.dumps(regions), encoding="utf-8")
    print(f"  wrote {folder}/regions_{proj['region_name']}.geojson ({len(regions['features'])} countries)")
    # Compact "student table" for receiving countries with at least 1,000 refugees
    tab = attrs[pd.to_numeric(attrs[m], errors="coerce").fillna(0) >= 1000].copy()
    tab = tab.sort_values(m, key=lambda s: pd.to_numeric(s), ascending=False)
    write_csv(tab.drop(columns=["lon", "lat", "continent"]), OUT / folder / f"table_receiving_countries_{main_year}.csv")

    for y in years:
        if y not in proj.get("project_years", [main_year]):
            continue
        flows = pd.read_csv(OUT / folder / f"flows_{slug}_refugees_{y}.csv", dtype=str)
        p = fm.Project.from_data(attrs.astype(str), flows, node_id="iso3", x="lon", y="lat",
                                 origin="origin", destination="destination", volume="refugees",
                                 name=f"{coo_name} refugees {y}")
        p.regions = regions
        p.region_table = attrs.astype(str)
        value = f"refugees_per_1000_pop_{main_year}" if y == main_year else f"refugees_{y}"
        p.region_join.update(CSVId="iso3", geoId="iso3", value=value)
        if y == main_year and proj.get("breaks"):
            p.region_settings.update(cfMethod="ManualBreak", breakInput=proj["breaks"],
                                     clsNum=len(proj["breaks"].split()) - 1)
        else:
            p.region_settings.update(cfMethod="NaturalBreak", clsNum=5)
        p.region_settings.update(clrScheme="Oranges", fillOpacity=85,
                                 strokeColor="#ffffff", strokeWidth=0.4, ifMapRegionAttribute=True, attrSource="csv",
                                 decimalPlaces=1 if y == main_year else 0, fillColorNoAttr="#e0e0e0",
                                 legendTitle=(f"{coo_name} refugees per 1,000 residents ({y})" if y == main_year
                                              else f"{coo_name} refugees ({y})"))
        p.node_settings.update(volume=f"refugees_{main_year}", ifMapAttribute=False, noAttrRadius=3, noAttrFillColor="#333333",
                               showNoFlowNodes=False, strokeWidth=0)
        p.flow_settings.update(flowStyleName="nyt", cfMethod="Proportional", clrScheme="Custom",
                               minCustomColor="#1d4f7a", maxCustomColor="#08203a", widthMin=1, widthMax=20,
                               numTopFlows=proj.get("top", 40), fillOpacity=90, strokeWidth=0.3,
                               legendTitle=f"Refugees from {coo_name}, end of {y} (UNHCR)")
        p.basemap_settings.update(projection=proj["projection"], baseMap="esriLightGray", ifAddTitle=True,
                                  title=f"Refugees from {coo_name}, end of {y}", titleSize=24,
                                  ifAddNorthArrow=False, ifAddProjectionLabel=True)
        dst = OUT / folder / f"flowmapper_{slug}_refugees_{y}.json"
        p.save(dst, indent=None)
        print(f"  wrote {dst.relative_to(OUT)}")
        try:
            p.save_map(dst.with_suffix(".png"), width=1400, height=1000, dpi=110)
            print(f"  wrote {dst.with_suffix('.png').relative_to(OUT)}")
        except Exception as e:  # preview only
            print(f"  (preview not rendered: {e})")


# ======================================================================================
# Part 2. Disaster displacement from IRS county-to-county migration data
# ======================================================================================

def gazetteer(year: int) -> pd.DataFrame:
    f = DL / "gaz" / ("g2010/Gaz_counties_national.txt" if year == 2010 else "g2019/2019_Gaz_counties_national.txt")
    g = pd.read_csv(f, sep="\t", dtype={"GEOID": str}, encoding="latin1")
    g.columns = [c.strip() for c in g.columns]
    return pd.DataFrame({"fips": g.GEOID.str.zfill(5), "county": g.NAME, "state": g.USPS,
                         "lon": g.INTPTLONG.astype(float).round(5), "lat": g.INTPTLAT.astype(float).round(5)})


def irs_xls(path: Path, direction: str) -> pd.DataFrame:
    """Old (2004-2008) IRS county files. Returns home_fips (the file's county), other_fips, households, persons, agi."""
    import xlrd
    sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
    out = []
    for r in range(sh.nrows):
        v = sh.row_values(r)
        try:
            s1, c1, s2, c2 = (str(x).split(".")[0] for x in v[:4])
            n1, n2, agi = float(v[6]), float(v[7]), float(v[8])
        except (ValueError, TypeError):
            continue
        if not (s1.isdigit() and s2.isdigit()) or c1 == "000" or int(s2) > 56 or c2 == "000":
            continue
        home, other = s1.zfill(2) + c1.zfill(3), s2.zfill(2) + c2.zfill(3)
        if home == other:  # non-migrants
            continue
        out.append({"home": home, "other": other, "households": int(n1), "persons": int(n2), "agi_thousand_usd": int(agi)})
    return pd.DataFrame(out)


def irs_csv_outflows(period: str) -> pd.DataFrame:
    d = pd.read_csv(DL / "irs" / f"countyoutflow{period}.csv", encoding="latin1")
    d = d[(d.y2_statefips <= 56) & (d.y2_countyfips > 0) & (d.y1_countyfips > 0)]
    home = d.y1_statefips.astype(str).str.zfill(2) + d.y1_countyfips.astype(str).str.zfill(3)
    other = d.y2_statefips.astype(str).str.zfill(2) + d.y2_countyfips.astype(str).str.zfill(3)
    out = pd.DataFrame({"home": home, "other": other, "households": d.n1, "persons": d.n2, "agi_thousand_usd": d.agi})
    return out[out.home != out.other]


def state_choropleth_table(flows_by_period: dict, prefix: str, key: str = "destination") -> pd.DataFrame:
    """Persons per state: by destination state (outflows) or origin state (inflows, key='origin')."""
    t = pd.DataFrame({"name": sorted(STATE_FIPS.values())})
    for per, f in flows_by_period.items():
        s = f.groupby(f[key].str[:2]).persons.sum()
        s.index = s.index.map(STATE_FIPS)
        t[f"{prefix}_{per}"] = t.name.map(s).fillna(0).astype(int)
    return t

def lower48_states() -> dict:
    """FlowMapper's built-in U.S. states without Alaska, Hawaii and Puerto Rico (the map opens on the lower 48)."""
    states = json.loads(US_STATES.read_text(encoding="utf-8"))
    states["features"] = [f for f in states["features"]
                          if f["properties"]["name"] not in ("Alaska", "Hawaii", "Puerto Rico")]
    return states


def write_lower48(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "regions_us_states.geojson").write_text(json.dumps(lower48_states()), encoding="utf-8")
    print(f"  wrote {(folder / 'regions_us_states.geojson').relative_to(OUT)}")


def disaster_project(flows: pd.DataFrame, nodes: pd.DataFrame, state_tab: pd.DataFrame, value: str, title: str,
                     legend_flow: str, legend_region: str, dst: Path, flow_breaks: str, region_breaks: str,
                     top: int = 150) -> None:
    """Fixed (manual) breaks so that maps of different periods are directly comparable."""
    used = set(flows.origin) | set(flows.destination)
    n = nodes[nodes.fips.isin(used)]
    p = fm.Project.from_data(n.astype(str), flows.astype(str), node_id="fips", x="lon", y="lat",
                             origin="origin", destination="destination", volume="persons", name=title)
    p.regions = lower48_states()
    p.region_table = state_tab.astype(str)
    p.region_join.update(CSVId="name", geoId="name", value=value)
    p.region_settings.update(cfMethod="ManualBreak", breakInput=region_breaks, clrScheme="Purples",
                             clsNum=len(region_breaks.split()) - 1, fillOpacity=75, strokeColor="#ffffff",
                             strokeWidth=0.5, ifMapRegionAttribute=True, attrSource="csv", legendTitle=legend_region)
    p.node_settings.update(volume="lat", ifMapAttribute=False, noAttrRadius=2, noAttrFillColor="#333333",
                           showNoFlowNodes=False, strokeWidth=0)
    p.flow_settings.update(flowStyleName="nyt", cfMethod="ManualBreak", breakInput=flow_breaks,
                           clsNum=len(flow_breaks.split()) - 1, clrScheme="Custom",
                           minCustomColor="#f4a259", maxCustomColor="#9b2226", widthMin=1, widthMax=16,
                           numTopFlows=top, fillOpacity=90, strokeWidth=0.3, legendTitle=legend_flow)
    p.basemap_settings.update(projection="abEqAreaUS", baseMap="esriLightGray", ifAddTitle=True, title=title,
                              titleSize=22)
    p.save(dst, indent=None)
    print(f"  wrote {dst.relative_to(OUT)}")
    try:
        p.save_map(dst.with_suffix(".png"), width=1400, height=900, dpi=110)
        print(f"  wrote {dst.with_suffix('.png').relative_to(OUT)}")
    except Exception as e:
        print(f"  (preview not rendered: {e})")


KATRINA = {"22071": "Orleans Parish, LA", "22051": "Jefferson Parish, LA", "22087": "St. Bernard Parish, LA",
           "22075": "Plaquemines Parish, LA", "22103": "St. Tammany Parish, LA", "28045": "Hancock County, MS",
           "28047": "Harrison County, MS", "28059": "Jackson County, MS"}
PERIODS = {"0405": "2004_05", "0506": "2005_06", "0607": "2006_07", "0708": "2007_08"}


def katrina() -> None:
    print("\n== Hurricane Katrina (IRS county-to-county, 2004-05 to 2007-08) -> DisasterMigration/Katrina/")
    folder = OUT / "DisasterMigration" / "Katrina"
    write_lower48(folder)
    nodes = gazetteer(2010)
    nodes["katrina_area"] = nodes.fips.isin(KATRINA).map({True: "yes", False: "no"})
    outs, ins, long = {}, {}, []
    for code, per in PERIODS.items():
        o, i = [], []
        for st in ("LA", "MS"):
            o.append(irs_xls(DL / "irs" / f"co{code}" / f"co{code}{st}o.xls", "out"))
            i.append(irs_xls(DL / "irs" / f"co{code}" / f"co{code}{st}i.xls", "in"))
        o = pd.concat(o)
        o = o[o.home.isin(KATRINA)].rename(columns={"home": "origin", "other": "destination"})
        i = pd.concat(i)
        i = i[i.home.isin(KATRINA)].rename(columns={"other": "origin", "home": "destination"})
        cols = ["origin", "destination", "households", "persons", "agi_thousand_usd"]
        o, i = o[cols].sort_values("persons", ascending=False), i[cols].sort_values("persons", ascending=False)
        miss = (set(o.destination) | set(i.origin)) - set(nodes.fips)
        if miss:
            print(f"  {per}: {len(miss)} county codes without a centroid (dropped): {sorted(miss)[:8]}")
            o, i = o[~o.destination.isin(miss)], i[~i.origin.isin(miss)]
        outs[per], ins[per] = o, i
        write_csv(o, folder / f"flows_katrina_out_{per}.csv")
        write_csv(i, folder / f"flows_katrina_in_{per}.csv")
        long.append(o.assign(period=per, direction="out"))
        long.append(i.assign(period=per, direction="in"))
    write_csv(pd.concat(long), folder / "flows_katrina_all_periods.csv")

    # Per-county summary for the 8 affected counties: out, in, net by period
    summ = []
    for f, nm in KATRINA.items():
        r = {"fips": f, "county": nm}
        for per in PERIODS.values():
            r[f"out_{per}"] = int(outs[per][outs[per].origin == f].persons.sum())
            r[f"in_{per}"] = int(ins[per][ins[per].destination == f].persons.sum())
            r[f"net_{per}"] = r[f"in_{per}"] - r[f"out_{per}"]
        summ.append(r)
    write_csv(pd.DataFrame(summ), folder / "summary_katrina_counties.csv")
    used = set().union(*[set(x.origin) | set(x.destination) for x in list(outs.values()) + list(ins.values())])
    write_csv(nodes[nodes.fips.isin(used)], folder / "nodes_counties.csv")
    st = state_choropleth_table(outs, "persons_from_katrina_area")
    st = st.merge(state_choropleth_table(ins, "persons_to_katrina_area", key="origin"), on="name")
    write_csv(st, folder / "regions_states_katrina_totals.csv")
    for per in ("2004_05", "2005_06"):
        lbl = per.replace("_", "-")
        disaster_project(outs[per], nodes, st, f"persons_from_katrina_area_{per}",
                         f"Out-migration from Katrina-affected counties, {lbl}",
                         f"Persons (tax exemptions), {lbl}", f"Persons received from affected area, {lbl}",
                         folder / f"flowmapper_katrina_out_{per}.json",
                         flow_breaks="10 100 500 2000 10000 30000", region_breaks="0 250 1000 5000 20000 100000")


def camp_fire() -> None:
    print("\n== Camp Fire, Butte County CA (IRS county outflows 2017-18 to 2019-20) -> DisasterMigration/CampFire/")
    folder = OUT / "DisasterMigration" / "CampFire"
    write_lower48(folder)
    nodes = gazetteer(2019)
    outs = {}
    for code, per in {"1718": "2017_18", "1819": "2018_19", "1920": "2019_20"}.items():
        o = irs_csv_outflows(code)
        o = o[o.home == "06007"].rename(columns={"home": "origin", "other": "destination"})
        o = o[["origin", "destination", "households", "persons", "agi_thousand_usd"]].sort_values("persons", ascending=False)
        o = o[o.destination.isin(nodes.fips)]
        outs[per] = o
        write_csv(o, folder / f"flows_butte_out_{per}.csv")
    used = set().union(*[set(x.origin) | set(x.destination) for x in outs.values()])
    write_csv(nodes[nodes.fips.isin(used)], folder / "nodes_counties.csv")
    st = state_choropleth_table(outs, "persons_from_butte")
    write_csv(st, folder / "regions_states_butte_totals.csv")
    for per in ("2017_18", "2018_19"):
        lbl = per.replace("_", "-")
        disaster_project(outs[per], nodes, st, f"persons_from_butte_{per}",
                         f"Out-migration from Butte County, CA, {lbl}", f"Persons, {lbl}",
                         f"Persons received from Butte County, {lbl}", folder / f"flowmapper_butte_out_{per}.json",
                         flow_breaks="10 50 100 250 500 1000", region_breaks="0 50 100 250 500 10000", top=100)


if __name__ == "__main__":
    refugee_case("UKR", "Ukraine", [2022, 2023, 2024], 2024, "Refugees/Ukraine",
                 {"region_name": "europe", "projection": "laeaEurope", "top": 40, "project_years": [2022, 2024],
                  "clip": (-25, 34, 50, 71.5), "breaks": "0 2 5 10 20 40 60"})
    refugee_case("SYR", "Syria", [2015, 2024], 2024, "Refugees/Syria",
                 {"region_name": "europe_mena", "projection": "abEqAreaEu", "top": 40, "project_years": [2015, 2024],
                  "clip": (-25, 12, 60, 71.5), "breaks": "0 1 5 10 50 100 200"})
    katrina()
    camp_fire()
