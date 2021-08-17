/*
 * All the functions that draw the flows should be in a seperated file. (DrawFlows.js)
 * Flowmap.js-> MapInit.js
 * 
 */



var w = document.getElementById('map').offsetWidth , h = document.getElementById('map').offsetHeight;
var translatewidth = w/2 , translateheight = h/2;

//Define projection
//var projection = d3.geoAlbersUsa();
//	.scale(1800)
//	.translate([translatewidth, translateheight + 50]);
//var projection = d3.geoProjection(function(coor) {
//	var point = map.getViewPortPxFromLonLat(new OpenLayers.LonLat(coor[0], coor[1]).transform("EPSG:4326", "EPSG:900913"));
//	return [point.x, point.y];
//});

var baseMapData = null;
var flowData = null;
var pointData = null;
var CPMData = null;

//var path = d3.geoPath().projection(projection);

var svg_user_painting = d3.selectAll("#UserOverlay").append("svg").attr("id", "svg_user_painting");

var svg_CPMLegend;
var svg_PointLegend;
var svg_FlowLegend;

//for choropleth map
var g1 = svg_user_painting.append("g");
//for flows
var g3 = svg_user_painting.append("g");
//for points
var g2 = svg_user_painting.append("g");
var CPMbound = [[Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER], [Number.MIN_SAFE_INTEGER, Number.MIN_SAFE_INTEGER]];
var flowbound = [[Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER], [Number.MIN_SAFE_INTEGER, Number.MIN_SAFE_INTEGER]];
var pointbound = [[Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER], [Number.MIN_SAFE_INTEGER, Number.MIN_SAFE_INTEGER]];

var markerDefs = null;

//classification method applied on points
var nodescale;

//create a quantile scale for flows

//define style of path
var currentPathProjection = chooseCurrentProjection();
function chooseCurrentProjection() {
	switch(document.getElementById("FlowMap_Style-Select").value){
		case "curve":{
			return pathstyle_curve;
		};
		case "straightWithHalfArrow" :{
			return pathstyle_straightwitharrow;
		};
		default:{
			return null;
		}
	}
};
function loadBaseMap(jsonData){
	var world = JSON.parse(jsonData);
	var keyNames = Object.keys(world['features'][0].properties);
	
	removeOptions("CPM_BMPK-Select");
	for(var i = 0; i < keyNames.length; i++){
		addOptions("CPM_BMPK-Select", keyNames[i], keyNames[i]);
	}
	
	processBaseMap(world);
	return world;
} 

function projectToOnlineBaseMap(x) {
	if(x == undefined) return;
    var point = map.getPixelFromCoordinate(new ol.proj.transform([x[0], x[1]], "EPSG:4326", "EPSG:900913"));
    return [point[0], point[1]];
}

function projectToOnlineBaseMapTransform(map) {
	  return d3.geoTransform({
	    point: function(x, y) {
	    	var point = map.getPixelFromCoordinate(new ol.proj.transform([x, y], "EPSG:4326", "EPSG:900913"));
	    	this.stream.point(point[0] , point[1]);
	    }
	  });
}

//Define the path projection to the online base map! 
//Write like this because in d3.4 we must use project stream to create self-designed projection.
var pathOnOBM = d3.geoPath().projection(projectToOnlineBaseMapTransform(map));

function deleteExistingLayer(layerName){
	for(var i = 0; i < map.layers.length; i++)
		if(map.layers[i].name == layerName){
			map.removeLayer(map.layers[i]);
			break;
		}
}

function getBoundOfOverlay(){
	var topleft = [Math.min(Math.min(CPMbound[0][0], flowbound[0][0]), pointbound[0][0]), Math.min(Math.min(CPMbound[0][1], flowbound[0][1]), pointbound[0][1])];
	var bottomright = [Math.max(Math.max(CPMbound[1][0], flowbound[1][0]), pointbound[1][0]), Math.max(Math.max(CPMbound[1][1], flowbound[1][1]), pointbound[1][1])];
	return [topleft, bottomright];
}

function resetMapOverlay(){
	var bound = getBoundOfOverlay();
	var bottomLeft = projectToOnlineBaseMap(bound[0]),
    topRight = projectToOnlineBaseMap(bound[1]);
	var maxRadius = parseInt(document.getElementById("Point_Radius_Max-Input").value);
	
    svg_user_painting.attr("width", topRight[0] - bottomLeft[0] + 2 * maxRadius)
    .attr("height", bottomLeft[1] - topRight[1] + 2 * maxRadius)
    
    g1.attr("transform", "translate(" + -(bottomLeft[0] - maxRadius) + "," + -(topRight[1] - maxRadius) + ")");
    g1.selectAll("path").attr("d", pathOnOBM);
    g2.attr("transform", "translate(" + -(bottomLeft[0] - maxRadius) + "," + -(topRight[1] - maxRadius) + ")");
    g2.selectAll("circle").attr("cx", function(d, i) { return projectToOnlineBaseMap(positions[i])[0];})
    .attr("cy", function(d, i) { return projectToOnlineBaseMap(positions[i])[1];});
    g3.attr("transform", "translate(" + -(bottomLeft[0] - maxRadius) + "," + -(topRight[1] - maxRadius) + ")");
    g3.selectAll("path").attr("d", currentPathProjection);
}
map.on("postrender", resetMapOverlay);

function processBaseMap(world){
    var overlay =  map.getOverlayById("UserOverlay");
    g1.selectAll("path").remove();
    CPMbound = d3.geoBounds(world);
    var maxRadius = parseInt(document.getElementById("Point_Radius_Max-Input").value);
    var feature = g1.selectAll("path")
	//The way that we load features into the map
		.data(world.features)
		.enter()
        .append("path")
        //attr should be placed on the bottom of what you want to add otherwise it won't be added
        .attr("class", "land")
        .attr("stroke", "black")
        .attr("stroke-linejoin", "round")
        .attr("fill", "grey")
        //!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! bugs on text display  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        feature.append("title")
//        .text("test");
    resetMapOverlay();
    overlay.setPosition(new ol.proj.transform([getBoundOfOverlay()[0][0], getBoundOfOverlay()[1][1]], "EPSG:4326", "EPSG:900913"));
    overlay.setOffset([-maxRadius, -maxRadius]);
}

// TODO: move them to a new file for flows. (Flowmap.js & change the current name of this js file)
var linksByOrigin = {},
//location of node by (x, y) coordinate
countByNodeID = {},
locationByNodeID = {},
volumeByNodeID = {},
positions = [],
volumearr = [],
topVolumeList = [],
topVolumeList_modified = [],
topLinks = [];
//only show flows which are greater than threshold
var flowthreshold = Number.MIN_SAFE_INTEGER;
// normalize the scale to positive numbers
var nodesizeattribute = [],
nodesizeattribute_modified = [];

function addOptions(selectElement, optionName, value) {
	var x = document.getElementById(selectElement);
	var option = document.createElement("option");
	  option.text = optionName;
	  option.value = value;
	  x.add(option);
}

function removeOptions(selectElement) {
	var x = document.getElementById(selectElement);
	var i, L = x.options.length - 1;
	if(L == 0) return null;
	else
		for(i = L; i >= 0; i--) {
			x.remove(i);
		}
}

function loadFlowData(csvData){	
	var flowData = d3.csvParse(csvData);
	var keyNames = Object.keys(flowData[0]);
//	var flowData = JSON.parse(jsonData);
//	var keyNames = Object.keys(flowData[0]);
	
	removeOptions("Flow_Volume-Select");
	removeOptions("Flow_SourceID-Select");
	removeOptions("Flow_TargetID-Select");
	for(var i = 0; i < keyNames.length; i++){
		addOptions("Flow_Volume-Select", keyNames[i], keyNames[i]);
		addOptions("Flow_SourceID-Select", keyNames[i], keyNames[i]);
		addOptions("Flow_TargetID-Select", keyNames[i], keyNames[i]);
	}
	
	return flowData;
}

function dataPreparation(flowData, nodes, sourceField, targetField, volumeField_Flows, IDField, XField, YField, volumeField_Points){
	//all these variables are global. Set them as none when we are trying to load data again.
	linksByOrigin = {};
	countByNodeID = {};
	locationByNodeID = {};
	volumeByNodeID = {};
	positions = [];
	flowthreshold = Number.MIN_SAFE_INTEGER;
	nodesizeattribute = [];
	volumearr = [];
	topVolumeList = [];
	topVolumeList_modified = [];
	topLinks = [];

	if(flowData != null){
		var volumeList = []; originList = [], destinationList = [];
		var jumpWithinFlows = true;
		flowData.forEach(function(flow) {
		      if(flow[sourceField] != flow[targetField]){
		        volumearr.push(flow[volumeField_Flows]);
		      }
		      //pick origin and destination
		      var origin = flow[sourceField],
		      destination = flow[targetField],
		      //get volume data
		      volume = flow[volumeField_Flows];
		      volumeList.push(parseInt(volume));
		      originList.push(origin);
		      destinationList.push(destination);
		    });
		
		if($("#Flow_DisplayAsAbs-CB").is(":checked")){
			topLinks = calculateTopLinks(100, volumeList.map(Math.abs), volumeList, originList, destinationList);
	      }else{
	    	topLinks = calculateTopLinks(100, volumeList, volumeList, originList, destinationList);
	      }
		
		//iterate through the list, to pick the top 100 flows
		// sort the data to make sure large flows are on top of small flows
		
		// --------------------------calculating top 100 flows ends-------------------------------------------------
	}
    
	// Only consider nodes with at least one flight.
	return filterNodes(nodes, IDField, XField, YField, volumeField_Points);
}

