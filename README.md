# FlowMapper

[FlowMapper.org](https://flowmapper.org) is a web application for designing origin-destination flow maps. This repository holds its example data, teaching materials and its Python package.

## Python package

[`python/`](python/) is **flowmapper.org**, the Python companion to FlowMapper.org: read, analyse, map and write FlowMapper project files. A project built in Python opens on FlowMapper.org, and every project saved there loads in Python.

```bash
pip install flowmapper.org
```
```python
import flowmapper_org as fm
p = fm.Project.load("Data/Refugees/Ukraine/flowmapper_ukraine_refugees_2022.json")
p.save_map("map.png")
```

The [example notebooks](python/notebooks/) use the data in this repository; start with `00_parameters_guide`. See the [package README](python/README.md) for everything else.

## Web application

The front end of FlowMapper.org is built with HTML, CSS, JavaScript and the Bootstrap template. OpenLayers is used for the mapping framework including the base maps and basic interactive map functions, and D3 (Data-Driven Documents) (Bostock, Ogievetsky, & Heer, 2011) is used to create the interactive maps that include polygon, point and flow symbol vectors. FlowMapper utilizes a Java back-end design connected with a PostgreSQL/PostGIS database with an Apache Tomcat server. The web application's source code is no longer published in this repository.

## Data
The data used in the FlowMapper paper is published here, together with newer example datasets. The datasets included are as follows:

* [Banana food flows](Data/Bananas/): Banana food flows within South America from 2019 (FAO, 2021).
* [Family tree flows](Data/FamilyTree/): Family tree data movement from 1887-1924 within the U.S. (Koylu et al., 2020)
* [Bikeshare flows](Data/Bikeshare): Bikeshare flows within Chicago from April 2021 (Divvy system data, 2021).
* [Migration flows](Data/Migration): Internal Migration flows between 2005 and 2010 across various continents (WHO, 2015).
* [Refugee flows](Data/Refugees/): Refugees from Ukraine (2022–2024) and Syria (2015, 2024) by country of asylum, with population, GDP and percent foreign-born of every country (UNHCR, 2026; World Bank, 2026).
* [Disaster migration](Data/DisasterMigration/): County-to-county migration before, during and after Hurricane Katrina (2004–2008) and the Camp Fire in Butte County, California (2017–2020) (IRS, 2026).

Most dataset folders follow the same naming: `flowmapper_*.json` is a FlowMapper project file (open it with **File > Project > Load Project**), `flowmapper_*.png` is a picture of that map, and `flows_*`, `nodes_*` and `regions_*` are the input files for flows, nodes and regions. The scripts that build the newer datasets are in [Data/scripts](Data/scripts/).

## Teaching
[Teaching](Teaching/) has two ready-to-use assignments built on these data: an undergraduate exercise on refugee flows from Ukraine (with a Syria variant), and a five-part graduate project on migration after disasters.

## About
FlowMapper is an interactive application for mapping geospatial data that include flows, or origin-destination data. In FlowMapper, upload regions (polygons) as a geojson, a region attribute dataset (csv), a node dataset (csv) that includes coordinates in WGS84, and a flow dataset (csv). For the regions, the geojson data should have an ID that joins to the region attribute dataset, and the flows should have an origin ID field and a destination ID field that join to the nodes dataset on a matching ID.

Regions can be symbolized through a classification scheme, color scheme, opacity, and stroke width and color. Nodes can be symbolized through scaling, fill color, opacity, radius sizing, and stroke color and width. Flows can be symbolized by the number of flows shown, flow line style, classification scheme, color scheme, opacity, and stroke width and color.

For regions, nodes, and flows, the legend can be formatted by title and the number of decimal places. FlowMapper also includes base map and map projection options.

After the flow map is created, the flow map visualization can be exported as a SVG or PNG and the project itself can be saved as a JSON to be imported again at a later time.

## Contact Us
If you have questions about the data formatting or processing, please contact us at:

geo-social@uiowa.edu

## Contributors

By Caglar Koylu, Geng Tian, and Mary Windsor

## References
* Koylu, C., Tian, G., & Windsor, M. (2022). FlowMapper.org: A web-based framework for designing origin-destination flow maps. Journal of Maps. doi:10.1080/17445647.2021.1996479

* Divvy system data. Retrieved May 13, 2021, from https://www.divvybikes.com/system-data

* FAO. (2021). Food and Agriculture Organization of United Nations (FAO). Retrieved from http://www.fao.org/faostat/en/#data/TM

* Koylu, C., Guo, D., Huang, Y., Kasakoff, A., & Grieve, J. (2020). Connecting family trees to construct a population-scale and longitudinal geo-social network for the U.S. International Journal of Geographical Information Science. doi:10.1080/13658816.2020.1821885

* IRS. (2026). SOI Tax Stats: Migration Data, county-to-county files 2004–2008 and 2017–2020. Internal Revenue Service, Statistics of Income. Retrieved November 2026, from https://www.irs.gov/statistics/soi-tax-stats-migration-data

* UNHCR. (2026). Refugee Data Finder. United Nations High Commissioner for Refugees. Retrieved November 2026, from https://www.unhcr.org/refugee-statistics/

* World Bank. (2026). World Development Indicators. Retrieved November 2026, from https://databank.worldbank.org/source/world-development-indicators

* Natural Earth. 1:50m Cultural Vectors, Admin 0 – Countries. Retrieved November 2026, from https://www.naturalearthdata.com/

* U.S. Census Bureau. Gazetteer Files, counties 2010 and 2019. Retrieved November 2026, from https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html


