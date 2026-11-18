# Teaching with FlowMapper: refugee and disaster migration

Two ready-to-use assignments built on the datasets in this repository:

* **Undergraduate (for example, Population Geography): "Where did Ukraine's refugees go, and why there?"**
  Uses [Data/Refugees](../Data/Refugees/). One lab session, or a take-home assignment.
* **Graduate (for example, Hazards and Disasters): "Disaster displacement streams"**, a five-part project
  over 4–6 weeks. Uses [Data/DisasterMigration](../Data/DisasterMigration/) (Hurricane Katrina and the Camp
  Fire).

Every `flowmapper_*.json` file opens directly on [FlowMapper.org](https://flowmapper.org): **File > Project >
Load Project**. The `.png` next to it shows what the map should look like. The CSV and GeoJSON files are
there for students who build the maps themselves. The dataset READMEs describe every field and the
limitations of each source.

---

## Undergraduate exercise: "Where did Ukraine's refugees go, and why there?"

**Purpose.** Students often already make a table of refugee numbers with population, GDP and percent
foreign-born for the receiving countries. The map adds two things a table cannot show: **distance and
adjacency** (who borders Ukraine), and the difference between **absolute and relative** burden. Germany hosts
the most refugees from Ukraine (1.21 million). Moldova hosts the most per resident (56 per 1,000, against 14
in Germany).

**Files:** [Data/Refugees/Ukraine](../Data/Refugees/Ukraine/).

### Part A. Read a finished map (about 20 minutes)

1. Open `flowmapper_ukraine_refugees_2024.json` (File > Project > Load Project).
2. Hover over flows and countries to read values. Click Ukraine to show only its flows.
3. Questions:
   * Which five countries receive the largest flows? What do they have in common geographically?
   * Which countries have the highest refugees per 1,000 residents? Are they the same countries as in the
     previous question? Why not?
   * Find one country with a large flow but a light shade, and one with a small flow but a dark shade.
     Explain each.

### Part B. Build the map yourself (about 30 minutes)

Starting from a blank FlowMapper page teaches the node/flow/region logic that every flow map uses:

1. **Nodes tab:** load `nodes_countries.csv`. ID = `iso3`, X = `lon`, Y = `lat`.
2. **Flows tab:** load `flows_ukraine_refugees_2024.csv`. Origin = `origin`, Destination = `destination`,
   Volume = `refugees`. Map it.
3. **Regions tab:** load `regions_europe.geojson`, tick *Map region attribute*, join a CSV file
   (`nodes_countries.csv`), Polygon ID = `iso3`, CSV ID = `iso3`.
4. **Base Map tab:** set the projection to *Lambert Azimuthal Europe*.
5. Try different numbers of top flows, flow styles and classification methods (Proportional against Natural
   Breaks). Write two sentences on how each choice changes the story the map tells.

### Part C. Explain the pattern with the receiving-country attributes (about 30 minutes)

Make three versions of the region shading: `gdp_per_capita_usd_2024`, `migrant_stock_pct_2024` and
`refugees_per_1000_pop_2024`. Keep the flows on top.

* Do refugees go mainly to rich countries, to nearby countries, or to countries that already have many
  immigrants? Use the maps and `table_receiving_countries_2024.csv` to support the answer. (Poland and
  Czechia score high on proximity and per-capita intake, but have low foreign-born shares. Ireland and Norway
  are wealthy, high-immigration countries.)
* Optional numeric step: in a spreadsheet, correlate `refugees_per_1000_pop_2024` with each attribute.

### Part D. Change over time (optional, about 20 minutes)

Open `flowmapper_ukraine_refugees_2022.json` next to the 2024 map, or map `flows_ukraine_refugees_2022.csv`
yourself. Total refugees fell from 5.68 million (2022) to 5.12 million (2024), but the map changed more than
that number suggests:

* **The Russian Federation** reports 1.28 million in 2022 and about 7,000 in 2024. Ask students whether this
  is a real change or a change in reporting. It is a good opening for a discussion of data reliability.
* Which western European countries grew between 2022 and 2024 (Germany, Spain, Romania, Ireland, Norway), and
  which near neighbours shrank (Czechia, Lithuania, Montenegro)?

### Data-literacy points worth making

* **Who counts as a "refugee".** UNHCR includes people under the EU's Temporary Protection. The United States
  admitted most Ukrainians through humanitarian parole (Uniting for Ukraine), so the U.S. shows only 3,397
  refugees. Canada's 75,000 do appear, which explains the single long arrow to North America.
* **Stocks against flows.** These are numbers of people *present* at year end, mapped as if they were flows.
  Ask students what a true flow (arrivals per year) would look like, and why secondary movement (Poland to
  Germany, for example) is invisible here.
* **Percent foreign-born.** `migrant_stock_pct_2024` is the UN DESA international migrant stock. It counts
  foreign-born people where birthplace data exist, and foreign citizens elsewhere.

### Syria variant

Use [Data/Refugees/Syria](../Data/Refugees/Syria/) with the same steps (polygons:
`regions_europe_mena.geojson`; projection: *Albers Equal Area Europe*). That case is mainly about
neighbouring countries: Turkey has 2.9 million, and Lebanon has 130 refugees per 1,000 residents. Germany's
intake grew from 116,000 (2015) to 725,000 (2024). Comparing Syria with Ukraine is an effective final
question: why did one crisis produce a regional pattern and the other a continental one?

---

## Graduate project: "Disaster displacement streams", in five parts

The project runs over 4–6 weeks. Each part produces a deliverable, and the parts add up to a final paper or
story map. Katrina is the common case for everyone. Each student (or group) then adds a comparison case.

**Files:** [Data/DisasterMigration](../Data/DisasterMigration/).

### Part 1. Data biography (week 1)

Before any mapping, students write a 2-page "data biography" for the IRS county-to-county migration data and
compare it with one other displacement source (UNHCR, IDMC's Global Internal Displacement Database, FEMA
registrations or the ACS). They should cover:

* **Who is counted:** only tax filers and their dependents. Low-income, elderly non-filers and undocumented
  residents are under-counted, and these are often the people most exposed to disasters.
* **When:** a "year" compares addresses on returns filed in consecutive springs. 2005–06 captures moves
  between spring 2005 and spring 2006, so it includes Katrina (August 2005).
* **Scale:** moves *within* a county are invisible. County flows below about 10 returns are grouped into
  "Other flows" and are not included in these files.

### Part 2. Baseline against shock (week 2)

Open `Katrina/flowmapper_katrina_out_2004_05.json` and `Katrina/flowmapper_katrina_out_2005_06.json`. They
use the same class breaks, so the maps are directly comparable.

* Describe the change in volume, distance and direction. Orleans Parish sent 19,491 people elsewhere in
  2004–05 and **139,467** in 2005–06.
* Main destinations: Houston (Harris County, TX: 28,106 people from Orleans alone), Baton Rouge, Dallas,
  Atlanta, and a long tail to California and Chicago. Why these places? Possible explanations include
  distance, evacuation routes, FEMA and shelter placement, kin networks and the size of the receiving labour
  market.
* **Analytical step: excess migration.** In a spreadsheet, join `flows_katrina_out_2004_05.csv` and
  `flows_katrina_out_2005_06.csv` on origin and destination, compute
  `excess = persons_2005_06 - persons_2004_05`, and map the excess as the flow volume. This separates the
  disaster signal from normal churn.

### Part 3. Return, replacement and selectivity (week 3)

Use the `flows_katrina_in_*.csv` files and `summary_katrina_counties.csv`.

* Map inflows into the affected counties in 2006–07 and 2007–08. Who came back, and from where? Orleans
  inflows rose from 6,177 (2005–06) to 33,796 (2006–07).
* Plot net migration by county and year from the summary table. Which places recovered? St. Tammany gained
  population every year (suburban relocation inside the region). St. Bernard lost 26,383 people (net) in
  2005–06, against 171 people moving in, and then gained about 2,000–2,700 a year.
* Selectivity: compare `agi_thousand_usd / households` for movers to Houston and movers to suburban parishes.
  Was displacement uneven by income?

### Part 4. Comparative case (weeks 4–5)

Each student chooses one:

* **Camp Fire, 2018 (provided):** [DisasterMigration/CampFire](../Data/DisasterMigration/CampFire/).
  Out-migration from Butte County rose only from 8,119 to 11,301 people, although Paradise (about 27,000
  residents) was largely destroyed. Students should find the reason: much of the displacement stayed
  *within* Butte County (Chico, Oroville), which county-level data cannot see. This is a direct lesson in the
  modifiable areal unit problem.
* **A disaster of their choice, using IRS data**
  ([irs.gov/statistics/soi-tax-stats-migration-data](https://www.irs.gov/statistics/soi-tax-stats-migration-data)):
  for example, Hurricane Harvey 2017 (Harris County, TX), Hurricane Michael 2018 (Bay County, FL), the 2021
  Marshall Fire (Boulder County, CO) or Hurricane Ian 2022 (Lee County, FL).
  [`Data/scripts/build_refugee_disaster_data.py`](../Data/scripts/) shows how to turn the IRS
  `countyoutflowYYYY.csv` files into FlowMapper inputs. Changing the county FIPS code in `camp_fire()` is
  enough.
* **Conflict against disaster:** compare the Katrina stream with the [Ukraine or Syria refugee
  data](../Data/Refugees/). How do distance decay, the role of borders and the share of people who return
  differ?
* **Hurricane Maria 2017 (Puerto Rico to the U.S. mainland):** the IRS data do not cover Puerto Rico well.
  Use the ACS state-to-state migration flow tables instead, which makes this a good extension for a student
  with stronger data skills.

### Part 5. Synthesis (week 6)

A 3,000-word paper, or a story map with 4–6 maps exported from FlowMapper (File > Export), that answers:

> What determines where disaster-displaced people go, how long they stay, and what do our data sources hide?

Suggested grading: data biography 15%, baseline/shock analysis 20%, return and selectivity 20%, comparative
case 20%, synthesis 25%. Map design (consistent classes, honest legends, an appropriate projection and
number of top flows) can be graded within each part.
