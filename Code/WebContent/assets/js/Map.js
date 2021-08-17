function makePointAndFlowMap(){
	if(!pointData) {
		popErrorWindow("Please input point data first!"); return null;
	}
	  
	if(!checkLegendInput("Flow_LegendTitle-Input", "Flow")){
		return;
	}
	  
	if(!checkLegendInput("Point_LegendTitle-Input", "Point")){
		return;
	}
	  
	if(!checkChangeMap()){
		return;
	}
	updatePointMapSettings();
	updateFlowMapSettings();
	
	IDField_Points = pointMapSettings.id;
    XField_Points = pointMapSettings.X;
    YField_Points = pointMapSettings.Y;
    volumeField_Points = pointMapSettings.volume;
	originIdField = flowMapSettings.origin;
    destinationIdField = flowMapSettings.destination;
    volumeField_Flows = flowMapSettings.volume;
    
    if(!checkFieldInput(pointData, "point ID", IDField_Points)){
  	  return;
    }
    
    if(!checkFieldInput(pointData, "point X field", XField_Points)){
  	  return;
    }
    
    if(!checkFieldInput(pointData, "point Y field", YField_Points)){
  	  return;
    }
    
    if(!checkFieldInput(pointData, "point value field", volumeField_Points)){
  	  return;
    }
    
    if($("#Point_Classification-Select").val() == "ManualBreak" && !$("#Point_ManualBreak-Input").val()){
  	  alertManualBreakInputError(); 
    }
    
    if($("#Flow_Classification-Select").val() == "ManualBreak" && !$("#Flow_ManualBreak-Input").val()){
  	  alertManualBreakInputError(); 
    }

	if(flowData){
		if(!checkFieldInput(flowData, "flow origin", originIdField)){
			return;
		}
	
		if(!checkFieldInput(flowData, "flow destination", destinationIdField)){
		  	return;
		}
		
		if(!checkFieldInput(flowData, "flow volume", volumeField_Flows)){
		  	return;
		}
		
		// Check if top flow input exceeds the flow number of data.
		if($("#Flow_TopFlowFromAllFlows-Input").val() > flowData.length){
			alertMaxNumOfFlowError(flowData.length);
			$("#Flow_TopFlowFromAllFlows-Input").val(flowData.length);
			return;
		}
	}
	
	if(pointMapSettings.cfMethod == "ManualBreak"){
		pointMapSettings.breakArray =  getManualBreaksArray(pointMapSettings.breakInput, d3.min(nodesizeattribute), d3.max(nodesizeattribute));
		if(!pointMapSettings.breakArray) return;
	}
	
	if(flowMapSettings.cfMethod == "ManualBreak"){
		flowMapSettings.breakArray =  getManualBreaksArray(flowMapSettings.breakInput, topVolumeList[flowMapSettings.numTopFlows - 1], topVolumeList[0]);
		if(!flowMapSettings.breakArray) return;
	}
	
	preprocessData(flowData, pointData, originIdField, destinationIdField, volumeField_Flows, IDField_Points, XField_Points, YField_Points, volumeField_Points);
	// Only consider nodes with at least one flight.
	var filtedPointData = filterNodes(pointData, IDField_Points, XField_Points, YField_Points, volumeField_Points);
	// If nodes and flows are unmatched, pop up errors.
	if(filtedPointData && filtedPointData.length > 0){
		drawPoints(filtedPointData);
	}else{
		magnificPopupWindow("FlowUnmatched-Block", 'mfp-zoom-in');
		return;
	}
	if(flowData) drawFlows(flowData, filtedPointData, IDField_Points);
}

function magnificPopupWindow(id, type, ifDisplayClose = true, removeDelay = 500){
	if ($('#' + id).length) {
		const a = document.createElement("a");
		  a.setAttribute("id", "PopupTrigger-A");
		  document.body.appendChild(a);
		  a.click();
		
		 $('#PopupTrigger-A').magnificPopup({
	        items: {
	            src: '#' + id
	        },
//	        mainClass: type, // this class is for CSS animation below
	        callbacks: {
	            beforeOpen: function() {
	               this.st.mainClass = type;
	            }
	        },
	        removalDelay: removeDelay, 
	        showCloseBtn:ifDisplayClose,
	        closeBtnInside: ifDisplayClose,
	    }).click();
		document.body.removeChild(a);
	}
}

