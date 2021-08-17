function drawChoroplethMapPolygons(world){
    g1.selectAll("path").remove();
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
        .on("mouseover", function(){
			d3.select(this).attr("stroke-width", baseMapSettings.strokeWidth + 3)
			.attr("stroke", "cyan");
		}) 
		.on("mouseout", function(){
			d3.select(this).attr("stroke-width", baseMapSettings.strokeWidth)
			.attr("stroke", "black");
		});
    
    if(baseMapSettings.hasNewData){
    	setZoomToOverlay(0, true);
    	baseMapSettings.hasNewData = false;
    }
    else{
    	setZoomToOverlay(5, false);
    }
    
    resetMapOverlay();
}

function resetColorSchemeAndLegendForChoroplethMap(){
	var cfMethod = baseMapSettings.cfMethod;
	var clrScheme = baseMapSettings.clrScheme;
	var clsNum = baseMapSettings.clsNum;
	var opacity = baseMapSettings.fillOpacity * 1.0 / 100;
	var strokeColor = baseMapSettings.strokeColor;
	var strokeWidth = baseMapSettings.strokeWidth;
	var breakInput = baseMapSettings.breakInput;
	var toFlipColor = baseMapSettings.ifFlipColor;
	var decimalPlaces = baseMapSettings.decimalPlaces;
	var legendTitle = baseMapSettings.legendTitle;
	var CPMField = baseMapSettings.value;
	var selectedGeomID = baseMapSettings.geoId;
	
	var textBox = d3.select("#AttributeBox-Block");
	baseMapSettings.numFeatures = 0;
	baseMapSettings.numJoint = 0;
	baseMapSettings.numDisjoint = 0;
	var hasNull = false;
	var CPM_Color;
	var manualBreaksMinMax = [];

	if(cfMethod == "Quantile"){
		CPM_Color = d3.scaleQuantile()
		.domain(CPMValue)
		.range(getColorRange(toFlipColor, clrScheme, clsNum));
	}else if(cfMethod == "EqualInterval"){
		CPM_Color = d3.scaleQuantize()
		.range(getColorRange(toFlipColor, clrScheme, clsNum))
		.domain(d3.extent(CPMValue));
	}else if(cfMethod == "NaturalBreak"){
		CPM_Color =  d3.scaleThreshold();
		var naturalBreaks = ss.ckmeans(CPMValue, clsNum).map(v => v.pop());
		CPM_Color.domain(naturalBreaks);
		CPM_Color.range(getColorRange(toFlipColor, clrScheme, clsNum));
	}else if(cfMethod == "Linear"){
		CPM_Color = d3.scaleLinear()
		.domain([d3.min(CPMValue), d3.max(CPMValue)]);
		
		if(clrScheme != "Custom"){
			CPM_Color.range(getColorRangeOfUnclassified(toFlipColor, clrScheme));
		}else{
			CPM_Color.range([document.getElementById("CPM_MinCustomColor-Input").value, document.getElementById("CPM_MaxCustomColor-Input").value]);
		}
		
		var selectedGeomID = $("#CPM_BMPK-Select option:selected").text();
		g1.selectAll("path")
		//The way that we load features into the map
		.attr("fill", function(d) { 
			baseMapSettings.numFeatures += 1;
			if(CPMIdValueMap.get((d.properties[selectedGeomID]).toString())){
				baseMapSettings.numJoint += 1;
				return CPM_Color(CPMIdValueMap.get((d.properties[selectedGeomID]).toString()));
			}
			else{
				baseMapSettings.numDisjoint += 1;
				hasNull = true;
				return "#d0c8c8";
			}
		})
		.attr("stroke", strokeColor)
		.attr("stroke-width", strokeWidth)
		.attr("fill-opacity", opacity);
		
		addUnclassifiedChoroplethMapLegend(svg_CPMLegend, CPMSVGId, legendTitle, CPM_Color, strokeColor, strokeWidth, decimalPlaces);
		return;
	}else if(cfMethod == "ManualBreak"){
		var inputArr = baseMapSettings.breakArray;
		if(!inputArr) return;
		
		var min = inputArr.shift();
		var max = inputArr.pop();
		manualBreaksMinMax = [min, max];
		
		CPM_Color = d3.scaleThreshold();
		CPM_Color.domain(inputArr);
		CPM_Color.range(getColorRange(toFlipColor, clrScheme, inputArr.length + 1, baseMapSettings.minCustomColor, baseMapSettings.maxCustomColor));
	}
	
	g1.attr("class", clrScheme);
	var polygonPath = g1.selectAll("path")
	//The way that we load features into the map
	.attr("fill", function(d) {
		baseMapSettings.numFeatures += 1;
		if(CPMIdValueMap.get((d.properties[selectedGeomID]).toString())){
			baseMapSettings.numJoint += 1;
			return CPM_Color(CPMIdValueMap.get((d.properties[selectedGeomID]).toString()));
		}
		else{
			baseMapSettings.numDisjoint += 1;
			hasNull = true;
			return "#d0c8c8";
		}
	})
	.attr("display", "")
	.attr("stroke", strokeColor)
	.attr("stroke-width", strokeWidth)
	.attr("fill-opacity", opacity)
	.on("mouseover", function(e, d){
		d3.select(this).attr("stroke-width", strokeWidth + 3)
		.attr("stroke", "cyan");
		
		textBox.transition()
        .duration(200)
        .style("opacity", 1);
		textBox.html(`${selectedGeomID}: ` + d.properties[selectedGeomID] + "</br>" + `${CPMField}: ` +CPMIdValueMap.get((d.properties[selectedGeomID].toString())))
        .style("left", (d3.pointer(e)[0] + 10) + "px")
        .style("top", (d3.pointer(e)[1] - 15) + "px");
	})
	.on("click", function(d){

	})
	.on("mouseout", function(){
		d3.select(this).attr("stroke-width", strokeWidth)
		.attr("stroke", strokeColor);
		
		textBox.transition()
        .duration(200)
        .style("opacity", 0);
	});
	
	// Hide the null values:
	if(baseMapSettings.ifHideNull){
		// Not to show the null in legend.
		hasNull = false;
		
		// Not to display the null polygons:
		polygonPath.attr("display", function(d){
			if(CPMIdValueMap.get((d.properties[selectedGeomID]).toString())){
				return;
			}else{
				return "none";
			}
		})
	}
	
	addClassifiedChoroplethMapLegend(svg_CPMLegend, CPMSVGId, legendTitle, CPM_Color, strokeColor, strokeWidth, hasNull, manualBreaksMinMax, decimalPlaces);
}
