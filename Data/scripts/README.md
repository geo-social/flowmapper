# Data scripts

## `build_refugee_disaster_data.py`

Builds [Data/Refugees](../Refugees/) and [Data/DisasterMigration](../DisasterMigration/): the flow, node and
region files, the FlowMapper project files and their PNG previews.

### 1. Download the raw data into one folder

All sources are public and need no login. In PowerShell (`$d` is the download folder):

```powershell
$d = "C:\temp\flowmapper_raw"; New-Item -ItemType Directory -Force "$d\irs", "$d\gaz" | Out-Null

# UNHCR refugees by country of asylum
foreach ($c in "UKR", "SYR") { foreach ($y in 2015, 2022, 2023, 2024) {
  Invoke-WebRequest "https://api.unhcr.org/population/v1/population/?limit=1000&yearFrom=$y&yearTo=$y&coo=$c&coa_all=true" `
    -OutFile "$d\unhcr_$($c.ToLower())_$y.json" } }

# World Bank indicators
foreach ($i in "SP.POP.TOTL", "NY.GDP.PCAP.CD", "NY.GDP.MKTP.CD", "SM.POP.TOTL.ZS") {
  Invoke-WebRequest "https://api.worldbank.org/v2/country/all/indicator/${i}?format=json&per_page=20000&date=2015:2025" `
    -OutFile "$d\wb_$i.json" }

# Natural Earth countries
Invoke-WebRequest "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson" `
  -OutFile "$d\ne_50m_countries.geojson"

# IRS county-to-county migration
foreach ($y in "0405", "0506", "0607", "0708") { Invoke-WebRequest "https://www.irs.gov/pub/irs-soi/county$y.zip" -OutFile "$d\irs\county$y.zip" }
foreach ($y in "1718", "1819", "1920") { Invoke-WebRequest "https://www.irs.gov/pub/irs-soi/countyoutflow$y.csv" -OutFile "$d\irs\countyoutflow$y.csv" }

# Census Gazetteer county centroids
Invoke-WebRequest "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_counties_national.zip" -OutFile "$d\gaz\gaz2010.zip"
Invoke-WebRequest "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2019_Gazetteer/2019_Gaz_counties_national.zip" -OutFile "$d\gaz\gaz2019.zip"
Expand-Archive "$d\gaz\gaz2010.zip" "$d\gaz\g2010"; Expand-Archive "$d\gaz\gaz2019.zip" "$d\gaz\g2019"
```

From each `irs\county<yy>.zip`, extract the Louisiana and Mississippi in- and outflow files into
`irs\co<yy>\`, named `co<yy>LAi.xls`, `co<yy>LAo.xls`, `co<yy>MSi.xls` and `co<yy>MSo.xls`. The 2007–08 zip
names them `co0708iLa.xls` and so on, so rename those.

### 2. Run

```bash
pip install pandas shapely xlrd
python Data/scripts/build_refugee_disaster_data.py C:\temp\flowmapper_raw
```

The script also needs the `flowmapper` Python package, which writes FlowMapper project files and renders the
previews. To add a new year (for example UNHCR end-of-2025 figures), download it, add the year to the
`refugee_case(...)` calls at the bottom of the script, and run it again. To study another disaster, copy
`camp_fire()` and change the county FIPS code and the IRS years.