function popupWelcomeWindow(type){
	const a = document.createElement("a");
	  a.setAttribute("id", "PopupTrigger-A");
	  document.body.appendChild(a);
	  a.click();
	
	 $('#PopupTrigger-A').magnificPopup({
        items: {
            src: "#Welcome-Block"
        },
	    mainClass: type, // this class is for CSS animation below
//        callbacks: {
//            beforeOpen: function() {
//               this.st.mainClass = "";
//            },
//            beforeClose: function() {
//                this.st.mainClass = type;
//            },
//        },
        removalDelay: 500, 
        showCloseBtn: false,
        closeBtnInside: false,
    }).click();
	document.body.removeChild(a);
}
popupWelcomeWindow('mfp-zoom-in');

// Only usable on welcome window!
function magnificCloseWindow(id){
	if ($('#' + id).length) {
		$('#' + id).magnificPopup('close');
	}
}

function getColorRange(flip, schemeName, classNum, minColor, maxColor){
	if(schemeName == "Black"){
		var blkScheme = [];
		for(var i = 0; i < classNum; i++){
			blkScheme.push("#000000");
		}
		return blkScheme;
	}
	
	if(schemeName == "Custom"){
		if(flip){
			return d3.quantize(d3.interpolateRgb(maxColor, minColor), classNum);
		}else{
			return d3.quantize(d3.interpolateRgb(minColor, maxColor), classNum);
		}
	}
	
	if(!(classNum in colorbrewer[schemeName])){
		popErrorWindow('Your class number is more than or less than supported number of colors.');
		return null;
	}
	
	if(flip){
		return colorbrewer[schemeName][classNum].slice().reverse();
	}else{
		return colorbrewer[schemeName][classNum];
	}
}

function getColorRangeOfUnclassified(flip, schemeName, minColor, maxColor){
	if(schemeName == "Black"){
		return ["#000000", "#000000"];
	}
	
	if(schemeName == "Custom"){
		if(flip){
			return [maxColor, minColor];
		}else{
			return [minColor, maxColor];
		}
	}
	
	if(flip == true){
		return [colorbrewer[schemeName][9][8], colorbrewer[schemeName][9][0]];
	}else{
		return [colorbrewer[schemeName][9][0], colorbrewer[schemeName][9][8]];
	}
}

function makeChoroplethMap(){
	if(!CPMData){
		  popErrorWindow("Please input CSV file for Choropleth Map first!");
		  return;
	  }
	  
	  if(document.getElementById("CPM_LegendTitle-Input").value.charAt(0) == ' '){
		  popErrorWindow("Legend title can not start with a space!");
		  return;
	  }
	  
	  if(!baseMapData){
		  popErrorWindow("Region features are missing!");
		  return;
	  }
	  
	  updateBaseMapSettings();
	  drawChoroplethMapPolygons(baseMapData);
	  makeHashMapForChoroplethMap(CPMData);
	  
	  if(baseMapSettings.cfMethod == "ManualBreak"){
		  baseMapSettings.breakArray =  getManualBreaksArray(baseMapSettings.breakInput, d3.min(CPMValue), d3.max(CPMValue));
		  if(!baseMapSettings.breakArray) return;
	  }
	  
	  if(baseMapSettings.areNewFilesLoaded){
		  resetColorSchemeAndLegendForChoroplethMap();
		  popJointTable();
		  baseMapSettings.areNewFilesLoaded = false;
	  }else{
		  resetColorSchemeAndLegendForChoroplethMap();
	  }
}

function popJointTable(){
	// Update the joint table
	$("#NumFeatures-Span").html(baseMapSettings.numFeatures);
	$("#NumJoint-Span").html(baseMapSettings.numJoint);
	$("#NumDisjoint-Span").html(baseMapSettings.numDisjoint);
	magnificPopupWindow("CPM_JointTable-Block", 'mfp-zoom-in');
}

