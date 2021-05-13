# FlowMapper Data

The data used in the FlowMapper paper is published here. The datasets included are as follows:

* [Banana food flows](Bananas/): Banana food flows within South America from 2019 (FAO, 2021).
* [Family tree flows](Family-tree/): Family tree data movement from 1887-1924 within the U.S. (Koylu et al., 2020)
* [Bikeshare flows](Bikeshare): Bikeshare flows within Chicago from April 2021 (Divvy system data, 2021).

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
* Divvy system data. Retrieved May 13, 2021, from https://www.divvybikes.com/system-data

* FAO. (2021). Food and Agriculture Organization of United Nations (FAO). Retrieved from http://www.fao.org/faostat/en/#data/TM

* Koylu, C., Guo, D., Huang, Y., Kasakoff, A., & Grieve, J. (2020). Connecting family trees to construct a         population-scale and longitudinal geo-social network for the U.S. International Journal of Geographical Information Science. doi:10.1080/13658816.2020.1821885

* Koylu, C., Tian, G., & Windsor, M. In Review
