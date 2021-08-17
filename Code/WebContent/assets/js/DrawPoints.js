function drawPoints(nodes){
    g2.selectAll("circle").remove();
    
    var feature = g2.selectAll("circle")
	//The way that we load features into the map
      .data(nodes)
	  .enter()
	  .append("circle");
    
	resetColorSchemeAndLegendForPoints();
    
    if(pointMapSettings.hasNewData){
    	pointMapSettings.hasNewData = false;
    	setZoomToOverlay(5, true);
    }else{
    	setZoomToOverlay(5, false);
    }
    
    resetMapOverlay();
}

function pointMouseOver(e, d){
	var selectedGeomID = pointMapSettings.id;
	var XField = pointMapSettings.X;
	var YField = pointMapSettings.Y;
	var volumeField_Points = pointMapSettings.volume;
	
	// Highlighting the point.
	d3.select(this).style("stroke-width", pointMapSettings.strokeWidth + 3)
	.style("stroke", "cyan");
	
	d3.select("#AttributeBox-Block").transition()
    .duration(200)
    .style("opacity", 1);
	
	var inFlow = inflowByNodeID[d[selectedGeomID]] ? inflowByNodeID[d[selectedGeomID]] : 0,
		outFlow = outflowByNodeID[d[selectedGeomID]] ? outflowByNodeID[d[selectedGeomID]] : 0,
		netFlow = inFlow - outFlow;
		grossFlow = inFlow + outFlow;
	d3.select("#AttributeBox-Block").html(`${selectedGeomID}: ` + d[selectedGeomID] + "</br>" 
	        + `${XField}: ` + d[XField] + "</br>" 
	        + `${YField}: ` + d[YField] + "</br>" 
	        + `${volumeField_Points}: ` + d[volumeField_Points]+ "</br>"
	        + "Gross-flow:" + grossFlow + "</br>"
	        + "In-flow:" + inFlow + "</br>"
	        + "Out-flow:" + outFlow + "</br>"
	        + "Net-flow:" + netFlow + "</br>"
	        + "Net-flow ratio:" + d3.format(".2f")(netFlow / grossFlow))
    .style("left", (d3.pointer(e)[0] + 10) + "px")
    .style("top", (d3.pointer(e)[1] - 15) + "px");
}

function pointMouseOut(d){
	// Recover the stroke.
	d3.select(this).style("stroke-width", pointMapSettings.strokeWidth)
	.style("stroke", pointMapSettings.strokeColor);
	
	// Remove the infobox in a time duration.
	d3.select("#AttributeBox-Block").transition()
    .duration(200)
    .style("opacity", 0);
}

function getPointAttrValue(point){
	if(pointMapSettings.volume === "In-flow"){
		return inflowByNodeID[point[selectedGeomID]];
	}else if(pointMapSettings.volume === "Out-flow"){
		return outflowByNodeID[point[selectedGeomID]];
	}else if(pointMapSettings.volume === "Gross-flow"){
		return inflowByNodeID[point[selectedGeomID]] + outflowByNodeID[point[selectedGeomID]];
	}else if(pointMapSettings.volume === "Net-flow"){
		return inflowByNodeID[point[selectedGeomID]] - outflowByNodeID[point[selectedGeomID]];
	}else if(pointMapSettings.volume === "Gross-flow ratio"){
		return (inflowByNodeID[point[selectedGeomID]] - outflowByNodeID[point[selectedGeomID]]) / (inflowByNodeID[point[selectedGeomID]] + outflowByNodeID[point[selectedGeomID]]);
	}else {
		return point[volumeField_Points];
	}
}

function pointClick(e, point){
	//Highlighting the flows from and to the point.
	if(g3 != null){
		g3.selectAll("path")
		.style("opacity", function(d){
			if(!this.classList.contains("source-" + point[pointMapSettings.id]) && !this.classList.contains("target-" + point[pointMapSettings.id])){
				return flowMapSettings.fillOpacity / 100 - 0.8;
			}
			else 
				return flowMapSettings.fillOpacity / 100;
		});
	}
}