function projectToOnlineBaseMap(x) {
	if(x == undefined) return;
    var point = map.getPixelFromCoordinate(new ol.proj.transform([x[0], x[1]], "EPSG:4326", baseMap.projection));
    return [point[0], point[1]];
}

function projectToOnlineBaseMapTransform() {
	  return d3.geoTransform({
	    point: function(x, y) {
	    	var projectedCoor = new ol.proj.transform([x, y], "EPSG:4326", baseMap.projection);
	    	var point = map.getPixelFromCoordinate(projectedCoor);
	    	this.stream.point(point[0] , point[1]);
	    }
	  });
}

// Add or remove options for selection boxes.
function addOption(selectElement, optionName, value) {
	var x = document.getElementById(selectElement);
	var option = document.createElement("option");
	  option.text = optionName;
	  option.value = value;
	  x.add(option);
}

function updateSelectionBoxOptions(id, keyNames, values){
	removeOptions(id);
	if(!values){
		values = keyNames;
	}
	for(var i = 0; i < keyNames.length; i++){
		addOption(id, keyNames[i], values[i]);
	}
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

function isGeoJSON(jsonStr){
	if(JSON.parse(jsonStr).features){
		return true;
	}
	else {
		return false;
	}
}

function setViewOfMap(extent, padding){
	if(!extent || extent.length != 4){
		return;
	}
	
	var view = map.getView();
	var boundingBox = ol.extent.boundingExtent([[extent[0], extent[1]], [extent[2], extent[3]]]);
	view.fit(boundingBox, {padding: [padding, padding, padding, padding]});
}

//Define the path projection to the online base map! 
//Write like this because in d3.4 we must use project stream to create self-designed projection.
var pathOnOBM = d3.geoPath().projection(projectToOnlineBaseMapTransform());

function deleteExistingLayer(layerName){
	for(var i = 0; i < map.layers.length; i++)
		if(map.layers[i].name == layerName){
			map.removeLayer(map.layers[i]);
			break;
		}
}


// Make sure the d3 overlay move when the map is panned.
function resetMapOverlay(){
	var coor = map.getCoordinateFromPixel([0,0]);
	baseMap.overlay.setPosition(coor);
	
	if(!baseMapData && !pointData && !flowData && !refData)
		return;
	
    if(baseMapData){
        g1.selectAll("path").attr("d", function(d){return pathOnOBM(d);})
    }
    
    if(pointData){
        g2.selectAll("circle").attr("cx", function(d, i) { return projectToOnlineBaseMap(positions[i])[0];})
        	.attr("cy", function(d, i) { return projectToOnlineBaseMap(positions[i])[1];});
    }
    
    if(flowData){
    	g3.selectAll("path").attr("d", flowMapSettings.flowStyle);
    }
    
    if(refData){
    	gRef.selectAll("circle")
	    	.attr("cx", d => projectToOnlineBaseMap(d.geometry.coordinates)[0])
	    	.attr("cy", d => projectToOnlineBaseMap(d.geometry.coordinates)[1]);
    	gRef.selectAll("text")
    	.attr("dx", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[0] + 5;
        })
        .attr("dy", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[1];
        })
    }
}
map.on("postrender", resetMapOverlay);