function calculateTopLinks(topNum, volumeList, volumeList_original, originList, destinationList){
	var topLinks = [];
	var topIdList = [];
	while(topVolumeList.length < topNum){
		var max, tempMax = Number.MIN_SAFE_INTEGER, tempMaxId = 0;
		if(topVolumeList.length == 0) {max = Number.MAX_SAFE_INTEGER;}
		else {max = Math.abs(topVolumeList[topVolumeList.length - 1]); tempMaxId = topVolumeList.length - 1;}
		for(var i = 0; i < volumeList.length; i++){
			if(volumeList[i] <= max && volumeList[i] > tempMax) {
				if(!topIdList.includes(i) && originList[i] != destinationList[i]){
					tempMax = volumeList[i];
					tempMaxId = i;
				}
			}
		}
		
		topVolumeList.push(volumeList_original[tempMaxId]);
		topIdList.push(tempMaxId);
		//pick links by origin or set links by origin as empty
		var links = linksByOrigin[originList[tempMaxId]] || (linksByOrigin[originList[tempMaxId]] = []);
		//create the links by inserting it in descending order, for the convenience of showing the top flows
		links.push({source: originList[tempMaxId], target: destinationList[tempMaxId], volume: volumeList_original[tempMaxId]});
		countByNodeID[originList[tempMaxId]] = (countByNodeID[originList[tempMaxId]] || 0) + 1;
		countByNodeID[destinationList[tempMaxId]] = (countByNodeID[destinationList[tempMaxId]] || 0) + 1;
		topLinks.unshift({source: originList[tempMaxId], target: destinationList[tempMaxId], volume: volumeList_original[tempMaxId]});
	}
	return topLinks;
}

function filterNodes(nodes, IDField, XField, YField, volumeField_Points){
	return nodes.filter(function(node) {
		if (flowData == null || flowData != null && countByNodeID[node[IDField]]) {
			var location = [+node[XField], +node[YField]];
			// initialize the node location list

			locationByNodeID[node[IDField]] = location;

			// initialize the position list by project the location variables
			positions.push(location);
			// initialize the point size list by recalling data from file
			/*if($("#Point_DisplayAsAbs-CB").is(":checked")){
				volumeByNodeID[node[IDField]] = Math.abs(+node[volumeField_Points]);
			}else{
				volumeByNodeID[node[IDField]] = +node[volumeField_Points];
			}*/
			volumeByNodeID[node[IDField]] = +node[volumeField_Points];
			nodesizeattribute.push(+node[volumeField_Points]);
			return true;
		}
	});
}

function processFlowData(flowData, nodes, IDField){
    var overlay = map.getOverlayById("UserOverlay");
    g3.selectAll("path").remove();
  //Define the style of arrow (for some flow styles).
	var defs = svg_user_painting.append("defs");
    	
    /*var minX = d3.min(positions, function(d, i) {
  	  return positions[i][0];
    }), 
    minY = d3.min(positions, function(d, i) {
    	  return positions[i][1] ;
    }), 
    maxX = d3.max(positions, function(d, i) {
    	  return positions[i][0];
    }), 
    maxY = d3.max(positions, function(d, i) {
    	  return positions[i][1];
    }),
    flowbound = [[minX, minY], [maxX, maxY]],*/
    var pathOnOBM = d3.geoPath().projection(projectToOnlineBaseMapTransform(map));
    
    //------------------------------------------------This is old version of node setting-----------------------
//    var paths = g3.selectAll("g")
//	.data(nodes)
//	.enter()
//	.append("svg:g");
    
    //var feature = paths.selectAll("path")
  //------------------------------------------------Old node setting ends--------------------------------------
    var feature = g3.selectAll("path")
	.data(topLinks)
			//function(d) { 
		// --------------------------------------------this code is for top 10 flows from each node-----------------------------------
		/*var topNum = 10;
			if(linksByOrigin[d[IDField]] == null) return [];
			if(linksByOrigin[d[IDField]].length <= topNum) return linksByOrigin[d[IDField]];
			var topList = [];
			while(topList.length < topNum){
				var max, tempMax = linksByOrigin[d[IDField]][0].volume;
				if(topList.length == 0) max = 99999999999;
				else max = topList[topList.length - 1];
				for(var i = 0; i < linksByOrigin[d[IDField]].length - 1; i++){
					if(linksByOrigin[d[IDField]][i].volume <= max && linksByOrigin[d[IDField]][i].volume > tempMax) {
						tempMax = linksByOrigin[d[IDField]][i];
					}
				}
				topList.push(tempMax);
			}
			return topList;*/
		// ------------------------------------------code for top 10 flows from each node ends----------------------------------------
		
		// --------------------------------------------this code is for top 100 flows from all flows-----------------------------------
		/*if(linksByOrigin[d[IDField]] == null) return [];
		else return linksByOrigin[d[IDField]];*/
		// --------------------------------------------code for top 100 flows from all flows ends--------------------------------------
		//})
	.enter().append("path")
	feature.append("title")
//	.attr("class", "route")
//	.attr("marker-end", function(d) {
//	    	  if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
//	    		//define the markers (arrow for some flows).
//	    			var color = flows_color(d.volume);
//	    			var id = color.replace(/[(), ]/g,'_');
//	    				defs.append("marker")
//	    			    .attr("id", id)
//	    			    .attr("viewBox","0 0 12 12")
//	    				.attr("refX",6)
//	    				.attr("refY",6)
//	    				.attr("markerWidth",5)
//	    				.attr("markerHeight",5)
//	    				.attr("markerUnits","strokeWidth")
//	    			    .attr("orient", "auto")
//	    			    .append("path")
//	    			    .attr("d", "M2,2  L2,10 L11,6 L2,2")
//	    			    .attr("style", "fill:" + color);
//	    			return findMarker(flows_color(d.volume));
//	    	  } 
//    	  })
	//  .style("stroke-opacity", function(d) {
	//	    if(locationByNodeID[d[sourceField]] && locationByNodeID[d[targetField]]){
	//	      if(d[volumeField_Flow] < flowthreshold)
	//	    	  {
	////	    	  console.log("d[volumeField_Flow] being set 0 opacity: " + d[volumeField_Flow]);
	//	        return 0;
	//	    	  }
	//	    }
	//  })
//	.style("fill", "transparent"
////    			function(d) { return flows_color(d.volume);}
//	)
	//!!! please set stroke color otherwise you will only see the fill color, not the stroke color!!


	resetColorSchemeAndLegendForFlows();
    resetColorSchemeAndLegendForPoints();
    
//    overlay.setPosition(new ol.proj.transform([minX, maxY], "EPSG:4326", "EPSG:900913"));
//    var maxRadius = parseInt(document.getElementById("Point_Radius_Max-Input").value) * 3;
//    overlay.setOffset([-maxRadius, -maxRadius]);
    
    
    resetMapOverlay();
}

// TODO: Move the codes to a new JS file: PointSymbolMap.js.
function loadPointData(csvData){
	//load the nodes (cirles)
//	var nodes = JSON.parse(csvData);
//	var keyNames = Object.keys(nodes[0]);
	
	var nodes = d3.csvParse(csvData);
	var keyNames = Object.keys(nodes[0]);
	
	removeOptions("Point_Volume-Select");
	removeOptions("Point_ID-Select");
	removeOptions("Point_X-Select");
	removeOptions("Point_Y-Select");
	for(var i = 0; i < keyNames.length; i++){
		addOptions("Point_Volume-Select", keyNames[i], keyNames[i]);
		addOptions("Point_ID-Select", keyNames[i], keyNames[i]);
		addOptions("Point_X-Select", keyNames[i], keyNames[i]);
		addOptions("Point_Y-Select", keyNames[i], keyNames[i]);
	}

	return nodes;
}

