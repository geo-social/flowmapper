//Assign the function of drawing flows.
function chooseFlowStyle() {
	switch(flowMapSettings.flowStyleName){
		case "curve":{
			return pathstyle_curve;
		};
		case "strtHfArw" :{
			return pathstyle_straightwitharrow;
		};
		case "tapered" :{
			return pathstyle_tapered;
		};
		case "tearDrop" :{
			return pathstyle_tearDrop;
		};
		default:{
			console.log("Undefined flow style.");
		}
	}
}

function drawFlows(flowData, nodes, IDField){
    var overlay = map.getOverlayById("UserOverlay");
    g3.selectAll("path").remove();
  //Define the style of arrow (for some flow styles).
	var defs = svg_user_painting.append("defs");

//    var pathOnOBM = d3.geoPath().projection(projectToOnlineBaseMapTransform(map));
    
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
//	feature.append("title")
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
    
    if(flowMapSettings.hasNewData){
    	setZoomToOverlay(5, true);
    	flowMapSettings.hasNewData = false;
    }else{
    	setZoomToOverlay(5, false);
    }
    
    resetMapOverlay();
}

//TODO: Move the codes to a new JS file: DrawFlows.js.
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
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		var originRadius, desRedius;
		if(pointMapSettings.ifMapAttribute){
			originRadius = pointScale(volumeByNodeID[d.source]) + +pointMapSettings.strokeWidth;
			desRedius = pointScale(volumeByNodeID[d.target]) + +pointMapSettings.strokeWidth;
		}else{
			originRadius = 10 + +pointMapSettings.strokeWidth;
			desRedius = 10 + +pointMapSettings.strokeWidth;
		}
		
		return drawStraightWithArrow(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowWidthScale(d.volume), originRadius, desRedius);
	}
}

function pathstyle_curve(d){
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		var originRadius, desRedius;
		if(pointMapSettings.ifMapAttribute){
			originRadius = pointScale(+volumeByNodeID[d.source]) + +pointMapSettings.strokeWidth;
			desRedius = pointScale(+volumeByNodeID[d.target]) + +pointMapSettings.strokeWidth;
		}else{
			originRadius = 10 + +pointMapSettings.strokeWidth;
			desRedius = 10 + +pointMapSettings.strokeWidth;
		}
		
		var flowVolume = $("#Flow_DisplayAsAbs-CB").is(":checked") ? flowWidthScale(Math.abs(d.volume)) : flowWidthScale(d.volume);
		return drawCurve(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowVolume, originRadius, desRedius);
	}
}

function pathstyle_tapered(d){
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		var originRadius, desRedius;
		if(pointMapSettings.ifMapAttribute){
			originRadius = pointScale(+volumeByNodeID[d.source]) + +pointMapSettings.strokeWidth;
			desRedius = pointScale(+volumeByNodeID[d.target]) + +pointMapSettings.strokeWidth;
		}else{
			originRadius = 10 + +pointMapSettings.strokeWidth;
			desRedius = 10 + +pointMapSettings.strokeWidth;
		}
		
		var flowVolume = $("#Flow_DisplayAsAbs-CB").is(":checked") ? flowWidthScale(Math.abs(d.volume)) : flowWidthScale(d.volume);
		return drawTapered(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowVolume, originRadius, desRedius);
	}
}

function pathstyle_tearDrop(d){
	if(locationByNodeID[d.source] && locationByNodeID[d.target] && d.volume > flowthreshold){
		var originRadius, desRedius;
		if(pointMapSettings.ifMapAttribute){
			originRadius = pointScale(+volumeByNodeID[d.source]) + +pointMapSettings.strokeWidth;
			desRedius = pointScale(+volumeByNodeID[d.target]) + +pointMapSettings.strokeWidth;
		}else{
			originRadius = 10 + +pointMapSettings.strokeWidth;
			desRedius = 10 + +pointMapSettings.strokeWidth;
		}
		
		var flowVolume = $("#Flow_DisplayAsAbs-CB").is(":checked") ? flowWidthScale(Math.abs(d.volume)) : flowWidthScale(d.volume);
		return drawTearDrop(projectToOnlineBaseMap(locationByNodeID[d.source])[0], projectToOnlineBaseMap(locationByNodeID[d.source])[1],
				projectToOnlineBaseMap(locationByNodeID[d.target])[0], projectToOnlineBaseMap(locationByNodeID[d.target])[1],
				flowVolume, originRadius, desRedius);
	}
}

