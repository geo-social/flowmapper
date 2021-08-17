var map;
var onlineLayer ;
var referenceLayer = new ol.layer.Tile();
var otherTerrainLayer = new ol.layer.Tile();

var baseMapData;
var flowData;
var pointData;
var CPMData;
var refData;

// The CSV values for the Choropleth map. 
var CPMValue;
// The hash map from id to the CSV value of Choropleth map.
var CPMIdValueMap;

//var path = d3.geoPath().projection(projection);
var svg_user_painting = d3.selectAll("#UserOverlay").append("svg").attr("id", "svg_user_painting")
.attr("width", window.innerWidth)
.attr("height", window.innerHeight);

var flowSVGId = "svg_FlowLegend";
var pointSVGId = "svg_PointLegend";
var CPMSVGId = "svg_CPMLegend";

var svg_FlowLegend = d3.select("#Legend")
.append("svg")
.attr("id", flowSVGId)
.style("display", "none");

var svg_PointLegend = d3.select("#Legend")
.append("svg")
.attr("id", pointSVGId)
.style("display", "none");

var svg_CPMLegend = d3.select("#Legend")
.append("svg")
.attr("id", CPMSVGId)
.style("display", "none"); 

var gRef = svg_user_painting.append("g");

// Group of d3 for choropleth map
var g1 = svg_user_painting.append("g");
// Group of d3 for flows
var g3 = svg_user_painting.append("g");
// Group of d3 for points
var g2 = svg_user_painting.append("g");

var gTitle= svg_user_painting.append("g");

var gNA = svg_user_painting.append("g");

var gPrj = svg_user_painting.append("g");

var CPMBound = [[20037508.34, 20037508.34], [-20037508.34, -20037508.34]];
var flowBound = [[20037508.34, 20037508.34], [-20037508.34, -20037508.34]];
var pointBound = [[20037508.34, 20037508.34], [-20037508.34, -20037508.34]];

var markerDefs = null;

// Classification method applied on points
var pointScale;
var flowWidthScale;

var linksByOrigin = {},
// Location of node by (x, y) coordinate
countByNodeID = {},
locationByNodeID = {},
volumeByNodeID = {},
inflowByNodeID = {},
outflowByNodeID = {},
nodeFlowAttributeArr=[],
positions = [],
volumearr = [],
topVolumeList = [],
topVolumeList_modified = [],
topLinks = [];

// Only show flows which are greater than threshold 
var flowthreshold = Number.MIN_SAFE_INTEGER;
// Normalize the scale to positive numbers
var nodesizeattribute = [],
nodesizeattribute_modified = [];

// # of maximum top links
const maxNumOfTopLinks = 1000;

// Initial base map object
var baseMap = {
		projection: null,
		zoom: 5.3,
		center: [-96, 39],
		overlay: null,
		extent: [-180, -180, 180, 180],
		control: null,
		panInteraction: null,
		zoomControl: null,
		scaleControl: null,
};