function processPointData(nodes, volumeField_Points){
    var overlay = map.getOverlayById("UserOverlay");
    g2.selectAll("circle").remove();
    var maxRadius = parseInt(document.getElementById("Point_Radius_Max-Input").value);
    var minX = d3.min(positions, function(d, i) {
  	  return positions[i][0];
    }), 
    minY = d3.min(positions, function(d, i) {
    	  return positions[i][1] ;
    }), 
    maxX = d3.max(positions, function(d, i) {
    	  return positions[i][0];
    }), 
    maxY = d3.max(positions, function(d, i) {
    	  return positions[i][1];
    });
    pointbound = [[minX, minY],[maxX, maxY]];
    var feature = g2.selectAll("circle")
	//The way that we load features into the map
      .data(nodes)
	  .enter()
	  .append("circle")
	  feature.append("title")
//    	  .attr("cx", function(d, i) { return positions[i][0];})
//    	  .attr("cy", function(d, i) { return positions[i][1];})
    
	resetColorSchemeAndLegendForPoints();
    
    overlay.setPosition(new ol.proj.transform([getBoundOfOverlay()[0][0], getBoundOfOverlay()[1][1]], "EPSG:4326", "EPSG:900913"));
    overlay.setOffset([-maxRadius, -maxRadius]);
    
    resetMapOverlay();
}

// TODO: Move the codes to a new JS file: ChoroplethMap.js.
// Change the function name to loadChoroplethData.
function loadCPMData(data){
	//this code is for parsing json data
//	var CSVData = JSON.parse(jsonData);
//	var keyNames = Object.keys(CSVData[0]);
//	
//	removeOptions("CPM_CSVPK-Select");
//	removeOptions("CPM_Value-Select");
//	for(var i = 0; i < keyNames.length; i++){
//		addOptions("CPM_CSVPK-Select", keyNames[i], keyNames[i]);
//		addOptions("CPM_Value-Select", keyNames[i], keyNames[i]);
//	}
	var CSVData = d3.csvParse(data);
	var keyNames = Object.keys(CSVData[0]);
	
	removeOptions("CPM_CSVPK-Select");
	removeOptions("CPM_Value-Select");
	for(var i = 0; i < keyNames.length; i++){
		addOptions("CPM_CSVPK-Select", keyNames[i], keyNames[i]);
		addOptions("CPM_Value-Select", keyNames[i], keyNames[i]);
	}
	
	return CSVData;
}

var CPMValue;
var CPMIdValueMap;
function processCPMData(CPMData){
	var selectedCSVID = $("#CPM_CSVPK-Select option:selected").text();
	var selectedValue = $("#CPM_Value-Select option:selected").text();
	var selectedGeomID = $("#CPM_BMPK-Select option:selected").text();
	if(!Object.keys(CPMData[0]).includes(selectedCSVID)) 
		alert("Map cannot be made! Please check you have chosen a right ID field of your CSV file.");
	if(!Object.keys(baseMapData.features[0].properties).includes(selectedGeomID)) 
		alert("Map cannot be made! Please check you have chosen a right ID field of your base map.");
	if(!Object.keys(CPMData[0]).includes(selectedValue)) 
		alert("Map cannot be made! Please check you have chosen a right value field.");
	CPMValue = [];
	var csv_data = [];
	CPMData.forEach(function (obj){
	    var pair = [obj[selectedCSVID], obj[selectedValue]];
	    csv_data.push(pair);
	    CPMValue.push(+obj[selectedValue]);
	  });
	CPMIdValueMap = Object.assign(new Map(csv_data));
	
	resetColorSchemeAndLegendForCPM()
}

//TODO: Move the codes to a new JS file: Legend.js.
function addLegend(svg_legend, legendTitle, scale, id_svg, legendType, display, colorScheme, flowStyle, options, isColorDisabled){
	//remove the old legend
	if(svg_legend != undefined)
		d3.select("#Legend").select("#" + id_svg).remove();

	svg_legend = d3.select("#Legend")
	.append("svg")
	.attr("id", id_svg)
	.style("display", "block");
	
	if(legendType == "CPM_Classified"){
		var dp = document.getElementById("CPM_LegendDP-Input").value;
		svg_legend.append("g")
		  .attr("class", "legendQuant " + colorScheme)
		  .attr("id", "g_CPMlegend")
		  .attr("transform", "translate(20, 30)");

		var legend = d3.legendColor()
		  .labelFormat(d3.format("." + dp + "f"))
		  .title(legendTitle)
		  .titleWidth(100)
		  .scale(scale)
		  .useClass(false);

		if(options == "ManualBreak" || options == "NaturalBreak"){
			// Commented: "or more & or less"
//			legend.labels(d3.legendHelpers.thresholdLabels);
			legend.labels(function({
			  i,
			  genLength,
			  generatedLabels,
			  labelDelimiter
			}) {
			  if (i === 0) {
			    const values = generatedLabels[i].split(` ${labelDelimiter} `);
			    return `${d3.min(CPMValue)} to ${values[1]}`
			  } else if (i === genLength - 1) {
			    const values = generatedLabels[i].split(` ${labelDelimiter} `)
			    return `${values[0]} to ${d3.max(CPMValue)}`
			  }
			  return generatedLabels[i]
			});
		}
		
		svg_legend.select(".legendQuant")
		  .call(legend);
		
		var bbox_g = $("#g_CPMlegend")[0].getBBox();
		svg_legend.attr("width", bbox_g.width + 40);
		svg_legend.attr("height", bbox_g.height + 30);
	}if(legendType == "CPM_Unclassified"){
		var dp = document.getElementById("CPM_LegendDP-Input").value;
		svg_legend.append("g")
		  .attr("class", "legendLinear")
		  .attr("id", "g_CPMlegend")
		  .attr("transform", "translate(20, 30)");

		var legendLinear = d3.legendColor()
		.labelFormat(d3.format("." + dp_CPM + "f"))
		  .shapeWidth(30)
		  .title(legendTitle)
		  .orient('vertical')
		  .scale(scale);

		svg_legend.select(".legendLinear")
		  .call(legendLinear);
		
		var bbox_g = $("#g_CPMlegend")[0].getBBox();
		svg_legend.attr("width", bbox_g.width + 40);
		svg_legend.attr("height", bbox_g.height + 30);
	}else if(legendType == "Point"){
		var dp = document.getElementById("Point_LegendDP-Input").value;
		if($("#Point_DisplayAsAbs-CB").is(":checked")){
			svg_legend.append("g")
			  .attr("class", "legendLinear")
			  .attr("id", "g_PointLegend")
			  .attr("transform", "translate(20, 30)");
			
			var circleRadius, circleDomain;
			if(d3.min(nodesizeattribute) < 0){
				circleRadius = [circlePathGen(0, 0, nodescale(Math.abs(d3.min(nodesizeattribute)))), circlePathGen(0, 0, nodescale(Math.abs(d3.max(nodesizeattribute))))]
				circleDomain = [d3.min(nodesizeattribute), d3.max(nodesizeattribute)];
			}else{
				circleRadius = [circlePathGen(0, 0, nodescale(Math.abs(d3.max(nodesizeattribute))))];
				circleDomain = [d3.max(nodesizeattribute)];
			}
			
			var symbolScale =  d3.scaleOrdinal()
			  .domain(circleDomain)
			  .range(circleRadius);
			
			
			var legendCircleAbs = d3.legendSymbol()
			  .title(legendTitle)
			  .titleWidth(100)
			  .scale(symbolScale)
			  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
				  if(genLength == 1){
					  return `0 to ${d3.max(nodesizeattribute).toFixed(dp)}`;
				  }else{
					  if (i === 0) {
					    return `${d3.min(nodesizeattribute).toFixed(dp)} to 0`;
					  } 
					  return `0 to ${d3.max(nodesizeattribute).toFixed(dp)}`;
				  }
				});
			
			
			svg_legend.select(".legendLinear")
			  .call(legendCircleAbs);
			
			svg_legend.selectAll("#g_PointLegend path").each(function(d) {
				  d3.select(this).style("fill", scale(d))
			})
			
			var bbox_g = $("#g_PointLegend")[0].getBBox();
			svg_legend.attr("width", bbox_g.width + 40);
			svg_legend.attr("height", bbox_g.height + 30);
		}else{
			svg_legend .append("g")
			  .attr("class", "legendSize")
			  .attr("id", "g_PointLegend")
			  .attr("transform", "translate(20, 40)");

			var legendSize = d3.legendSize()
			  .labelFormat(d3.format("." + dp + "f"))
			  .scale(scale)
			  .title(legendTitle)
			  .shape('circle')
			  .shapePadding(15)
			  .labelOffset(20)
			  .orient('vertical');

			if(options == "ManualBreak" || options == "NaturalBreak"){
//				Commented: "or more & or less"
//				legend.labels(d3.legendHelpers.thresholdLabels);
				legendSize.labels(function({
				  i,
				  genLength,
				  generatedLabels,
				  labelDelimiter
				}) {
				  if (i === 0) {
				    const values = generatedLabels[i].split(` ${labelDelimiter} `);
				    return `${d3.min(nodesizeattribute_modified).toFixed(dp)} to ${values[1]}`
				  } else if (i === genLength - 1) {
				    const values = generatedLabels[i].split(` ${labelDelimiter} `)
				    return `${values[0]} to ${d3.max(nodesizeattribute_modified).toFixed(dp)}`
				  }
				  return generatedLabels[i]
				});
			}
			
			svg_legend.select(".legendSize")
			  .call(legendSize);
			
			var bbox_g = $("#g_PointLegend")[0].getBBox();
			svg_legend.attr("width", bbox_g.width + 40);
			svg_legend.attr("height", bbox_g.height + 30);
		}
	}else if(legendType == "flow_Classified"){
		var legend;
		var dp = document.getElementById("FlowMap_LegendDP-Input").value;
		if(!isColorDisabled){
			if($("#Flow_DisplayAsAbs-CB").is(":checked")){
				return;
			}else{
				legend = d3.legendColor()
				  .labelFormat(d3.format("." + dp + "f"))
				  .title(legendTitle)
				  .titleWidth(100)
				  .scale(scale)
				  .useClass(false);
				
				if(options == "ManualBreak" || options == "NaturalBreak" ){
	//				legend.labels(d3.legendHelpers.thresholdLabels);
					legend.labels(function({i,genLength,generatedLabels,labelDelimiter}) {
						  if (i === 0) {
						    const values = generatedLabels[i].split(` ${labelDelimiter} `);
						    return `${d3.min(topVolumeList).toFixed(dp)} to ${values[1]}`
						  } else if (i === genLength - 1) {
						    const values = generatedLabels[i].split(` ${labelDelimiter} `)
						    return `${values[0]} to ${d3.max(topVolumeList).toFixed(dp)}`
						  }
						  return generatedLabels[i];
						});
				}
				
				if(flowStyle == "straight" || flowStyle == "arc"){
					legend.shape("path", "M-10,1L10,1L10,-1L10,-1");
				}
				else if(flowStyle == "straightWithHalfArrow"){
					legend.shape("path", drawStraightWithArrow(30, 0, -30, 0, 10, 0, 0));
				}
				else if(flowStyle == "curve"){
					legend.shape("path", drawCurve(30, 0, -30, 0, 10, 0, 0, true));
				}
			}
		}else{
			var labelTexts;
			switch(options){
				case "Quantile":{
					labelTexts = flowStrokeWidthScale.quantiles();
					break;
				};
				case "EqualInterval":{
					labelTexts = flowStrokeWidthScale.thresholds();
					break;
				};
				case "ManualBreak":{
					labelTexts = flowStrokeWidthScale.domain();
					break;
				};
				case "NaturalBreak":{
					labelTexts = flowStrokeWidthScale.domain();
					break;
				};
				default :{
					alert("Can not draw flow legend in this classification");
					break;
				}
			}
			labelTexts.push(d3.max(topVolumeList_modified));
			var symbolScale =  d3.scaleOrdinal()
			  .domain(labelTexts)
			  .range(buildLegendFlowSymbolsRange(flowStyle, flowStrokeWidthScale.range()));
			legend = d3.legendSymbol()
			  .title(legendTitle)
			  .titleWidth(100)
			  .scale(symbolScale)
			  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
				  if (i === 0) {
				    return `${d3.min(topVolumeList_modified).toFixed(dp)} to ${generatedLabels[i].toFixed(dp)}`;
				  } 
				  return `${generatedLabels[i - 1].toFixed(dp)} to ${generatedLabels[i].toFixed(dp)}`;
			});
		}
		