// sourceSize and target size means the radius + stroke width of the node.
function drawStraightWithArrow(x1, y1, x2, y2, flowSize, sourceSize, targetSize){
	var ndsize0 = sourceSize;
	var ndsize3 = targetSize;
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

	// Add points for flowfigures.html
	if(typeof controlPoints !== 'undefined'  && typeof regularPoints !== 'undefined' && typeof elbowPoints !== 'undefined' ){
//		regularPoints.push([x1, y1]);
//		regularPoints.push([x2, y2]);
//		controlPoints.push([xc1, yc1]);
//		controlPoints.push([xc2, yc2]);
//		elbowPoints.push([x2elbow1, y2elbow1]);
		
		regularPoints.push({name: "P0", coordinates: [x1, y1]});
		regularPoints.push({name: "P2", coordinates: [x2, y2]});
		controlPoints.push({name: "CP1", coordinates: [xc1, yc1]});
		controlPoints.push({name: "CP2", coordinates: [xc2, yc2]});
		elbowPoints.push({name: "EP", coordinates: [x2elbow1, y2elbow1]});
	}
	
	
	return "M" + x1 + "," + y1 + "L" + xc1 + "," + yc1 + "L" + xc2 + "," + yc2
			+ "L" + x2elbow1 + "," + y2elbow1 + "L" + x2 + "," + y2 + "Z";
}

function drawCurve(x0, y0, x3, y3, flowSize, sourceRadius, targetRadius, isDrawingLegend){
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
	
	var ndsize0 = sourceRadius;
	var ndsize3 = targetRadius;
	var dx = Math.abs(x3 - x0);
	var dy = Math.abs(y3 - y0);
	
	// no line is drawn if the circle to circle distance is too small
	var len = Math.sqrt(dx * dx + dy * dy);
	if (len < (ndsize0 + ndsize3) * 1.2)
		return;
	
	var noarrow = false;
	if (len < (ndsize0 + ndsize3) * 1.6 && (!isDrawingLegend || isDrawingLegend == false))
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

	if (!noarrow){
		// Add points for flowfigures.html
		if(typeof controlPoints !== 'undefined'  && typeof regularPoints !== 'undefined' && typeof elbowPoints !== 'undefined' ){
//			regularPoints.push([x0, y0]);
//			regularPoints.push([x3, y3]);
//			controlPoints.push([xc1, yc1]);
//			controlPoints.push([xc13rd, yc13rd]);
//			controlPoints.push([xc23rd, yc23rd]);
//			controlPoints.push([xc2, yc2]);
//			elbowPoints.push([x3elbow1, y3elbow1]);
//			controlPoints.push([x23rd, y23rd]);
//			controlPoints.push([x13rd, y13rd]);
			
			regularPoints.push({name: "P0", coordinates: [x0, y0]});
			regularPoints.push({name: "P3", coordinates: [x3, y3]});
			controlPoints.push({name: "P1", coordinates: [xc1, yc1]});
			controlPoints.push({name: "CP1_C1", coordinates: [xc13rd, yc13rd], color: "red"});
			controlPoints.push({name: "CP2_C1", coordinates: [xc23rd, yc23rd], color: "red"});
			controlPoints.push({name: "P2", coordinates: [xc2, yc2]});
			elbowPoints.push({name: "EP3", coordinates: [x3elbow1, y3elbow1]});
			controlPoints.push({name: "CP1_C2", coordinates: [x23rd, y23rd], color: "blue"});
			controlPoints.push({name: "CP2_C2", coordinates: [x13rd, y13rd], color: "blue"});
		}
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3elbow1 + "," + y3elbow1 
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
	}
	else{
		// Add points for flowfigures.html
		if(typeof controlPoints !== 'undefined'  && typeof regularPoints !== 'undefined' && typeof elbowPoints !== 'undefined' ){
//			regularPoints.push([x0, y0]);
//			regularPoints.push([x3, y3]);
//			controlPoints.push([xc1, yc1]);
//			controlPoints.push([xc13rd, yc13rd]);
//			controlPoints.push([xc23rd, yc23rd]);
//			controlPoints.push([xc2, yc2]);
//			controlPoints.push([x23rd, y23rd]);
//			controlPoints.push([x13rd, y13rd]);
			
			regularPoints.push({name: "P0", coordinates: [x0, y0]});
			regularPoints.push({name: "P3", coordinates: [x3, y3]});
			controlPoints.push({name: "P1", coordinates: [xc1, yc1]});
			controlPoints.push({name: "CP1_C1", coordinates: [xc13rd, yc13rd], color: "red"});
			controlPoints.push({name: "CP2_C1", coordinates: [xc23rd, yc23rd], color: "red"});
			controlPoints.push({name: "P2", coordinates: [xc2, yc2]});
			controlPoints.push({name: "CP1_C2", coordinates: [x23rd, y23rd], color: "blue"});
			controlPoints.push({name: "CP2_C2", coordinates: [x13rd, y13rd], color: "blue"});
		}
		
		return "M" + x0 + "," + y0 
		+ " L" + xc1 + "," + yc1 
		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
		+ " L" + x3 + "," + y3 
		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
	}
}