function getPointRadiusRange(max, min, clsNum)
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
	var selectedGeomID = pointMapSettings.id;
	var XField = pointMapSettings.X;
	var YField = pointMapSettings.Y;
	var volumeField_Points = pointMapSettings.volume;
	var cfMethod = pointMapSettings.cfMethod;
	var clsNum = pointMapSettings.clsNum;
	var clrScheme = pointMapSettings.clrScheme;
	var radiusMin = pointMapSettings.radiusMin;
	var radiusMax = pointMapSettings.radiusMax;
	var strokeColor = pointMapSettings.strokeColor;
	var strokeWidth = pointMapSettings.strokeWidth;
	var breakInput = pointMapSettings.breakInput;
	var toFlipColor = pointMapSettings.ifFlipColor;
	var pointId = pointMapSettings.id;
	var isDisplayedAsAbs = pointMapSettings.isDisplayedAsAbs;
	var legendTitle = pointMapSettings.legendTitle;
	var decimalPlaces = pointMapSettings.decimalPlaces;
	
	var pointColor;
	// hasNull is always null currently since there is no need to display in legend.
	var hasNull = false;
	
	if(pointMapSettings.volume === "In-flow" || pointMapSettings.volume === "Out-flow" || pointMapSettings.volume === "Net-flow" || pointMapSettings.volume === "Gross-flow" || pointMapSettings.volume === "Net-flow ratio"){
		nodesizeattribute_modified = nodeFlowAttributeArr;
	}else{
		nodesizeattribute_modified = $("#Point_DisplayAsAbs-CB").is(":checked") ? nodesizeattribute.map(Math.abs) : nodesizeattribute;
	}
	
	
	var manualBreaksMinMax;
	
	// Apply a simpler style to points if no attribute is expected to be mapped.
	if(!pointMapSettings.ifMapAttribute){
		var points = g2.selectAll("circle")
		.attr("r", function(d) {
			return 10;
		})
		//The way that we load features into the map
		.attr("fill", function(d) {
			return pointMapSettings.noAttrFillColor;
		})
		.style("stroke", strokeColor)
		.style("stroke-width", strokeWidth)
		.attr("fill-opacity", pointMapSettings.fillOpacity / 100)
		.attr("id", d => "circle-"+ d[selectedGeomID])
		.attr("class", "ClickablePoints")
		.on("mouseover", pointMouseOver)
		.on("mouseout", pointMouseOut)
		.on("click", pointClick);
		removeOldLegendGraph(svg_PointLegend);
		// Make the boundary box larger to display full legend.
		adjustSVGSize(svg_PointLegend, 0, 0);
		return;
	}
	
	if(cfMethod == "Proportional"){
		pointScale = d3.scaleLinear()
		.range([radiusMin, radiusMax])
		.domain([d3.min(nodesizeattribute_modified), d3.max(nodesizeattribute_modified)]);
		pointColor = d3.scaleLinear()
		.domain([d3.min(nodesizeattribute), d3.max(nodesizeattribute)]);
		
		if(clrScheme != "Custom"){
			pointColor.range(getColorRangeOfUnclassified(toFlipColor, clrScheme, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor));
		}else{
			pointColor.range([pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor]);
		}
	}else if (cfMethod == "ManualBreak"){
		var inputArr = pointMapSettings.breakArray;
		if(!inputArr) return;
		
		var min = inputArr.shift();
		var max = inputArr.pop();
		manualBreaksMinMax = [min, max];
		
		pointColor = d3.scaleThreshold();
		pointColor.domain(inputArr);
		pointColor.range(getColorRange(toFlipColor, clrScheme, inputArr.length + 1, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor));
		
		var MBRadius = [];
		for(var i = 0; i < inputArr.length + 1; i++){
			MBRadius.push(parseFloat(radiusMin) + i * (radiusMax - radiusMin) * 1.0 / inputArr.length);
		}
		
		pointScale = d3.scaleThreshold().range(MBRadius)
		.domain(inputArr);
	}else if(cfMethod == "Quantile"){
		pointColor = d3.scaleQuantile()
					.range(getColorRange(toFlipColor, clrScheme, clsNum, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor))
					.domain(nodesizeattribute);
		
		pointScale = d3.scaleQuantile()
					.range(getPointRadiusRange(radiusMax, radiusMin, clsNum))
					.domain(nodesizeattribute_modified);
	}else if(cfMethod == "EqualInterval"){
		pointColor = d3.scaleQuantize()
					.range(getColorRange(toFlipColor, clrScheme, clsNum, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor))
					.domain(d3.extent(nodesizeattribute));
		
		pointScale = d3.scaleQuantize()
					.range(getPointRadiusRange(radiusMax, radiusMin, clsNum))
					.domain(d3.extent(nodesizeattribute_modified));
	}else if(cfMethod == "NaturalBreak"){
		pointColor =  d3.scaleThreshold();
		var naturalBreaksForColors = ss.ckmeans(nodesizeattribute, clsNum).map(v => v.pop());
		pointColor.range(getColorRange(toFlipColor, clrScheme, clsNum, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor))
		pointColor.domain(naturalBreaksForColors);
		
		var naturalBreaksForWidth = ss.ckmeans(nodesizeattribute_modified, clsNum).map(v => v.pop());
		flowWidthScale = d3.scaleThreshold()
						.range(getPointRadiusRange(radiusMax, radiusMin, clsNum))
						.domain(nodesizeattribute_modified);
	}
	
	// Set back the flow opacity
	svg_user_painting.on('click', function(e, elemt) {
		  // do nothing if a clickable circle is clicked
		  if (d3.select(e.target).classed('ClickablePoints')) {
		    return;
		  } 
		  else {
			//Highlighting the flows from and to the point.
			if(g3){
				g3.selectAll("path")
			    .style("opacity", 1);
			}
		  }
		});
	
	if(isDisplayedAsAbs){
		pointColor = d3.scaleThreshold();
		pointColor.range(getColorRangeOfUnclassified(toFlipColor, clrScheme, pointMapSettings.minCustomColor, pointMapSettings.maxCustomColor))
		.domain([0]);
	}
	
	var points = g2.selectAll("circle")
	.attr("r", function(d) {
		if($("#Point_DisplayAsAbs-CB").is(":checked")){
			return pointScale(Math.abs(getPointAttrValue(d)));
		}else{
//			hasNull = true;
			return pointScale(getPointAttrValue(d));
		}
	})
	//The way that we load features into the map
	.attr("fill", function(d) {
		// Display "grey" for null values
		if(getPointAttrValue(d))
			return pointColor(getPointAttrValue(d));
		else
			return "#d0c8c8";
	})
	.style("stroke", strokeColor)
	.style("stroke-width", strokeWidth)
	.attr("fill-opacity", pointMapSettings.fillOpacity / 100)
	.attr("id", d => "circle-"+ d[selectedGeomID])
	.attr("class", "ClickablePoints")
	.on("mouseover", pointMouseOver)
	.on("mouseout",pointMouseOut)
	.on("click", pointClick);
	
	//Change the size of point may also influence flows. Refresh the location of flows here as well.
	map.render();
	
	if(cfMethod == "Proportional"){
		addUnclassifiedPointLegend(svg_PointLegend, pointSVGId, legendTitle, pointScale, pointColor, strokeColor, strokeWidth, isDisplayedAsAbs, hasNull, decimalPlaces);
	}
	else{
		addClassifiedPointLegend(svg_PointLegend, pointSVGId, legendTitle, pointScale, pointColor, strokeColor, strokeWidth, manualBreaksMinMax, hasNull, decimalPlaces);
	}
}