//		if($("#Flow_DisplayAsAbs-CB").is(":checked")){
//			legend.labels(function({i,genLength,generatedLabels,labelDelimiter}) {
//				  if (i === 0) {
//				    return `${d3.min(topVolumeList).toFixed(dp)} to 0`;
//				  } 
//				  return `0 to ${d3.max(topVolumeList).toFixed(dp)}`;
//			})
//		}
		
		svg_legend.append("g")
		  .attr("class", "legendQuant " + colorScheme)
		  .attr("id", "g_FlowLegend")
		  .attr("transform", "translate(20, 30)");
		
		svg_legend.select(".legendQuant")
		  .call(legend);
		
		var bbox_g = $("#g_FlowLegend")[0].getBBox();
		svg_legend.attr("width", bbox_g.width + 40);
		svg_legend.attr("height", bbox_g.height + 30);
	}else if(legendType == "flow_Unclassified"){
		var dp = document.getElementById("FlowMap_LegendDP-Input").value;
		svg_legend.append("g")
		  .attr("class", "legendLinear")
		  .attr("id", "g_FlowLegend")
		  .attr("transform", "translate(20, 30)");
		var legend;
		if($("#Flow_DisplayAsAbs-CB").is(":checked")){
			var flowWidthDomain, flowPaths;
			
			if(d3.min(topVolumeList) < 0){
				flowWidthDomain = [d3.min(topVolumeList), d3.max(topVolumeList)];
				var flowWidthArr = [flowStrokeWidthScale(Math.abs(d3.min(topVolumeList))), flowStrokeWidthScale(Math.abs(d3.max(topVolumeList)))];
				flowPaths = buildLegendFlowSymbolsRange(flowStyle, flowWidthArr);
			}else{
				flowWidthDomain = [d3.max(topVolumeList)];
				var flowWidthArr = [flowStrokeWidthScale(Math.abs(d3.max(topVolumeList)))];
				flowPaths = buildLegendFlowSymbolsRange(flowStyle, flowWidthArr);
			}
			
			var symbolScale =  d3.scaleOrdinal()
			  .domain(flowWidthDomain)
			  .range(flowPaths);
			
			
			legend = d3.legendSymbol()
			  .title(legendTitle)
			  .titleWidth(100)
			  .scale(symbolScale)
			  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
				  if(genLength == 1){
					  return `0 to ${d3.max(topVolumeList).toFixed(dp)}`;
				  }else{
					  if (i === 0) {
					    return `${d3.min(topVolumeList).toFixed(dp)} to 0`;
					  } 
					  return `0 to ${d3.max(topVolumeList).toFixed(dp)}`;
				  }
				});
			
			svg_legend.select(".legendLinear")
			  .call(legend);
			
			svg_legend.selectAll("#g_FlowLegend path").each(function(d) {
				d3.select(this).style("fill", scale(d))
			})
			
			var bbox_g = $("#g_FlowLegend")[0].getBBox();
			svg_legend.attr("width", bbox_g.width + 40);
			svg_legend.attr("height", bbox_g.height + 30);
		}else{
			legend = d3.legendColor()
			.labelFormat(d3.format("." + dp + "f"))
			  .shapeWidth(30)
			  .title(legendTitle)
			  .orient('vertical')
			  .scale(scale);
			
			if(flowStyle == "straight" || flowStyle == "arc"){
				legend.shape("path", "M-10,1L10,1L10,-1L10,-1");
			}
			else if(flowStyle == "straightWithHalfArrow"){
				legend.shape("path", drawStraightWithArrow(30, 0, -30, 0, 10, 0, 0));
			}
			else if(flowStyle == "curve"){
				legend.shape("path", drawCurve(30, 0, -30, 0, 10, 0, 0, true));
			}
		}
		
		svg_legend.select(".legendLinear")
		  .call(legend);
		
		var bbox_g = $("#g_FlowLegend")[0].getBBox();
		svg_legend.attr("width", bbox_g.width + 40);
		svg_legend.attr("height", bbox_g.height + 30);
	}
	
	
	//check whether the user wants the legend to be displayed
	if(!display)
		$("#" + id_svg).css("display","none");
	
	return svg_legend;
	
	function buildLegendFlowSymbolsRange(flowStyle, widthArr){
		var symbolArray = [];
		if(flowStyle == "curve"){
			for(var i = 0; i < widthArr.length; i++){
				symbolArray.push(drawCurve(30, 0, -30, 0, widthArr[i], 0, 0, true));
			}
		}
		return symbolArray;
	}
	
	function circlePathGen(cx, cy, myr){
		return "M" + cx + "," + cy + " " +
        "m" + -myr + ", 0 " +
        "a" + myr + "," + myr + " 0 1,0 " + myr*2  + ",0 " +
        "a" + myr + "," + myr + " 0 1,0 " + -myr*2 + ",0Z";;
	}
}

//function drawPathSymbol(pathStr) {
//	  return d3.path(pathStr);
//}

function resizeLegend(){
	var bbox_g = $('#g_CPMlegend')[0].getBBox();
	svg_CPMLegend.attr("width", bbox_g.width + 40);
	svg_CPMLegend.attr("height", bbox_g.height + 30);
	return;
}

function findMarker(color) {
	//!!remove these symbols in the id otherwise the color cannot be displayed
	var id = color.replace(/[(), ]/g,'_');
    return "url(#" + id + ")";
};

// TODO: Move the codes to a new JS file: DrawFlows.js.
function pathstyle_straight(d) {
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		return pathOnOBM({ type:"LineString", coordinates: [locationByNodeID[d.source], locationByNodeID[d.target] ]});
	}
}

function pathstyle_Arc(d) {
	 if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		  return drawArc(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1], 
				  projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1]);
	 }
}