function drawCurveOriginal(x0, y0, x3, y3, flowSize, sourceSize, targetSize, isDrawingLegend){
	var ndsize0 = pointScale(parseFloat(sourceSize));
	var ndsize3 = pointScale(parseFloat(targetSize));
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

function drawTapered(x0, y0, x3, y3, flowSize, sourceRadius, targetRadius){
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
	
	var ndsize0 = sourceRadius;
	var ndsize3 = targetRadius;
	var dx = Math.abs(x3 - x0);
	var dy = Math.abs(y3 - y0);
	
	var len = Math.sqrt(dx * dx + dy * dy);
	if (len < (ndsize0 + ndsize3) * 1.2)
		return;
	
	var noarrow = false;
	if (len < (ndsize0 + ndsize3) * 2.5)
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

//	if (!noarrow)
//		return "M" + x0 + "," + y0 
//		+ " L" + xc1 + "," + yc1 
//		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
//		+ " L" + x3elbow1 + "," + y3elbow1 
//		+ " L" + x3 + "," + y3 
//		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
//	else
	
	// Add points for flowfigures.html
	if(typeof controlPoints !== 'undefined'  && typeof regularPoints !== 'undefined' && typeof elbowPoints !== 'undefined' ){
		regularPoints.push({name: "P0", coordinates: [x0, y0]});
		regularPoints.push({name: "P3", coordinates: [x3, y3]});
		controlPoints.push({name: "P1", coordinates: [xc1, yc1]});
		controlPoints.push({name: "CP1_C1", coordinates: [xc13rd, yc13rd]});
		controlPoints.push({name: "CP2_C1", coordinates: [xc23rd, yc23rd]});
//		controlPoints.push({name: "xc2,yc2", coordinates: [xc2, yc2]});
		controlPoints.push({name: "CP1_C2", coordinates: [x23rd, y23rd]});
		controlPoints.push({name: "CP2_C2", coordinates: [x13rd, y13rd]});
	}
	
	return "M" + x0 + "," + y0 
	+ " L" + xc1 + "," + yc1 
	+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + x3 + "," + y3
//	+ " " + xc2 + "," + yc2
	+ " L" + x3 + "," + y3 
	+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
}

function drawTearDrop(x0, y0, x3, y3, flowSize, sourceRadius, targetRadius){
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
	
	var ndsize0 = sourceRadius;
	var ndsize3 = targetRadius;
	var dx = Math.abs(x3 - x0);
	var dy = Math.abs(y3 - y0);
	
	var len = Math.sqrt(dx * dx + dy * dy);
	if (len < (ndsize0 + ndsize3) * 1.2)
		return;
	
	var noarrow = false;
	if (len < (ndsize0 + ndsize3) * 2.5)
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
		xc1 = (y0 > y3) ? x3 + xdelta / 2 : x3 - xdelta / 2;
		yc1 = (x0 > x3) ? y3 - ydelta / 2 : y3 + ydelta / 2;

		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var x13rd = (y0 > y3) ? x3 + (x0 - x3) / 3 + arcxdelta : x3 + (x0 - x3) / 3 - arcxdelta;
		var y13rd = (x0 > x3) ? y3 + (y0 - y3) / 3 - arcydelta : y3 + (y0 - y3) / 3 + arcydelta;
		var x23rd = (y0 > y3) ? x3 + arcxdelta : x3 - arcxdelta;
		var y23rd = (x0 > x3) ? y3 - arcydelta : y3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var xc13rd = (y0 > y3) ? x3 + (x0 - x3) / 3 + arcxdelta : x3 + (x0 - x3) / 3 - arcxdelta;
		var yc13rd = (x0 > x3) ? y3 + (y0 - y3) / 3 - arcydelta : y3 + (y0 - y3) / 3 + arcydelta;
		var xc23rd = (y0 > y3) ? x3 + arcxdelta : x3 - arcxdelta;
		var yc23rd = (x0 > x3) ? y3 - arcydelta : y3 + arcydelta;
	}else
	{
		xc1 = (y0 < y3) ? x3 + xdelta / 2 : x3 - xdelta / 2;
		yc1 = (x0 < x3) ? y3 - ydelta / 2 : y3 + ydelta / 2;

		var arcxdelta = xdelta * len / 4 / flowSize;
		var arcydelta = ydelta * len / 4 / flowSize;
		var xc13rd = (y0 < y3) ? x3 + (x0 - x3) / 3 + arcxdelta : x3 + (x0 - x3) / 3 - arcxdelta;
		var yc13rd = (x0 < x3) ? y3 + (y0 - y3) / 3 - arcydelta : y3 + (y0 - y3) / 3 + arcydelta;
		var xc23rd = (y0 < y3) ? x3 + arcxdelta : x3 - arcxdelta;
		var yc23rd = (x0 < x3) ? y3 - arcydelta : y3 + arcydelta;
		arcxdelta = arcxdelta + xdelta;
		arcydelta = arcydelta + ydelta;
		var x13rd = (x0 < x3) ? y3 + (y0 - y3) / 3 - arcydelta : y3 + (y0 - y3) / 3 + arcydelta;
		var y13rd = (x0 < x3) ? y0 + (y0 - y3) / 3 - arcydelta : y3 + (y0 - y3) / 3 + arcydelta;
		var x23rd = (y0 < y3) ? x3 + arcxdelta : x3 - arcxdelta;
		var y23rd = (x0 < x3) ? y3 - arcydelta : y3 + arcydelta;
	}

//	if (!noarrow)
//		return "M" + x0 + "," + y0 
//		+ " L" + xc1 + "," + yc1 
//		+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + xc2 + "," + yc2
//		+ " L" + x3elbow1 + "," + y3elbow1 
//		+ " L" + x3 + "," + y3 
//		+ " C" + x23rd + "," + y23rd + " " + x13rd + "," + y13rd + " " + x0 + "," + y0;
//	else
	
	// Add points for flowfigures.html
	if(typeof controlPoints !== 'undefined'  && typeof regularPoints !== 'undefined' && typeof elbowPoints !== 'undefined' ){
		regularPoints.push({name: "P0", coordinates: [x0, y0]});
		regularPoints.push({name: "P3", coordinates: [x3, y3]});
//		controlPoints.push({name: "xc1,yc1", coordinates: [xc1, yc1]});
		controlPoints.push({name: "CP1_C1", coordinates: [xc13rd, yc13rd]});
		controlPoints.push({name: "CP2_C1", coordinates: [xc23rd, yc23rd]});
//		controlPoints.push({name: "xc2,yc2", coordinates: [xc2, yc2]});
		controlPoints.push({name: "CP1_C2", coordinates: [x23rd, y23rd]});
		controlPoints.push({name: "CP2_C2", coordinates: [x13rd, y13rd]});
	}
	
	return "M" + x0 + "," + y0 
	+ " C" + xc13rd + ","+ yc13rd + " " + xc23rd + "," + yc23rd + " " + x3 + "," + y3
//	+ " " + xc2 + "," + yc2
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

function resetColorSchemeAndLegendForFlows(){
	var selectedOriginID = flowMapSettings.origin;
	var selectedTargetID = flowMapSettings.destination;
	var flowVolumeField =  flowMapSettings.volume;
	var cfMethod = flowMapSettings.cfMethod;
	var clrScheme = flowMapSettings.clrScheme;
	var clsNum = flowMapSettings.clsNum;
	var flowStyle = flowMapSettings.flowStyleName;
	var showTopFlowsNumFromAll = flowMapSettings.numTopFlows;
	var toFlipColor = flowMapSettings.ifFlipColor;
	var widthMax = flowMapSettings.widthMax;
	var widthMin = flowMapSettings.widthMin;
	var flowStrokeWidth = flowMapSettings.strokeWidth;
	var flowStrokeColor = flowMapSettings.strokeColor;
	var legendTitle = flowMapSettings.legendTitle;
	var decimalPlaces = flowMapSettings.decimalPlaces;
	var isDisplayedAsAbs = flowMapSettings.isDisplayedAsAbs;
	var manualBreaksMinMax;
	
	var isColorless = $("#Flow_ColorScheme-Select").val() == "Black" ? true: false;
	
	//var showTopFromNodeNum = document.getElementById("Flow_TopFlowFromNodeNum-Input").value;
	var textBox = d3.select("#AttributeBox-Block");
	var FM_Color;
	topVolumeList_modified = isDisplayedAsAbs ?  topVolumeList.map(Math.abs) : topVolumeList;
	// Selected top flows:
	var topFlows = topVolumeList.slice(0, showTopFlowsNumFromAll);
	var topFlows_modified = topVolumeList_modified.slice(0, showTopFlowsNumFromAll);
	
	if(cfMethod == "Quantile"){
		FM_Color = d3.scaleQuantile();
		FM_Color.range(getColorRange(toFlipColor, clrScheme, clsNum))
		FM_Color.domain(topFlows);
		
		flowWidthScale = d3.scaleQuantile();
		flowWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowWidthScale.domain(topFlows_modified);
	}else if(cfMethod == "EqualInterval"){
		FM_Color = d3.scaleQuantize();
		FM_Color.range(getColorRange(toFlipColor, clrScheme, clsNum));
		FM_Color.domain(d3.extent(topFlows));
		flowWidthScale = d3.scaleQuantize();
		flowWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowWidthScale.domain(d3.extent(topFlows_modified));
	}else if(cfMethod == "NaturalBreak"){
		FM_Color =  d3.scaleThreshold();
		var naturalBreaksForColors = ss.ckmeans(topFlows, clsNum).map(v => v.pop());
		FM_Color.range(getColorRange(toFlipColor, clrScheme, clsNum))
		FM_Color.domain(naturalBreaksForColors);
		
		var naturalBreaksForWidth = ss.ckmeans(topFlows_modified, clsNum).map(v => v.pop());
		flowWidthScale = d3.scaleThreshold();
		flowWidthScale.range(getFlowWidthRange(widthMax, widthMin, clsNum))
		flowWidthScale.domain(naturalBreaksForWidth);
	}else if(cfMethod == "ManualBreak"){
		var inputArr = flowMapSettings.breakArray;
		if(!inputArr) return;
		
		var min = inputArr.shift();
		var max = inputArr.pop();
		manualBreaksMinMax = [min, max];
		
		FM_Color = d3.scaleThreshold();
		FM_Color.domain(inputArr);
		FM_Color.range(getColorRange(toFlipColor, clrScheme, inputArr.length + 1, flowMapSettings.minCustomColor, flowMapSettings.maxCustomColor));
		
		flowWidthScale = d3.scaleThreshold();
		flowWidthScale.range(getFlowWidthRange(widthMax, widthMin, inputArr.length + 1))
		flowWidthScale.domain(inputArr);
	}else if(cfMethod == "Proportional"){
		FM_Color = d3.scaleLinear()
		.domain([d3.min(topFlows_modified), d3.max(topFlows_modified)]);
		
		if(clrScheme != "Custom"){
			FM_Color.range(getColorRangeOfUnclassified(toFlipColor, clrScheme));
		}else{
			FM_Color.range([document.getElementById("Flow_MinCustomColor-Input").value, document.getElementById("Flow_MaxCustomColor-Input").value]);
		}
		
		flowWidthScale = d3.scaleLinear().range([widthMin, widthMax])
		.domain([d3.min(topFlows_modified), d3.max(topFlows_modified)]);
	}

	
	if($("#Flow_DisplayAsAbs-CB").is(":checked")){
		FM_Color = d3.scaleThreshold();
		FM_Color.range(getColorRangeOfUnclassified(toFlipColor, clrScheme))
		.domain([0]);
	}
	
	var threshold;
	if(showTopFlowsNumFromAll - 1 < 0) threshold = Number.POSITIVE_INFINITY;
	else threshold = topVolumeList_modified[showTopFlowsNumFromAll - 1];
	
	g3.attr("class", clrScheme);
	//g3.selectAll("g").selectAll("path")
	var points = g2.selectAll("circle")
					.attr("display", "none");
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
	.attr("d", flowMapSettings.flowStyle)
	//show flows within top number
	.style("display", function(d) {
		var inputVolume = isDisplayedAsAbs ? Math.abs(d.volume) : d.volume;
		if(inputVolume >= threshold) {
			d3.select("#circle-" + d.source)
			.attr("display", "block")
			d3.select("#circle-" + d.target)
			.attr("display", "block")
			return "block"; 
		}
		else
			return "none";
	})
	.attr("stroke-width", flowStrokeWidth)
	.attr("stroke", flowStrokeColor)
	.style("fill-opacity", flowMapSettings.fillOpacity / 100)
	.attr("class", d => "source-" + d.source + " " + "target-" + d.target)
	.on("mouseover", function(e, d){
		d3.select(this).attr("stroke-width", flowStrokeWidth + 3)
		.attr("stroke", "cyan");
		
		textBox.transition()
        .duration(200)
        .style("opacity", 1);
		
		textBox.html(`${selectedOriginID}: ` + d["source"] + "</br>" 
		        + `${selectedTargetID}: ` + d["target"] + "</br>" 
		        + `${flowVolumeField}: ` + d["volume"])
        .style("left", (d3.pointer(e)[0] + 10) + "px")
        .style("top", (d3.pointer(e)[1] - 15) + "px");
	})
	.on("mouseout", function(){
		d3.select(this).attr("stroke-width", flowStrokeWidth)
		.attr("stroke", flowStrokeColor);
		
		textBox.transition()
        .duration(200)
        .style("opacity", 0);
	})
	.on("click", function(d){
		
	});
	
	
    //add legend for flows.
	if(cfMethod != "Proportional")
		addClassifiedFlowLegend(svg_FlowLegend, flowSVGId, legendTitle, FM_Color, flowStrokeColor, flowStrokeWidth, cfMethod, flowStyle, isColorless, decimalPlaces, manualBreaksMinMax);
	else
		addUnclassifiedFlowLegend(svg_FlowLegend, flowSVGId, legendTitle, FM_Color, flowStrokeColor, flowStrokeWidth, cfMethod, flowStyle, isDisplayedAsAbs, decimalPlaces, topFlows_modified);
}