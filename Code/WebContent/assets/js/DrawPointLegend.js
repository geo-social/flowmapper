function addUnclassifiedPointLegend(legendSVG, SVG_id, legendTitle, sizeScale, colorScheme, strokeColor, strokeWidth, isDisplayedAsAbs, hasNull, decimalPlaces){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG.append("g")
	  .attr("id", "g_PointLegend")
	  .attr("class", "pointLegendGraph")
	  .attr("transform", "translate(20, 30)");
	
	if(isDisplayedAsAbs){
		var circleRadius, circleDomain;
		if(d3.min(nodesizeattribute) < 0){
			circleRadius = [circlePathGen(0, 0, pointScale(Math.abs(d3.min(nodesizeattribute)))), circlePathGen(0, 0, pointScale(Math.abs(d3.max(nodesizeattribute))))]
			circleDomain = [d3.min(nodesizeattribute), d3.max(nodesizeattribute)];
		}else{
			circleRadius = [circlePathGen(0, 0, pointScale(Math.abs(d3.max(nodesizeattribute))))];
			circleDomain = [d3.max(nodesizeattribute)];
		}
		
		var symbolScale =  d3.scaleOrdinal()
		  .domain(circleDomain)
		  .range(circleRadius);
		
		
		var legendCircleAbs = d3.legendSymbol()
		  .title(legendTitle)
		  .titleWidth(flowMapSettings.titleWidth)
		  .titleWidth(100)
		  .scale(symbolScale)
		  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
			  if(genLength == 1){
				  return `0 to ${d3.max(nodesizeattribute).toFixed(decimalPlaces)}`;
			  }else{
				  if (i === 0) {
				    return `${d3.min(nodesizeattribute).toFixed(decimalPlaces)} to 0`;
				  } 
				  return `0 to ${d3.max(nodesizeattribute).toFixed(decimalPlaces)}`;
			  }
			});
		
		
		legendSVG.select(".pointLegendGraph")
		  .call(legendCircleAbs);
		
		legendSVG.selectAll("g_PointLegend path").each(function(d) {
			  d3.select(this).style("fill", scale(d))
		})
		.style("stroke-width", strokeWidth)
		.style("stroke", strokeColor)
		.attr("opacity", pointMapSettings.opacity);

	}else{
		var legendSize = d3.legendSize()
		  .labelFormat(d3.format(",." + decimalPlaces + "f"))
		  .scale(sizeScale)
		  .cells(3)
		  .title(legendTitle)
		  .titleWidth(flowMapSettings.titleWidth)
		  .shape('circle')
		  .shapePadding(15)
		  .labelOffset(20)
		  .orient('vertical');
		
		legendSVG.select(".pointLegendGraph")
		.call(legendSize);
		
		// Since we are using size legend, the data we are using is the radius of circles, which can not be used in painting colors. 
		// As an instead, we should use the domain rather than data to draw colors.
		legendSVG.selectAll("circle")
		.style("stroke-width", strokeWidth)
		.style("stroke", strokeColor)
		.attr("fill", function(d, i) {
			return colorScheme(d);
		})
		.attr("fill-opacity", pointMapSettings.fillOpacity / 100);
		
		// Add the row of null value in the legend.
		if(hasNull){
			addNullLegendCell(legendSVG.select(".legendCells"), legendSymbol.circle, "#d0c8c8", "Null Value");
		}
	}

	// Make the boundary box larger to display full legend.
	adjustSVGSize(legendSVG, $("#g_PointLegend")[0].getBBox().width + 40, $("#g_PointLegend")[0].getBBox().height + 30);
	
	function circlePathGen(cx, cy, myr){
		return "M" + cx + "," + cy + " " +
        "m" + -myr + ", 0 " +
        "a" + myr + "," + myr + " 0 1,0 " + myr*2  + ",0 " +
        "a" + myr + "," + myr + " 0 1,0 " + -myr*2 + ",0Z";;
	}
}

function addClassifiedPointLegend(legendSVG, SVG_id, legendTitle, sizeScale, colorScheme, strokeColor, strokeWidth, manualBreaksMinMax, hasNull, decimalPlaces){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG .append("g")
	  .attr("class", "legendSize")
	  .attr("id", "g_PointLegend")
	  .attr("transform", "translate(20, 40)");

	var legendSize = d3.legendSize()
	  .labelFormat(d3.format(",." + decimalPlaces + "f"))
	  .scale(sizeScale)
	  .title(legendTitle)
	  .titleWidth(flowMapSettings.titleWidth)
	  .shape('circle')
	  .shapePadding(15)
	  .labelOffset(20)
	  .orient('vertical');

	if(pointMapSettings.cfMethod == "ManualBreak"){
		legendSize.labels(function({
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
		  return generatedLabels[i];
		});
		
		legendSVG.select(".legendSize")
		.call(legendSize);
		
		// Since we are using size legend, the data we are using is the radius of circles, which can not be used in painting colors. 
		// As an instead, we should use the domain rather than data to draw colors.
		var colorValues = sizeScale.domain();
		colorValues.unshift(colorValues[0]-1);
		legendSVG.selectAll("circle")
		.style("stroke-width", strokeWidth)
		.style("stroke", strokeColor)
		.attr("fill", function(d, i) {
				return colorScheme(colorValues[i]);
		})
		.attr("fill-opacity", pointMapSettings.fillOpacity / 100);
	}else{
		legendSize.labels(function({
		  i,
		  genLength,
		  generatedLabels,
		  labelDelimiter
		}) {
		  if (i === 0) {
		    const values = generatedLabels[i].split(` ${labelDelimiter} `);
		    return `${d3.min(nodesizeattribute_modified).toFixed(decimalPlaces)} to ${values[1]}`
		  } else if (i === genLength - 1) {
		    const values = generatedLabels[i].split(` ${labelDelimiter} `)
		    return `${values[0]} to ${d3.max(nodesizeattribute_modified).toFixed(decimalPlaces)}`
		  }
		  return generatedLabels[i]
		});
		
		legendSVG.select(".legendSize")
		.call(legendSize);
		
		var colorValues;
		switch(pointMapSettings.cfMethod){
			case "Quantile":{
				colorValues = colorScheme.quantiles();
				break;
			};
			case "EqualInterval":{
				colorValues = colorScheme.thresholds();
				break;
			};
			case "NaturalBreak":{
				colorValues = colorScheme.domain();
				break;
			};
			default :{
				alert("Can not draw flow legend in this classification");
				break;
			}
		}
		
		colorValues.unshift(colorValues[0]-1);
		legendSVG.selectAll("circle")
		.style("stroke-width", strokeWidth)
		.style("stroke", strokeColor)
		.attr("fill", function(d, i) {
				return colorScheme(colorValues[i]);
		})
		.attr("fill-opacity", pointMapSettings.fillOpacity / 100);
	}
	
	// Make the boundary box larger to display full legend.
	adjustSVGSize(legendSVG, $("#g_PointLegend")[0].getBBox().width + 40, $("#g_PointLegend")[0].getBBox().height + 30);
}