var baseMapSettings = {
		// Inputs for base map.
		baseMap: document.getElementById("Online_BaseMap-Select").value,
		projection: document.getElementById("MapProjection-Select").value,
		ifDisplayReferences: $("#DisplayMapReference-CB").is(":checked"),
		baseMapOpacity: +document.getElementById("CPM_BaseMapOpacity-Input").value,
		ifAddTitle: $("#AddTitle-CB").is(":checked"),
		title: document.getElementById("MapTitle-Input").value,
		ifAddNorthArrow: $("#AddNorthArrow-CB").is(":checked"),
		ifAddProjectionLabel: $("#AddProjectionLabel-CB").is(":checked"),
		
		// Reference:
		ifUploadReferences: $("#UploadReference-CB").is(":checked"),
		referenceField: document.getElementById("BaseMap_Reference-Select").value,
		labelFontSize: document.getElementById("BaseMap_LabelFontSize-Input").value,
		refRadius: document.getElementById("BaseMap_LabelRadius-Input").value,
		refColor: document.getElementById("BaseMap_LabelColor-Input").value,
		refOpacity: +document.getElementById("BaseMap_LabelOpacity-Input").value,
		ifRefTop: $("#BaseMap_LebelTop-CB").is(":checked"),
		
		// Inputs for choroplethMap
		cfMethod: document.getElementById("CPM_Classification-Select").value, // Classification method.
		clrScheme: document.getElementById("CPM_ColorScheme-Select").value, // Color scheme.
		minCustomColor: document.getElementById("CPM_MinCustomColor-Input").value,
		maxCustomColor: document.getElementById("CPM_MaxCustomColor-Input").value,
		ifFlipColor: $("#CPM_FlipLgClr-CB").is(":checked"), // If to flip the color.
		decimalPlaces: $("#CPM_LegendDP-Input").val(),
		clsNum: document.getElementById("CPM_ClassNum-Input").value, // Number of classes
		fillOpacity: document.getElementById("CPM_FillOpacity-Input").value,
		strokeColor: document.getElementById("CPM_StrokeColor-Input").value,
		strokeWidth: +document.getElementById("CPM_StrokeWidth-Input").value,
		legendTitle: document.getElementById('CPM_LegendTitle-Input').value,
		breakInput: document.getElementById("CPM_ManualBreak-Input").value, // Input for manual break.
		ifHideNull: $("#CPM_DisplayNull-CB").is(":checked"), // If to display null values.
		
		// Inputs for CSV data.
		CSVId: $("#CPM_CSVPK-Select option:selected").text(), // ID for the CSV.
		geoId: $("#CPM_BMPK-Select option:selected").text(), // ID for the base map polygons.
		value: $("#CPM_Value-Select option:selected").text(), // Input for the value field from CSV data.
		
		// Legend settings:
		titleWidth: 150,
		
		// Status:
		hasNewData: false,
		numFeatures: 0,
		numJoint: 0,
		numDisjoint: 0,
		areNewFilesLoaded: false,
		breakArray: null
};

var pointMapSettings = {
		id: document.getElementById("Point_ID-Select").value,
		X: document.getElementById("Point_X-Select").value,
		Y: document.getElementById("Point_Y-Select").value,
		volume: document.getElementById("Point_Volume-Select").value,
		ifMapAttribute: $("#Point_MapAttribute-CB").is(":checked"),
		cfMethod: document.getElementById("Point_Classification-Select").value, // Scaling for size.
		clsNum: +document.getElementById("Point_ClassNum-Input").value,
		clrScheme: document.getElementById("Point_ColorScheme-Select").value, // Node fill-color.
		minCustomColor: document.getElementById("Point_MinCustomColor-Input").value,
		maxCustomColor: document.getElementById("Point_MaxCustomColor-Input").value,
		noAttrFillColor: document.getElementById("Point_FillColor_NoAttr-Input").value,
		fillOpacity: document.getElementById("Point_FillOpacity-Input").value,
		radiusMin: +document.getElementById("Point_Radius_Min-Input").value,
		radiusMax: +document.getElementById("Point_Radius_Max-Input").value,
		strokeColor: document.getElementById("Point_StrokeColor-Input").value,
		ifFlipColor: $("#Point_FlipLgClr-CB").is(":checked"),
		strokeWidth: +document.getElementById("Point_StrokeWidth-Input").value,
		decimalPlaces: +document.getElementById('Point_LegendDP-Input').value,
		legendTitle: document.getElementById('Point_LegendTitle-Input').value,
		breakInput: document.getElementById("Point_ManualBreak-Input").value,
		isDisplayedAsAbs: $("#Point_DisplayAsAbs-CB").is(":checked"), // Display as absolute (it is temporarily hidden from the interface).
		
		// Legend settings:
		titleWidth: 150,
		
		// Status:
		hasNewData: false,
		breakArray: null
};