function drawArc(x1, y1, x2, y2, dr){
	var dx =  x1 - x2,
	  dy = y1 - y2, 
	  dr = Math.sqrt(dx * dx + dy * dy);
	return "M" +  x1 + "," +  y1 
	  + "A" + dr + "," + dr + " 0 0,1 " 
	  + x2 + "," + y2;
}

function pathstyle_straightwitharrow(d){
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold) 
		return drawStraightWithArrow(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowStrokeWidthScale(d.volume), volumeByNodeID[d.source], volumeByNodeID[d.target]);
}

function drawStraightWithArrow(x1, y1, x2, y2, flowSize, sourceSize, targetSize){
	var ndsize0 = Math.sqrt(sourceSize) / 3;
	var ndsize3 = Math.sqrt(targetSize) / 3;
	var width = flowSize;
	var dx = Math.abs(x2 - x1);
	var dy = Math.abs(y2 - y1);
	var dist = Math.sqrt(dx * dx + dy * dy);
	if (dist < (ndsize0 + ndsize3) * 1.6)
		return;

	var haselbow = true;
	var arrowlen = 3.0;
	if (dist < (ndsize0 + ndsize3) * 2.5)
		arrowlen = 1.0;

	// Shorten the length so that the line only touches the node circle
	if (haselbow) {
		x1 = x1 + (x2 - x1) * ndsize0 / dist;
		y1 = y1 + (y2 - y1) * ndsize0 / dist;
		x2 = x2 - (x2 - x1) * ndsize3 / (dist - ndsize0);
		y2 = y2 - (y2 - y1) * ndsize3 / (dist - ndsize0);
	}
	// Four corners of a flow line
	var xc1 = null, yc1 = null, xc2 = null, yc2 = null;
	// Four points to round the head
	var x2elbow1 = null, y2elbow1 = null;
	var sign = 1;
	var xdelta = null, ydelta = null, xarrowdelta = null, yarrowdelta = null, xgap = null, ygap = null;
	var gap = width * 0.05;
	if (y1 == y2) { // horizontal
		xdelta = 0;
		ydelta = width / 2;
		xarrowdelta = 0;
		yarrowdelta = width / 1.0;
		xgap = 0;
		ygap = gap;
	} else if (x1 == x2) { // vertical
		ydelta = 0;
		xdelta = width / 2;
		yarrowdelta = 0;
		xarrowdelta = width / 1.0;
		xgap = gap;
		ygap = 0;
	} else {
		var v = (x2 - x1) / (y1 - y2);
		xdelta = width / 2.0 / Math.sqrt(1 + v * v);
		ydelta = Math.abs(xdelta * v);
		xarrowdelta = width / Math.sqrt(1 + v * v);
		yarrowdelta = Math.abs(xarrowdelta * v);
		xgap = gap / Math.sqrt(1 + v * v);
		ygap = Math.abs(xgap * v);
		if (v > 0)
			sign = -1;
	}

	x1 = (y1 >= y2) ? x1 + xgap : x1 - xgap;
	x2 = (y1 >= y2) ? x2 + xgap : x2 - xgap;
	y1 = (x1 >= x2) ? y1 - ygap : y1 + ygap;
	y2 = (x1 >= x2) ? y2 - ygap : y2 + ygap;

	xc1 = (y1 >= y2) ? x1 + xdelta : x1 - xdelta;
	yc1 = (x1 >= x2) ? y1 - ydelta : y1 + ydelta;
	xc2 = (y1 >= y2) ? x2 + xdelta + arrowlen * ydelta * sign : x2 - xdelta
			- arrowlen * ydelta * sign;
	yc2 = (x1 >= x2) ? y2 - ydelta + arrowlen * xdelta * sign : y2 + ydelta
			- arrowlen * xdelta * sign;

	x2elbow1 = (y1 >= y2) ? x2 + xarrowdelta + arrowlen * ydelta * sign : x2
			- xarrowdelta - arrowlen * ydelta * sign;
	y2elbow1 = (x1 >= x2) ? y2 - yarrowdelta + arrowlen * xdelta * sign : y2
			+ yarrowdelta - arrowlen * xdelta * sign;

	return "M" + x1 + "," + y1 + "L" + xc1 + "," + yc1 + "L" + xc2 + "," + yc2
			+ "L" + x2elbow1 + "," + y2elbow1 + "L" + x2 + "," + y2 + "Z";
}

function pathstyle_curve(d){
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		var flowVolume = $("#Flow_DisplayAsAbs-CB").is(":checked") ? flowStrokeWidthScale(Math.abs(d.volume)) : flowStrokeWidthScale(d.volume);
		return drawCurve(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowVolume, volumeByNodeID[d.source], volumeByNodeID[d.target]);
	}
}