function preprocessData(flowData, nodes, sourceField, targetField, volumeField_Flows, IDField, XField, YField, volumeField_Points){
	//all these variables are global. Set them as none when we are trying to load data again.
	linksByOrigin = {};
	countByNodeID = {};
	locationByNodeID = {};
	volumeByNodeID = {};
	inflowByNodeID = {};
	outflowByNodeID = {};
	nodeFlowAttributeArr = [];
	positions = [];
	flowthreshold = Number.MIN_SAFE_INTEGER;
	nodesizeattribute = [];
	volumearr = [];
	topVolumeList = [];
	topVolumeList_modified = [];
	topLinks = [];

	if(flowData){
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
	    	  volumeList.push(+volume);
		      originList.push(origin);
		      destinationList.push(destination);
		      
		      // Calculate flows stats
		      if(origin != destination){ // Exclude within flows.
		    	  if(!inflowByNodeID[destination]){
			    	  inflowByNodeID[destination] = 0;
			      }
			      inflowByNodeID[destination] += +volume;
					
			      if(!outflowByNodeID[origin]){
			    	  outflowByNodeID[origin] = 0;
			      }
			      outflowByNodeID[origin] += +volume;
		      }
	    });
		
		//Set the # of maximum top flows
		if($("#Flow_DisplayAsAbs-CB").is(":checked")){
			topLinks = calculateTopLinks(maxNumOfTopLinks, volumeList.map(Math.abs), volumeList, originList, destinationList);
	      }else{
	    	topLinks = calculateTopLinks(maxNumOfTopLinks, volumeList, volumeList, originList, destinationList);
	      }
	}
    
	return;
}

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


function isNumber(n) { return !isNaN(parseFloat(n)) && !isNaN(n - 0) }

function getBoundOfOverlay(){
	getPointExtent();
	getChoroplethMapExtent();
	var topLeft = [Math.min(Math.min(CPMBound[0][0], flowBound[0][0]), pointBound[0][0]), Math.min(Math.min(CPMBound[0][1], flowBound[0][1]), pointBound[0][1])];
	var bottomRight = [Math.max(Math.max(CPMBound[1][0], flowBound[1][0]), pointBound[1][0]), Math.max(Math.max(CPMBound[1][1], flowBound[1][1]), pointBound[1][1])];
	return [topLeft, bottomRight];
}

function getPointExtent(){
	if(!positions || positions.length == 0){
//		console.log("Point positions loading failed.");
		return;
	}
	
	var minX = d3.min(positions, function(d, i) {
    	return projectToOnlineBaseMap(positions[i])[0];
    }), 
    minY = d3.min(positions, function(d, i) {
    	  return projectToOnlineBaseMap(positions[i])[1] ;
    }), 
    maxX = d3.max(positions, function(d, i) {
    	  return projectToOnlineBaseMap(positions[i])[0];
    }), 
    maxY = d3.max(positions, function(d, i) {
    	  return projectToOnlineBaseMap(positions[i])[1];
    });
    pointBound = [[minX, minY],[maxX, maxY]];
}

function getChoroplethMapExtent(){
	if(!baseMapData){
//		console.log("Base map data loading failed.");
		return;
	}
	
	CPMBound = pathOnOBM.bounds(baseMapData);
}