var flowMapSettings = {
		origin: document.getElementById("Flow_SourceID-Select").value,
		destination: document.getElementById("Flow_TargetID-Select").value,
		volume: document.getElementById("Flow_Volume-Select").value,
		flowStyleName: document.getElementById("Flow_Style-Select").value, // Name of flow style.
		cfMethod: document.getElementById("Flow_Classification-Select").value,
		clrScheme: document.getElementById("Flow_ColorScheme-Select").value,
		minCustomColor: document.getElementById("Flow_MinCustomColor-Input").value,
		maxCustomColor: document.getElementById("Flow_MaxCustomColor-Input").value,
		fillOpacity: document.getElementById("Flow_FillOpacity-Input").value,
		ifFlipColor: $("#Flow_FlipLgClr-CB").is(":checked"),
		decimalPlaces: +document.getElementById('Flow_LegendDP-Input').value,
		clsNum: +document.getElementById("Flow_ClassNum-Input").value,
		numTopFlows: document.getElementById("Flow_TopFlowFromAllFlows-Input").value,
		breakInput: document.getElementById("Flow_ManualBreak-Input").value,
		widthMax: +document.getElementById("Flow_FlowWidth_Max-Input").value,
		widthMin: +document.getElementById("Flow_FlowWidth_Min-Input").value,
		strokeWidth: +document.getElementById("Flow_StrokeWidth-Input").value,
		strokeColor: document.getElementById("Flow_StrokeColor-Input").value,
		legendTitle: document.getElementById('Flow_LegendTitle-Input').value,
		isDisplayedAsAbs: $("#Flow_DisplayAsAbs-CB").is(":checked"), // Display as absolute (it is temporarily hidden from the interface).
		
		// Attributes below are not loaded into project file.
		// Legend settings:
		titleWidth: 150,
		labelOffset: -10,
		
		// Flow style:
		flowStyle: null, // Will be assigned when drawing flows.
		
		// Status:
		hasNewData: false,
		breakArray: null
};

function init() {
	baseMap.control = ol.control.defaults({
        zoom : true,
        attribution: false
    });
    map = new ol.Map({
        controls: baseMap.control.extend([setScaleControl(), setZoomControl()]),
        target: "map",
    });
    
//    $("#ScaleBar-Div div").addClass("LeftLimit");

    onlineLayer = new ol.layer.Tile();
    switchBaseMapLayer(baseMapSettings.baseMap);
    onlineLayer.setZIndex(1);
    otherTerrainLayer.setZIndex(0);
    referenceLayer.setZIndex(2);
    map.addLayer(onlineLayer);
    baseMap.overlay = new ol.Overlay({id: "UserOverlay", element: document.getElementById('UserOverlay'), stopEvent: false, insertFirst: false, autoPan: false});
    map.addOverlay(baseMap.overlay);
    switchMapProjection(baseMapSettings.projection);
    // Add title
    map.updateSize();
}

function setScaleControl() {
		baseMap.scaleControl = new ol.control.ScaleLine({
	      units: "metric",
	      target: "ScaleBar-Div"
	    });
	    return baseMap.scaleControl;
}

function setZoomControl(zoomExtent){
	baseMap.zoomControl = new ol.control.ZoomToExtent({
		extent: zoomExtent
    });
	return baseMap.zoomControl;
}

function setZoomToOverlay(margin, ifZooming){
	if(!baseMapData && !pointData)
		return;
	var overlayBoundary = getBoundOfOverlay();
	var leftBot = map.getCoordinateFromPixel([overlayBoundary[0][0] - margin, overlayBoundary[0][1] - margin]);
	var rightUp = map.getCoordinateFromPixel([overlayBoundary[1][0] + margin, overlayBoundary[1][1] + margin]);
	if(leftBot && rightUp){
		var extent = [leftBot[0], leftBot[1],rightUp[0], rightUp[1]];
		map.removeControl(baseMap.zoomControl);
		map.addControl(setZoomControl(extent));
		if(ifZooming){
			// Zoom to the extent
			setViewOfMap(extent, margin);
		}
	}
}

function removeZoomToOverlay(){
	map.removeControl(baseMap.zoomControl);
}