function drawCurve(x0, y0, x3, y3, flowSize, sourceSize, targetSize, isDrawingLegend){
    var arrowlen = 2.42;
    arrowwidthconstant = flowSize * 1.1;
	if(flowSize < 10 && flowSize >= 8){
		arrowlen = 2.64;
		arrowwidthconstant = flowSize * 1.2;
	}
	else if(flowSize < 8 && flowSize >= 6){
		arrowlen = 3.08;
		arrowwidthconstant = flowSize * 1.4;
	}
	else if(flowSize < 6 && flowSize >= 4){
		arrowlen = 4.4;
		arrowwidthconstant = flowSize * 2;
	}
	else if(flowSize < 4 && flowSize >= 3){
		arrowlen = 6.6;
		arrowwidthconstant = flowSize * 3;
	}
	else if(flowSize < 3 && flowSize >= 2){
		arrowlen = 8.8;
		arrowwidthconstant = flowSize * 4;
	}
	else if(flowSize < 2){
		arrowlen = 11;
		arrowwidthconstant = flowSize * 5;
	}
	
	var ndsize0 = nodescale(parseFloat(sourceSize));
	var ndsize3 = nodescale(parseFloat(targetSize));
	var dx = Math.abs(x3 - x0);
	var dy = Math.abs(y3 - y0);
	
	var len = Math.sqrt(dx * dx + dy * dy);
	if (len < (ndsize0 + ndsize3) * 1.2)
		return;
	
	var noarrow = false;
	if (len < (ndsize0 + ndsize3) * 2.5 && (isDrawingLegend == undefined || isDrawingLegend == false))
		noarrow = true;

	var haselbow = true;

	// Shorten the length so that the line only touches the node circle
	if (haselbow) {
		x0 = x0 + (x3 - x0) * ndsize0 / len;
		y0 = y0 + (y3 - y0) * ndsize0 / len;
		x3 = x3 - (x3 - x0) * ndsize3 / (len - ndsize0);
		y3 = y3 - (y3 - y0) * ndsize3 / (len - ndsize0);
	}

	// Four corners of a flow line
	var xc1 = null, yc1 = null, xc2 = null, yc2 = null;
	// Four points to round the head
	var x3elbow1 = null, y3elbow1 = null;
	var sign = -1;
	var xdelta = null, ydelta = null, xarrowdelta = null, yarrowdelta = null, xgap = null, ygap = null;
	var gap = flowSize * 0.05;
	if (y0 == y3) { // horizontal
		xdelta = 0;
		ydelta = flowSize / 2;
		xarrowdelta = 0;
		yarrowdelta = arrowwidthconstant / 1.0;
		xgap = 0;
		ygap = gap;
	} else if (x0 == x3) { // vertical
		ydelta = 0;
		xdelta = flowSize / 2;
		yarrowdelta = 0;
		xarrowdelta = arrowwidthconstant / 1.0;
		xgap = gap;
		ygap = 0;
	} else {
		var v = (x3 - x0) / (y0 - y3);
		xdelta = flowSize / 2.0 /  Math.sqrt(1 + v * v);
		ydelta = Math.abs(xdelta * v);
		xarrowdelta = arrowwidthconstant / Math.sqrt(1 + v * v);
		yarrowdelta = Math.abs(xarrowdelta * v);
		xgap = gap / Math.sqrt(1 + v * v);
		ygap = Math.abs(xgap * v);
		if (v < 0)
			sign = 1;
	}
	x0 = (y0 > y3) ? x0 + xgap : x0 - xgap;
	x3 = (y0 > y3) ? x3 + xgap : x3 - xgap;
	y0 = (x0 > x3) ? y0 - ygap : y0 + ygap;
	y3 = (x0 > x3) ? y3 - ygap : y3 + ygap;

	var righthandrule = true;
	if(righthandrule)
	{
		xc1 = (y0 > y3) ? x0 + xdelta / 2 : x0 - xdelta / 2;
		yc1 = (x0 > x3) ? y0 - ydelta / 2 : y0 + ydelta / 2;
		if (noarrow) {
			yc2 = (x0 > x3) ? y3 - ydelta : y3 + ydelta;
			xc2 = (y0 > y3) ? x3 + xdelta : x3 - xdelta;
		} else {
			yc2 = (x0 > x3) ? y3 - ydelta + arrowlen * xdelta * sign : y3 + ydelta - arrowlen * xdelta * sign;
			xc2 = (y0 > y3) ? x3 + xdelta + arrowlen * ydelta * sign : x3 - xdelta - arrowlen * ydelta * sign;
		}
		x3elbow1 = (y0 > y3) ? x3 + xarrowdelta + arrowlen * ydelta * sign : x3 - xarrowdelta - arrowlen * ydelta
				* sign;
		y3elbow1 = (x0 > x3) ? y3 - yarrowdelta + arrowlen * xdelta * sign : y3 + yarrowdelta - arrowlen * xdelta
				* sign;


		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var x13rd = (y0 > y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var y13rd = (x0 > x3) ? y0 - arcydelta : y0 + arcydelta;
		var x23rd = (y0 > y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var y23rd = (x0 > x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var xc13rd = (y0 > y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var yc13rd = (x0 > x3) ? y0 - arcydelta : y0 + arcydelta;
		var xc23rd = (y0 > y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var yc23rd = (x0 > x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;

	}else
	{
		xc1 = (y0 < y3) ? x0 + xdelta / 2 : x0 - xdelta / 2;
		yc1 = (x0 < x3) ? y0 - ydelta / 2 : y0 + ydelta / 2;
		if (noarrow) {
			yc2 = (x0 < x3) ? y3 - ydelta : y3 + ydelta;
			xc2 = (y0 < y3) ? x3 + xdelta : x3 - xdelta;
		} else {
			yc2 = (x0 < x3) ? y3 - ydelta + 2.5 * xdelta * sign : y3 + ydelta - 2.5 * xdelta * sign;
			xc2 = (y0 < y3) ? x3 + xdelta + 2.5 * ydelta * sign : x3 - xdelta - 2.5 * ydelta * sign;
		}
		x3elbow1 = (y0 < y3) ? x3 + xarrowdelta + 2.5 * ydelta * sign : x3 - xarrowdelta - 2.5 * ydelta
				* sign;
		y3elbow1 = (x0 < x3) ? y3 - yarrowdelta + 2.5 * xdelta * sign : y3 + yarrowdelta - 2.5 * xdelta
				* sign;



		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var x13rd = (y0 < y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var y13rd = (x0 < x3) ? y0 - arcydelta : y0 + arcydelta;
		var x23rd = (y0 < y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var y23rd = (x0 < x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var xc13rd = (y0 < y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var yc13rd = (x0 < x3) ? y0 - arcydelta : y0 + arcydelta;
		var xc23rd = (y0 < y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var yc23rd = (x0 < x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
	}

	if (!noarrow)
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3elbow1 + "," + y3elbow1 
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
	else
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
}

function drawCurveOriginal(x0, y0, x3, y3, flowSize, sourceSize, targetSize, isDrawingLegend){
	var ndsize0 = nodescale(parseFloat(sourceSize));
	var ndsize3 = nodescale(parseFloat(targetSize));
	var dx = Math.abs(x3 - x0);
	var dy = Math.abs(y3 - y0);
	
	var len = Math.sqrt(dx * dx + dy * dy);
	if (len < (ndsize0 + ndsize3) * 1.2)
		return;
	
	var noarrow = false;
	if (len < (ndsize0 + ndsize3) * 2.5 && (isDrawingLegend == undefined || isDrawingLegend == false))
		noarrow = true;

	var haselbow = true;

	// Shorten the length so that the line only touches the node circle
	if (haselbow) {
		x0 = x0 + (x3 - x0) * ndsize0 / len;
		y0 = y0 + (y3 - y0) * ndsize0 / len;
		x3 = x3 - (x3 - x0) * ndsize3 / (len - ndsize0);
		y3 = y3 - (y3 - y0) * ndsize3 / (len - ndsize0);
	}

	// Four corners of a flow line
	var xc1 = null, yc1 = null, xc2 = null, yc2 = null;
	// Four points to round the head
	var x3elbow1 = null, y3elbow1 = null;
	var sign = -1;
	var xdelta = null, ydelta = null, xarrowdelta = null, yarrowdelta = null;
	if (y0 == y3) { // horizontal
		xdelta = 0;
		ydelta = flowSize / 2;
		xarrowdelta = 0;
		yarrowdelta = flowSize / 1.0;
	} else if (x0 == x3) { // vertical
		ydelta = 0;
		xdelta = flowSize / 2;
		yarrowdelta = 0;
		xarrowdelta = flowSize / 1.0;
	} else {
		var v = (x3 - x0) / (y0 - y3);
		xdelta = flowSize / 2.0 /  Math.sqrt(1 + v * v);
		ydelta = Math.abs(xdelta * v);
		xarrowdelta = flowSize / 1.0 /  Math.sqrt(1 + v * v);
		yarrowdelta = Math.abs(xarrowdelta * v);
		if (v < 0)
			sign = 1;
	}

	var righthandrule = true;
	if(righthandrule)
	{
		xc1 = (y0 > y3) ? x0 + xdelta / 2 : x0 - xdelta / 2;
		yc1 = (x0 > x3) ? y0 - ydelta / 2 : y0 + ydelta / 2;
		if (noarrow) {
			yc2 = (x0 > x3) ? y3 - ydelta : y3 + ydelta;
			xc2 = (y0 > y3) ? x3 + xdelta : x3 - xdelta;
		} else {
			yc2 = (x0 > x3) ? y3 - ydelta + 2.5 * xdelta * sign : y3 + ydelta - 2.5 * xdelta * sign;
			xc2 = (y0 > y3) ? x3 + xdelta + 2.5 * ydelta * sign : x3 - xdelta - 2.5 * ydelta * sign;
		}
		x3elbow1 = (y0 > y3) ? x3 + xarrowdelta + 2.5 * ydelta * sign : x3 - xarrowdelta - 2.5 * ydelta
				* sign;
		y3elbow1 = (x0 > x3) ? y3 - yarrowdelta + 2.5 * xdelta * sign : y3 + yarrowdelta - 2.5 * xdelta
				* sign;



		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var x13rd = (y0 > y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var y13rd = (x0 > x3) ? y0 - arcydelta : y0 + arcydelta;
		var x23rd = (y0 > y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var y23rd = (x0 > x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var xc13rd = (y0 > y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var yc13rd = (x0 > x3) ? y0 - arcydelta : y0 + arcydelta;
		var xc23rd = (y0 > y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var yc23rd = (x0 > x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;

	}else
	{
		xc1 = (y0 < y3) ? x0 + xdelta / 2 : x0 - xdelta / 2;
		yc1 = (x0 < x3) ? y0 - ydelta / 2 : y0 + ydelta / 2;
		if (noarrow) {
			yc2 = (x0 < x3) ? y3 - ydelta : y3 + ydelta;
			xc2 = (y0 < y3) ? x3 + xdelta : x3 - xdelta;
		} else {
			yc2 = (x0 < x3) ? y3 - ydelta + 2.5 * xdelta * sign : y3 + ydelta - 2.5 * xdelta * sign;
			xc2 = (y0 < y3) ? x3 + xdelta + 2.5 * ydelta * sign : x3 - xdelta - 2.5 * ydelta * sign;
		}
		x3elbow1 = (y0 < y3) ? x3 + xarrowdelta + 2.5 * ydelta * sign : x3 - xarrowdelta - 2.5 * ydelta
				* sign;
		y3elbow1 = (x0 < x3) ? y3 - yarrowdelta + 2.5 * xdelta * sign : y3 + yarrowdelta - 2.5 * xdelta
				* sign;



		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var x13rd = (y0 < y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var y13rd = (x0 < x3) ? y0 - arcydelta : y0 + arcydelta;
		var x23rd = (y0 < y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var y23rd = (x0 < x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var xc13rd = (y0 < y3) ? x0 + arcxdelta : x0 - arcxdelta;
		var yc13rd = (x0 < x3) ? y0 - arcydelta : y0 + arcydelta;
		var xc23rd = (y0 < y3) ? x0 + (x3 - x0) / 3 + arcxdelta : x0 + (x3 - x0) / 3 - arcxdelta;
		var yc23rd = (x0 < x3) ? y0 + (y3 - y0) / 3 - arcydelta : y0 + (y3 - y0) / 3 + arcydelta;
	}

	if (!noarrow)
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3elbow1 + "," + y3elbow1 
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
	else
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
}

//function setPathstyle_straight(){
//	g3.selectAll("g").selectAll("path")
//  	.attr("d", pathstyle_straight)
//    .attr("marker-end", function(d){
//    	  if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold)
//    		  return findMarker(flows_color(d.volume));
//    	  });
//	currentPathProjection = pathstyle_straight;
//}
//
//function setPathstyle_Arc(){
//	g3.selectAll("g").selectAll("path")
//	  .attr("d", pathstyle_Arc)
//	  .attr("marker-end", function(d){
//	  	  if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold)
//	  		  return findMarker(flows_color(d.volume));
//	  	  });
//	currentPathProjection = pathstyle_Arc;
//}

function setPathstyle_straightwitharrow(){
	g3.selectAll("g").selectAll("path")
	  .attr("d", pathstyle_straightwitharrow)
	  .attr("marker-end", "");
	currentPathProjection = pathstyle_straightwitharrow;
}

function setPathstyle_curve(){
	g3.selectAll("g").selectAll("path")
	  .attr("d", pathstyle_curve)
	  .attr("marker-end", "");
	currentPathProjection = pathstyle_curve;
}

function resetColorSchemeAndLegendForCPM(){
	var cfMethod = document.getElementById("CPM_Classification-Select").value;
	var clrScheme = document.getElementById("CPM_ColorScheme-Select").value;
	var clsNum = document.getElementById("CPM_ClassNum-Input").value;
	var opacity = document.getElementById("CPM_Opacity-Input").value * 1.0 / 100;
	var strokeColor = document.getElementById("CPM_StrokeColor-Select").value;
	var strokeWidth = document.getElementById("CPM_StrokeWidth-Input").value;
	var breakInput = document.getElementById("CPM_ManualBreak-Input").value;
	var toFlipColor = $("#CPM_FlipLgClr-CB").is(":checked");
	
	var CPM_Color;
	if(cfMethod == "Quantile"){
		CPM_Color = d3.scaleQuantile()
		.domain(CPMValue)
		.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum));
	}else if(cfMethod == "EqualInterval"){
		CPM_Color = d3.scaleQuantize()
		.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum))
		.domain(d3.extent(CPMValue));
	}else if(cfMethod == "NaturalBreak"){
		CPM_Color =  d3.scaleThreshold();
		var naturalBreaks = ss.ckmeans(CPMValue, clsNum).map(v => v.pop());
		CPM_Color.domain(naturalBreaks);
		CPM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum));
	}else if(cfMethod == "Linear"){
		var colorForUnclassed;
		colorForUnclassed = getLegendColorSchemeOfUnclassified(toFlipColor, clrScheme);
		CPM_Color = d3.scaleLinear()
		.range(colorForUnclassed)
		.domain([d3.min(CPMValue), d3.max(CPMValue)]);
		
		var selectedGeomID = $("#CPM_BMPK-Select option:selected").text();
		g1.selectAll("path")
		//The way that we load features into the map
		.attr("fill", function(d) { 
			return CPM_Color(CPMIdValueMap.get((d.properties[selectedGeomID]).toString()));
		})
		.attr("stroke", strokeColor)
		.attr("stroke-width", strokeWidth)
		.attr("opacity", opacity)
		.attr("class","");
			
		var filename = document.getElementById('CPM_CSV-Input').files[0].name;
		svg_CPMLegend = addLegend(svg_CPMLegend, filename, CPM_Color, "svg_CPMLegend", "CPM_UnClassified", $("#CMP_LegendShow-CB").is(":checked"));
		return;
	}else if(cfMethod == "ManualBreak"){
		CPM_Color = d3.scaleThreshold();
		if(breakInput == "") return;
		var inputArr = breakInput.split(" ");
		for(var i=0; i<inputArr.length; i++) {
			if(isNumber(inputArr[i]))
				inputArr[i] = parseFloat(inputArr[i]); 
			else{
				alert('Your break input can not be parsed to numbers, please make sure to use numbers ONLY and follow the format requirement in "help".');
				return;
			}
		} 
		
		if(inputArr.length < 3){
			alert('You should have at least 4 classes. (three break inputs)');
			return;
		}else if(inputArr.length > 10){
			alert('You should have at most 11 classes. (ten break inputs)');
			return;
		}
		
		CPM_Color.domain(inputArr);
		CPM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, inputArr.length + 1));
	}
	
	var file = document.getElementById('CPM_CSV-Input').files[0];
	var CPMField = $("#CPM_Value-Select option:selected").text();
	var selectedGeomID = $("#CPM_BMPK-Select option:selected").text();
	g1.attr("class", clrScheme);
	g1.selectAll("path")
	//The way that we load features into the map
	.attr("fill", function(d) { 
		if(file != undefined)
			return CPM_Color(CPMIdValueMap.get((d.properties[selectedGeomID]).toString()));
		else 
			return;
	})
	.attr("stroke", strokeColor)
	.attr("stroke-width", strokeWidth)
	.attr("opacity", opacity)
	.selectAll("title")
    .text( function(d){
        return `${selectedGeomID}: ` + d.properties[selectedGeomID] + "\n" + `${CPMField}: ` + +CPMIdValueMap.get((d.properties[selectedGeomID].toString()));
    });
		
	if(file != undefined)
	{
		var filename = file.name;
		var options = "";
		if(cfMethod == "ManualBreak")
			options = "ManualBreak";
		else if(cfMethod == "NaturalBreak")
			options = "NaturalBreak";
		svg_CPMLegend = addLegend(svg_CPMLegend, filename, CPM_Color, "svg_CPMLegend", "CPM_Classified", $("#CMP_LegendShow-CB").is(":checked"), clrScheme, "", options);
	}
}

function isNumber(n) { return !isNaN(parseFloat(n)) && !isNaN(n - 0) }

var flowStrokeWidthScale;
function resetColorSchemeAndLegendForFlows(){
	var cfMethod = document.getElementById("FlowMap_Classification-Select").value;
	var clrScheme = document.getElementById("FlowMap_ColorScheme-Select").value;
	var clsNum = +document.getElementById("FlowMap_ClassNum-Input").value;
	var flowStyle = document.getElementById("FlowMap_Style-Select").value;
	//var showTopFromNodeNum = document.getElementById("FlowMap_TopFlowFromNodeNum-Input").value;
	var showTopFlowsNumFromAll = document.getElementById("FlowMap_TopFlowFromAllFlows-Input").value;
	var IDField = document.getElementById("Point_ID-Select").value;
	var FM_Color;
	var breakInput = document.getElementById("FlowMap_ManualBreak-Input").value;
	var toFlipColor = $("#Flow_FlipLgClr-CB").is(":checked");
	var widthMax = +document.getElementById("FlowMap_FlowWidth_Max-Input").value;
	var widthMin = +document.getElementById("FlowMap_FlowWidth_Min-Input").value;
	topVolumeList_modified = $("#Flow_DisplayAsAbs-CB").is(":checked") ?  topVolumeList.map(Math.abs) : topVolumeList;
	
	if(cfMethod == "Quantile"){
		FM_Color = d3.scaleQuantile();
		FM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum))
		FM_Color.domain(topVolumeList);
		
		flowStrokeWidthScale = d3.scaleQuantile();
		flowStrokeWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowStrokeWidthScale.domain(topVolumeList_modified);
	}else if(cfMethod == "EqualInterval"){
		FM_Color = d3.scaleQuantize();
		FM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum));
		FM_Color.domain(d3.extent(topVolumeList));
		flowStrokeWidthScale = d3.scaleQuantize();
		flowStrokeWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowStrokeWidthScale.domain(d3.extent(topVolumeList_modified));
	}else if(cfMethod == "NaturalBreak"){
		FM_Color =  d3.scaleThreshold();
		var naturalBreaksForColors = ss.ckmeans(topVolumeList, clsNum).map(v => v.pop());
		FM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, clsNum))
		FM_Color.domain(naturalBreaksForColors);
		var naturalBreaksForWidth = ss.ckmeans(topVolumeList_modified, clsNum).map(v => v.pop());
		flowStrokeWidthScale = d3.scaleThreshold();
		flowStrokeWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowStrokeWidthScale.domain(naturalBreaksForWidth);
	}else if(cfMethod == "ManualBreak"){
		FM_Color = d3.scaleThreshold();
		if(breakInput == "") return;
		var inputArr = breakInput.split(" ");
		for(var i=0; i<inputArr.length; i++) {
			if(isNumber(inputArr[i]))
				inputArr[i] = parseFloat(inputArr[i]); 
			else{
				alert('Your break input can not be parsed to numbers, please make sure to use numbers ONLY and follow the format requirement in "help".');
				return;
			}
		} 
		
		if(inputArr.length < 3){
			alert('You should have at least 4 classes. (three break inputs)');
			return;
		}else if(inputArr.length > 10){
			alert('You should have at most 11 classes. (ten break inputs)');
			return;
		}
		
		FM_Color.domain(inputArr);
		FM_Color.range(getLegendColorScheme(toFlipColor, clrScheme, inputArr.length + 1));
		
		flowStrokeWidthScale = d3.scaleThreshold();
		flowStrokeWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowStrokeWidthScale.domain(inputArr);
	}else if(cfMethod == "Proportional"){
		FM_Color = d3.scaleLinear()
		.range(getLegendColorSchemeOfUnclassified(toFlipColor, clrScheme))
		.domain([d3.min(topVolumeList_modified), d3.max(topVolumeList_modified)]);
		
		flowStrokeWidthScale = d3.scaleLinear().range([widthMin, widthMax])
		.domain([d3.min(topVolumeList_modified), d3.max(topVolumeList_modified)]);
	}

	
	if($("#Flow_DisplayAsAbs-CB").is(":checked")){
		FM_Color = d3.scaleThreshold();
		FM_Color.range(getLegendColorSchemeOfUnclassified(toFlipColor, clrScheme))
		.domain([0]);
	}
	
	var selectedGeomID = $("#CPM_BMPK-Select option:selected").text();
	var threshold;
	if(showTopFlowsNumFromAll - 1 < 0) threshold = Number.POSITIVE_INFINITY;
	else threshold = topVolumeList_modified[showTopFlowsNumFromAll - 1];
	
	var selectedOriginID = document.getElementById("Flow_SourceID-Select").value;
	var selectedTargetID = document.getElementById("Flow_TargetID-Select").value;
	var flowVolumeField =  document.getElementById("Flow_Volume-Select").value;
	g3.attr("class", clrScheme);
	//g3.selectAll("g").selectAll("path")
	var flows = g3.selectAll("path")
	//not show all flows
//	.style("display", "none")
//	.data(function(d) { 
//		// ------------------------------This is for showing the top flows from each node------------------------------
//			/*if(linksByOrigin[d[IDField]] == null) return [];
//			else if(linksByOrigin[d[IDField]].length <= showTopFromNodeNum) return linksByOrigin[d[IDField]];
//			else return linksByOrigin[d[IDField]].slice(0, showTopFromNodeNum);*/
//		// ------------------------------Showing the top flows from each node ends-------------------------------------
//		
//		// ------------------------------This is for showing the top flows from all flows------------------------------
//		/*if(linksByOrigin[d[IDField]] == null) return [];
//		else{
//			var threshold = topVolumeList[showTopFlowsNumFromAll - 1];
//			for(var i = 0; i < linksByOrigin[d[IDField]].length; i++){
//				if(linksByOrigin[d[IDField]][i].volume )
//			}
//			return linksByOrigin[d[IDField]];
//		}*/
//		// ------------------------------Showing the top flows from all flows ends-------------------------------------
//		})
	//The way that we load features into the map
	.attr("fill", function(d) { return FM_Color(d.volume);	})
	.attr("d", currentPathProjection)
	//show flows within top number
	.style("display", function(d) {
		var inputVolume = $("#Flow_DisplayAsAbs-CB").is(":checked") ? Math.abs(d.volume) : d.volume;
		if(inputVolume >= threshold) return "block"; else return "none";
	})
	.selectAll("title")
    .text( function(d){
    	var test = d;
        return `${selectedOriginID}: ` + d["source"] + "\n" 
        + `${selectedTargetID}: ` + d["target"] + "\n" 
        + `${flowVolumeField}: ` + d["volume"];
    });;
	if($("#Flow_Stroke-CB").is(":checked")){
		flows.style("stroke-width", 0.5)
		.style("stroke", "black");
	}else{
		flows.style("stroke-width", 0)
		.style("stroke", "none");
	}
	
    //add legend for flows.
	var filename = document.getElementById('Flow_File-Input').files[0].name;
	var clsfctType = cfMethod != "Proportional" ? "flow_Classified" : "flow_Unclassified";
	svg_FlowLegend = addLegend(svg_FlowLegend, filename, FM_Color, "svg_FlowLegend", clsfctType, $("#Flow_LegendShow-CB").is(":checked"), clrScheme, flowStyle, cfMethod, clrScheme == "Black" ? true : false);
}

function getFlowWidthRange(max, min, clsNum)
{
	var range = [],
	interval = (max - min) / ((clsNum - 1) * 1.0);
	for(var i = 0; i < clsNum; i++)
	{
		range.push(+min + i * interval);
	}
	return range;
}

function resetColorSchemeAndLegendForPoints(){
	var cfMethod = document.getElementById("Point_Classification-Select").value;
	var clrScheme = document.getElementById("Point_ColorScheme-Select").value;
	var radiusMin = +document.getElementById("Point_Radius_Min-Input").value;
	var radiusMax = +document.getElementById("Point_Radius_Max-Input").value;
	var strokeColor = document.getElementById("Point_StrokeColor-Select").value;
	var strokeWidth = document.getElementById("Point_StrokeWidth-Input").value;
	var volumeField_Points = document.getElementById("Point_Volume-Select").value;
	var breakInput = document.getElementById("Point_ManualBreak-Input").value;
	var toFlipColor = $("#Point_FlipLgClr-CB").is(":checked");
	nodesizeattribute_modified = $("#Point_DisplayAsAbs-CB").is(":checked") ? nodesizeattribute.map(Math.abs) : nodesizeattribute;
	// Currently point symbols only supports linear scale.
	if(cfMethod == "Proportional"){
		nodescale = d3.scaleLinear().range([radiusMin, radiusMax])
		.domain([d3.min(nodesizeattribute_modified), d3.max(nodesizeattribute_modified)]);
		var colorForUnclassed = getLegendColorSchemeOfUnclassified(toFlipColor, clrScheme);
		point_Color = d3.scaleLinear()
		.range(colorForUnclassed)
		.domain([d3.min(nodesizeattribute), d3.max(nodesizeattribute)]);
	}else if (cfMethod == "ManualBreak"){
		var point_Color = d3.scaleThreshold();
		if(breakInput == "") return;
		var inputArr = breakInput.split(" ");
		for(var i=0; i<inputArr.length; i++) {
			if(isNumber(inputArr[i]))
				inputArr[i] = parseFloat(inputArr[i]); 
			else{
				alert('Your break input can not be parsed to numbers, please make sure to use numbers ONLY and follow the format requirement in "help".');
				return;
			}
		} 
		
		if(inputArr.length < 3){
			alert('You should have at least 4 classes. (three break inputs)');
			return;
		}else if(inputArr.length > 10){
			alert('You should have at most 11 classes. (ten break inputs)');
			return;
		}
		
		point_Color.domain(inputArr);
		point_Color.range(getLegendColorScheme(toFlipColor, clrScheme, inputArr.length + 1));
		
		var MBRadius = [];
		for(var i = 0; i < inputArr.length + 1; i++){
			MBRadius.push(parseFloat(radiusMin) + i * (radiusMax - radiusMin) * 1.0 / inputArr.length);
		}
		
		nodescale = d3.scaleThreshold().range(MBRadius)
		.domain(inputArr);
	}
	
	
	var inputScale;
	if($("#Point_DisplayAsAbs-CB").is(":checked")){
		point_Color = d3.scaleThreshold();
		point_Color.range(getLegendColorSchemeOfUnclassified(toFlipColor, clrScheme))
		.domain([0]);
		inputScale = point_Color;
	}else{
		inputScale = nodescale;
	}
	
	var selectedGeomID = document.getElementById("Point_ID-Select").value;
	var XField = document.getElementById("Point_X-Select").value;
	var YField = document.getElementById("Point_Y-Select").value;
	g2.selectAll("circle")
	.attr("r", function(d) {
		if($("#Point_DisplayAsAbs-CB").is(":checked")){
			return nodescale(Math.abs(d[volumeField_Points]));
		}else{
			return nodescale(d[volumeField_Points]);
		}
	})
	//The way that we load features into the map
	.attr("fill", function(d) { return point_Color(d[volumeField_Points]);})
	.attr("stroke", strokeColor)
	.attr("stroke-width", strokeWidth)
	.selectAll("title")
    .text( function(d){
        return `${selectedGeomID}: ` + d[selectedGeomID] + "\n" 
        + `${XField}: ` + d[XField] + "\n" 
        + `${YField}: ` + d[YField] + "\n" 
        + `${volumeField_Points}: ` + d[volumeField_Points];
    });
	
	var filename = document.getElementById('Point_File-Input').files[0].name;
	var options = "";
	if(cfMethod == "ManualBreak")
		options = "ManualBreak";
	else if(cfMethod == "NaturalBreak")
		options = "NaturalBreak";
	//Change the size of point may also influence flows. Refresh the location of flows here as well.
	map.render();
	
	svg_PointLegend = addLegend(svg_PointLegend, filename, inputScale, "svg_PointLegend", "Point", $("#Point_LegendShow-CB").is(":checked"), "", "", options);
}

function getLegendColorScheme(flip, schemeName, classNum){
	if(schemeName == "Black"){
		var blkScheme = [];
		for(var i = 0; i < classNum; i++){
			blkScheme.push("#000000");
		}
		return blkScheme;
	}
	if(!(classNum in colorbrewer[schemeName])){
		alert('Your class number is more than or less than supported number.');
		return null;
	}
	if(flip == true){
		return colorbrewer[schemeName][classNum];
	}else{
		return colorbrewer[schemeName][classNum].slice().reverse();
	}
}

function getLegendColorSchemeOfUnclassified(flip, schemeName){
	if(schemeName == "Black"){
		return ["#000000", "#000000"];
	}
	if(flip == true){
		return [colorbrewer[schemeName][9][0], colorbrewer[schemeName][9][8]];
	}else{
		return [colorbrewer[schemeName][9][8], colorbrewer[schemeName][9][0]];
	}
}