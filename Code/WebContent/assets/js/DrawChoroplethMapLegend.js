function addClassifiedChoroplethMapLegend(legendSVG, SVG_id, legendTitle, colorScheme, strokeColor, strokeWidth, hasNull, manualBreaksMinMax, decimalPlaces){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG.append("g")
	  .attr("class", "classifiedCPMLegendQuant")
	  .attr("id", "g_CPMLegend")
	  .attr("transform", "translate(20, 30)")
	 
//	  .attr("width", 300)
//	  .attr("height", 150);
	var shapeWidth = 15, shapeHeight = 15, shapePadding = 2;
	  
	var legend = d3.legendColor()
	  .labelFormat(d3.format(",." + decimalPlaces + "f"))
	  .title(legendTitle)
	  .titleWidth(baseMapSettings.titleWidth)
	  .scale(colorScheme)
	  .shapeWidth(shapeWidth)
	  .shapeHeight(shapeHeight)
	  .shapePadding(shapePadding)
	  .useClass(false);

	// Make special legend text for manual break and natural break. 
	if(baseMapSettings.cfMethod == "NaturalBreak"){
		legend.labels(function({
		  i,
		  genLength,
		  generatedLabels,
		  labelDelimiter
		}) {
		  if (i === 0) {
		    const values = generatedLabels[i].split(` ${labelDelimiter} `);
		    return `${d3.format(",." + decimalPlaces + "f")(d3.min(CPMValue))} to ${values[1]}`
		  } else if (i === genLength - 1) {
		    const values = generatedLabels[i].split(` ${labelDelimiter} `)
		    return `${values[0]} to ${d3.format(",." + decimalPlaces + "f")(d3.max(CPMValue))}`
		  }
		  return generatedLabels[i]
		});
	}else if(baseMapSettings.cfMethod == "ManualBreak"){
			legend.labels(function({
			  i,
			  genLength,
			  generatedLabels,
			  labelDelimiter
			}) {
			  if (i === 0) {
			    const values = generatedLabels[i].split(` ${labelDelimiter} `);
			    return `${d3.format(",." + decimalPlaces + "f")(manualBreaksMinMax[0])} to ${values[1]}`
			  } else if (i === genLength - 1) {
			    const values = generatedLabels[i].split(` ${labelDelimiter} `)
			    return `${values[0]} to ${d3.format(",." + decimalPlaces + "f")(manualBreaksMinMax[1])}`
			  }
			  return generatedLabels[i]
			});
		}
	
	// Call the legend
	legendSVG.select(".classifiedCPMLegendQuant")
	  .call(legend);
	
	// Make the title closer to content.
	legendSVG.select(".legendCells")
//	.attr("transform", "translate(0, 10)");
	.attr("transform", function(d){
		var x = legendSVG.select(".legendCells").node().transform.baseVal[0].matrix.e;
		var y = legendSVG.select(".legendCells").node().transform.baseVal[0].matrix.f;
		return "translate("+ x +", "+ (y - 10) +")";
	})
	
	if(hasNull){
		addNullLegendCell(SVG_id, legendSVG.select(".legendCells"), legendSymbol.rectangle, "#d0c8c8", "Null Value");
	}
	
	// Add stroke in legend like the choropleth map.
	legendSVG.selectAll("rect")
	.style("stroke-width", strokeWidth)
	.style("stroke", strokeColor)
	.attr("fill-opacity", baseMapSettings.fillOpacity / 100);
	
	// Make the boundary box larger to display full legend.
	adjustSVGSize(legendSVG, $("#g_CPMLegend")[0].getBBox().width + 40, $("#g_CPMLegend")[0].getBBox().height + 30);
}

function addUnclassifiedChoroplethMapLegend(legendSVG, SVG_id, legendTitle, colorScheme, strokeColor, strokeWidth, decimalPlaces){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG.append("g")
	  .attr("class", "legendLinear")
	  .attr("id", "g_CPMLegend")
	  .attr("transform", "translate(20, 30)");

	var legendLinear = d3.legendColor()
	.labelFormat(d3.format(",." + decimalPlaces + "f"))
	  .shapeWidth(30)
	  .title(legendTitle)
	  .titleWidth(baseMapSettings.titleWidth)
	  .orient('vertical')
	  .cells(3)
	  .scale(colorScheme);

	legendSVG.select(".legendLinear")
	  .call(legendLinear);
	
	legendSVG.selectAll("rect")
	.style("stroke-width", strokeColor)
	.style("stroke", strokeWidth)
	.attr("fill-opacity", baseMapSettings.fillOpacity / 100);
	
	adjustSVGSize(legendSVG, $("#g_CPMLegend")[0].getBBox().width + 40, $("#g_CPMLegend")[0].getBBox().height + 30);
}