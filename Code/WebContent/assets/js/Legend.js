const legendSymbol = {
		rectangle: 0,
		circle: 1,
		curveFlow: 2,
		straight: 3
};

function removeOldLegendGraph(legendSVG){
	// Remove the old legend.
	if(legendSVG){
		legendSVG.selectAll("g").remove();
		adjustSVGSize(legendSVG, 0 ,0);
	}
}

function adjustSVGSize(svg, svgWidth, svgHeight){
	svg.attr("width", svgWidth)
		.attr("height", svgHeight);
}

function addNullLegendCell(svgId, legendCellsGraph,symbolShape, fillColor, text){
	var cellCollection = legendCellsGraph.selectAll("g");
	var cellCount = cellCollection.size();
	var rowHeight = cellCollection.nodes()[1].transform.baseVal[0].matrix["f"];
	var textTransform = window
	  .getComputedStyle(document.querySelector('#' + svgId + ' text'))
	  .getPropertyValue('transform');
	var transformMatrix = new WebKitCSSMatrix(textTransform);
	
	cell = legendCellsGraph.append("g")
	.attr("class", "cell")
	.attr("transform", "translate(0, " + (cellCount * rowHeight) + ")")
	
	var symbol;
	
	switch(symbolShape){
		case legendSymbol.rectangle:{
			symbol = cell.append("rect")
			.style("fill", fillColor)
			.attr("width", 15)
			.attr("height", 15)
			.attr("class", "swatch");
			break;
		};
		case legendSymbol.circle:{
			symbol = cell.append("circle")
			.attr("class", "swatch")
			.attr("r", pointMapSettings.radiusMin)
			.attr("fill", fillColor)
			.style("stroke", pointMapSettings.strokeColor)
			.style("stroke-width", pointMapSettings.strokeWidth);
			break;
		};
		case legendSymbol.curveFlow:
		case legendSymbol.straight:{
			symbol = "path";
			break;
		};
		default:{
			alert("Can not add null value legend for this symbology.");
			break;
		}
	}
	
	if(!symbol){
		return;
	}
	
	var legendText = cell.append("text")
	.attr("class", "label")
	.attr("transform", "translate(" + transformMatrix.e +", " + transformMatrix.f +")")
	.text(text);
}