function switchBaseMapLayer(baseMapVal){
	  map.removeLayer(otherTerrainLayer);
	  map.removeLayer(referenceLayer);
	  switch(baseMapVal){
  	  case "stamenLite":{
  		  onlineLayer.setSource(new ol.source.Stamen({
		        layer: 'toner-lite',
		        crossOrigin: "Anonymous"
  		  }));
  		  break;
  	  };
  	  case "osm":{
  		  onlineLayer.setSource(new ol.source.OSM({
  			  crossOrigin: "Anonymous"
  		  }));
  		  break;
  	  };
  	  case "esriWorldImaginary":{
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Tiles © <a href="https://services.arcgisonline.com/ArcGIS/' +
      	            'rest/services/World_Topo_Map/MapServer">ArcGIS</a>',
      	        url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  
  		  if($("#DisplayMapReference-CB").is(":checked")){
  			map.addLayer(referenceLayer);
  		  }
  		  referenceLayer.setSource(new ol.source.XYZ({
  	        attributions:  'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
  	        url:'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
		  }));
  		  break;
  	  };
  	  case "esriWorldPhysical":{
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Tiles &copy; Esri &mdash; Source: US National Park Service',
      	        url:'https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  if($("#DisplayMapReference-CB").is(":checked")){
  			map.addLayer(referenceLayer);
  		  }
  		  referenceLayer.setSource(new ol.source.XYZ({
  	        attributions:  'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
  	        url:'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places_Alternate/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
		  }));
  		  break;
  	  };
  	  case "esriLightGray":{
  		//light gray canvas
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions:  'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
      	        url:'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  if($("#DisplayMapReference-CB").is(":checked")){
  			map.addLayer(referenceLayer);
  		  }
  		  referenceLayer.setSource(new ol.source.XYZ({
	  	        attributions:  'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
	  	        url:'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
		  		        crossOrigin: "Anonymous"
  		  }));
  		  break;
  	  };
  	  case "esriDarkGray":{
  		//dark gray canvas
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Tiles &copy; Esri &mdash; Source: US National Park Service',
      	        url:'https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  if($("#DisplayMapReference-CB").is(":checked")){
  			map.addLayer(referenceLayer);
		  }
  		  referenceLayer.setSource(new ol.source.XYZ({
	        attributions:  'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
	        url:'https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
		        crossOrigin: "Anonymous"
	      }));
  		  break;
  	  };
  	  case "esriTerrain":{
  		  // Terrain with labels
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Esri, HERE, Garmin, FAO, NOAA, USGS, Intermap, METI, © OpenStreetMap contributors, and the GIS User Community',
      	        url:'https://services.arcgisonline.com/arcgis/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  otherTerrainLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Esri, HERE, Garmin, FAO, NOAA, USGS, Intermap, METI, © OpenStreetMap contributors, and the GIS User Community',
      	        url:'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  referenceLayer.setSource(new ol.source.XYZ({
      	        attributions: 'Esri, HERE, Garmin, FAO, NOAA, USGS, Intermap, METI, © OpenStreetMap contributors, and the GIS User Community',
      	        url:'https://services.arcgisonline.com/arcgis/rest/services/Reference/World_Reference_Overlay/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
		  if($("#DisplayMapReference-CB").is(":checked")){
	  		   map.addLayer(otherTerrainLayer);
	  		   map.addLayer(referenceLayer); 
		  }
  		  break;
  	  };
  	  case "esriTopographic":{
  		  // Topographic
  		  onlineLayer.setSource(new ol.source.XYZ({
      	        attributions: ' Esri, DeLorme, NAVTEQ, TomTom, Intermap, increment P Corp, GEBCO, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, and the GIS User Community',
      	        url:'https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
	  		        crossOrigin: "Anonymous"
      	      }));
  		  break;
  	  };
  	  default:
  		  break;
	  }; 
}

function registerProjection(name, proj4Str){
	 proj4.defs(name, proj4Str);
	 ol.proj.proj4.register(proj4);
	 return name;
}