function updateBaseMapSettings(){
	// Inputs for base map.
	baseMapSettings.baseMap =  document.getElementById("Online_BaseMap-Select").value;
	baseMapSettings.projection =  document.getElementById("MapProjection-Select").value;
	baseMapSettings.ifDisplayReferences =  $("#DisplayMapReference-CB").is(":checked");
	baseMapSettings.baseMapOpacity =  document.getElementById("CPM_BaseMapOpacity-Input").value;
	baseMapSettings.ifAddTitle = $("#AddTitle-CB").is(":checked");
	baseMapSettings.title =  document.getElementById("MapTitle-Input").value;
	baseMapSettings.ifAddNorthArrow = $("#AddNorthArrow-CB").is(":checked");
	baseMapSettings.ifAddProjectionLabel = $("#AddProjectionLabel-CB").is(":checked");
	
	//Reference
	baseMapSettings.ifUploadReferences = $("#UploadReference-CB").is(":checked");
	baseMapSettings.referenceField = document.getElementById("BaseMap_Reference-Select").value;
	baseMapSettings.labelFontSize = document.getElementById("BaseMap_LabelFontSize-Input").value;
	baseMapSettings.refRadius = document.getElementById("BaseMap_LabelRadius-Input").value;
	baseMapSettings.refColor = document.getElementById("BaseMap_LabelColor-Input").value;
	baseMapSettings.refOpacity = +document.getElementById("BaseMap_LabelOpacity-Input").value;
	baseMapSettings.ifRefTop = $("#BaseMap_LebelTop-CB").is(":checked");
	
	// Inputs for choroplethMap
	baseMapSettings.cfMethod =  document.getElementById("CPM_Classification-Select").value; // Classification method.
	baseMapSettings.clrScheme =  document.getElementById("CPM_ColorScheme-Select").value; // Color scheme.
	baseMapSettings.minCustomColor = document.getElementById("CPM_MinCustomColor-Input").value;
	baseMapSettings.maxCustomColor = document.getElementById("CPM_MaxCustomColor-Input").value;
	baseMapSettings.ifFlipColor =  $("#CPM_FlipLgClr-CB").is(":checked"); // If to flip the color.
	baseMapSettings.decimalPlaces =  $("#CPM_LegendDP-Input").val();
	baseMapSettings.clsNum =  document.getElementById("CPM_ClassNum-Input").value; // Number of classes
	baseMapSettings.fillOpacity =  document.getElementById("CPM_FillOpacity-Input").value;
	baseMapSettings.strokeColor =  document.getElementById("CPM_StrokeColor-Input").value;
	baseMapSettings.strokeWidth =  +document.getElementById("CPM_StrokeWidth-Input").value;
	baseMapSettings.legendTitle =  document.getElementById('CPM_LegendTitle-Input').value;
	baseMapSettings.breakInput =  document.getElementById("CPM_ManualBreak-Input").value; // Input for manual break.
	baseMapSettings.ifHideNull = $("#CPM_HideNull-CB").is(":checked");
	
	// Inputs for CSV data.
	baseMapSettings.CSVId =  $("#CPM_CSVPK-Select option:selected").text(); // ID for the CSV.
	baseMapSettings.geoId =  $("#CPM_BMPK-Select option:selected").text(); // ID for the base map polygons.
	baseMapSettings.value =  $("#CPM_Value-Select option:selected").text() // Input for the value field from CSV data.
}

function updatePointMapSettings(){
	pointMapSettings.id = document.getElementById("Point_ID-Select").value;
	pointMapSettings.X = document.getElementById("Point_X-Select").value;
	pointMapSettings.Y = document.getElementById("Point_Y-Select").value;
	pointMapSettings.volume = document.getElementById("Point_Volume-Select").value;
	pointMapSettings.ifMapAttribute = $("#Point_MapAttribute-CB").is(":checked");
	pointMapSettings.cfMethod = document.getElementById("Point_Classification-Select").value; // Scaling for size.
	pointMapSettings.clrScheme = document.getElementById("Point_ColorScheme-Select").value; // Node fill-color.
	pointMapSettings.minCustomColor = document.getElementById("Point_MinCustomColor-Input").value;
	pointMapSettings.maxCustomColor = document.getElementById("Point_MaxCustomColor-Input").value;
	pointMapSettings.noAttrFillColor = document.getElementById("Point_FillColor_NoAttr-Input").value;
	pointMapSettings.fillOpacity = document.getElementById("Point_FillOpacity-Input").value;
	pointMapSettings.clsNum = +document.getElementById("Point_ClassNum-Input").value;
	pointMapSettings.radiusMin = +document.getElementById("Point_Radius_Min-Input").value;
	pointMapSettings.radiusMax = +document.getElementById("Point_Radius_Max-Input").value;
	pointMapSettings.strokeColor = document.getElementById("Point_StrokeColor-Input").value;
	pointMapSettings.ifFlipColor = $("#Point_FlipLgClr-CB").is(":checked");
	pointMapSettings.strokeWidth = +document.getElementById("Point_StrokeWidth-Input").value;
	pointMapSettings.decimalPlaces = +document.getElementById('Point_LegendDP-Input').value;
	pointMapSettings.breakInput = document.getElementById("Point_ManualBreak-Input").value;
	pointMapSettings.legendTitle = document.getElementById('Point_LegendTitle-Input').value;
	pointMapSettings.isDisplayedAsAbs = $("#Point_DisplayAsAbs-CB").is(":checked"); // Display as absolute (it is temporarily hidden from the interface).
}