function switchMapProjection(prj){
	var view;
	switch(prj){
		case "webMct":{
			baseMap.projection = "EPSG:900913";
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([0, 20], "EPSG:4326", baseMap.projection),
		        zoom: 0,
		        extent: [-20037508.34, -20037508.34, 20037508.34, 20037508.34]
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaUS":{
			baseMap.projection = registerProjection("ESRI:102003", "+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=37.5 +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m+no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform(baseMap.center, "EPSG:4326", baseMap.projection),
		        zoom: baseMap.zoom
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaAfc":{
			baseMap.projection = registerProjection("ESRI:102022", "+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([25, 0], "EPSG:4326", baseMap.projection),
		        zoom: +baseMap.zoom - 1.5
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaAs":{
			baseMap.projection = registerProjection("EPSG:3577", "+proj=aea +lat_1=-18 +lat_2=-36 +lat_0=0 +lon_0=134 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs ");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([132, -28], "EPSG:4326", baseMap.projection),
		        zoom: +baseMap.zoom - 0.7
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaCn":{
			baseMap.projection = registerProjection("ESRI:102028", "+proj=aea +lat_1=27 +lat_2=45 +lat_0=35 +lon_0=105 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m+no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([105, 35], "EPSG:4326", baseMap.projection),
		        zoom: +baseMap.zoom - 0.5
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaEu":{
			baseMap.projection = registerProjection("ESRI:102013", "+proj=aea +lat_1=43 +lat_2=62 +lat_0=37.5 +lon_0=10 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m+no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([0.0, 52.0], "EPSG:4326", baseMap.projection),
		        zoom: +baseMap.zoom - 0.5
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "abEqAreaSthAm":{
			baseMap.projection = registerProjection("ESRI:102033", "+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 +x_0=0 +y_0=0 +ellps=aust_SA +units=m+no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([-60, -25], "EPSG:4326", baseMap.projection),
		        zoom: +baseMap.zoom - 1.3
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			break;
		};
		case "robin":{
			baseMap.projection = registerProjection("ESRI:53030", "+proj=robin +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([0,0], "EPSG:4326", baseMap.projection),
		        zoom: 2,
		        maxZoom:3,
		        minZoom:3
		      });
			removePanInteraction();
			removeZoomToOverlay();
			
			break;
		};
		
		case "gall":{
			baseMap.projection = registerProjection("SRORG:22", "+proj=cea +lon_0=0 +x_0=0 +y_0=0 +lat_ts=45 +ellps=WGS84 +datum=WGS84 +units=m +no_defs");
			view = new ol.View({
		        projection: baseMap.projection,
		        center: ol.proj.transform([0,0], "SRORG:22", baseMap.projection),
		        zoom:3,
		        minZoom: 3,
		        extent: [-20037508.34, -10037508.34, 20037508.34, 10037508.34]
		      });
			addPanInteraction();
			setZoomToOverlay(5);
			
			break;
		};
		
		// Equal earth is not usable currently.
//		case "eqEarth":{
//			baseMap.projection = registerProjection("ESRI:102008", "+proj=eqearth +x_0=0 +y_0=0 +R=1");
//			view = new ol.View({
//		        projection: baseMap.projection,
//		        center: ol.proj.transform(baseMap.center, "EPSG:4326", baseMap.projection),
//		        zoom: baseMap.zoom
//		      });
//			break;
//		};
	}
	// Set the extent
	map.setView(view);
}

function addPanInteraction(){
	var panInteraction;
	map.getInteractions().forEach(function (interaction) {
	   if (interaction instanceof ol.interaction.DragPan) {
		   panInteraction = interaction;
	   }
	});
	// Remove the interaction from the map.
	if (!panInteraction) { 
		map.addInteraction(baseMap.panInteraction); 
	}
}

function removePanInteraction(){
	var panInteraction;
	map.getInteractions().forEach(function (interaction) {
	   if (interaction instanceof ol.interaction.DragPan) {
		   panInteraction = baseMap.panInteraction = interaction;
	   }
	});
	// Remove the interaction from the map.
	if (panInteraction) { 
		map.removeInteraction(baseMap.panInteraction); 
	}
}

init();