function updateFlowMapSettings(){
	flowMapSettings.origin = document.getElementById("Flow_SourceID-Select").value;
	flowMapSettings.destination = document.getElementById("Flow_TargetID-Select").value;
	flowMapSettings.volume = document.getElementById("Flow_Volume-Select").value;
	flowMapSettings.flowStyleName = document.getElementById("Flow_Style-Select").value; // Name of flow style.
	flowMapSettings.cfMethod = document.getElementById("Flow_Classification-Select").value;
	flowMapSettings.clrScheme = document.getElementById("Flow_ColorScheme-Select").value;
	flowMapSettings.minCustomColor = document.getElementById("Flow_MinCustomColor-Input").value;
	flowMapSettings.maxCustomColor = document.getElementById("Flow_MaxCustomColor-Input").value;
	flowMapSettings.fillOpacity = document.getElementById("Flow_FillOpacity-Input").value; 
	flowMapSettings.ifFlipColor = $("#Flow_FlipLgClr-CB").is(":checked");
	flowMapSettings.decimalPlaces = +document.getElementById('Flow_LegendDP-Input').value;
	flowMapSettings.clsNum = +document.getElementById("Flow_ClassNum-Input").value;
	flowMapSettings.numTopFlows = document.getElementById("Flow_TopFlowFromAllFlows-Input").value;
	flowMapSettings.breakInput = document.getElementById("Flow_ManualBreak-Input").value;
	flowMapSettings.widthMax = +document.getElementById("Flow_FlowWidth_Max-Input").value;
	flowMapSettings.widthMin = +document.getElementById("Flow_FlowWidth_Min-Input").value;
	flowMapSettings.strokeWidth = +document.getElementById("Flow_StrokeWidth-Input").value;
	flowMapSettings.strokeColor = document.getElementById("Flow_StrokeColor-Input").value;
	flowMapSettings.legendTitle = document.getElementById('Flow_LegendTitle-Input').value;
	flowMapSettings.isDisplayedAsAbs = $("#Flow_DisplayAsAbs-CB").is(":checked"); // Display as absolute (it is temporarily hidden from the interface).
	
	flowMapSettings.flowStyle = chooseFlowStyle();
}

function getManualBreaksArray(breakStr, min, max){
	if(!breakStr || breakStr == ""){
		popErrorWindow('Your break input can not be empty. Please make sure the break input of flow is also not empty if you are mapping flows and nodes together.');
		return null;
	}
	
	var breakArray = breakStr.split(" ");
	for(var i=0; i<breakArray.length; i++) {
		if(isNumber(breakArray[i])){
			breakArray[i] = parseFloat(breakArray[i]);
			if(i > 0){
				if(breakArray[i] <= breakArray[i - 1]){
					popErrorWindow('Break values need to be in ascending order. Please reenter the values so that each value is followed by a larger one.');
					return null;
				}
			}
		}
		else{
			popErrorWindow('Your break input can not be parsed to numbers, please make sure to use numbers ONLY and follow the format requirement in "help".');
			return null;
		}
	} 
	
	if(breakArray.length < 4){
		popErrorWindow('For manual breaks, please enter the minimum value, break values and the maximum value as a sequence of numbers separated by a space. There should be at least 4 entries including the minimum and maximum values. You may use a different classification method to identify the minimum and maximum values of the data.');
		return null;
	}else if(breakArray.length >= 13){
		popErrorWindow('For manual breaks, please enter the minimum value, break values and the maximum value as a sequence of numbers separated by a space. There should be at most 12 entries including the minimum and maximum values. You may use a different classification method to identify the minimum and maximum values of the data.');
		return null;
	}
	
	if(breakArray[0] > min){
		popErrorWindow('The min of your input should be no larger than the min of data: ' + min + ".");
		return null;
	}else if(breakArray[breakArray.length - 1] < max){
		popErrorWindow('The max of your input should be no smaller than the max of data: ' + max + ".");
		return null;
	}
	
	return breakArray;
}