function buildLegendFlowSymbolsRange(flowStyle, widthArr){
	var symbolArray = [];
	switch(flowStyle){
		case "curve":{
			for(var i = 0; i < widthArr.length; i++){
				symbolArray.push(drawCurve(30, 0, -30, 0, widthArr[i], 0, 0, true));
			}
			break;
		};
		case "strtHfArw":{
			for(var i = 0; i < widthArr.length; i++){
				symbolArray.push(drawStraightWithArrow(30, 0, -30, 0, widthArr[i], 0, 0));
			}
			break;
		};
		case "tapered":{
			for(var i = 0; i < widthArr.length; i++){
				symbolArray.push(drawTapered(30, 0, -30, 0, widthArr[i], 0, 0));
			}
			break;
		};
		case "tearDrop":{
			for(var i = 0; i < widthArr.length; i++){
				symbolArray.push(drawTearDrop(30, 0, -30, 0, widthArr[i], 0, 0));
			}
			break;
		};
		default:{
			console.log("Did not find draw function in legend.");
			break;
		}
	}
	return symbolArray;
}

function chooseLegendFlowStyle(legend, styleName){
	switch(styleName){
		case "straight":
		case "arc":{
			legend.shape("path", "M-10,1L10,1L10,-1L10,-1");
			break;
		};
		case "curve":{
			legend.shape("path", drawCurve(30, 0, -30, 0, 10, 0, 0, true));
			break;
		};
		case "strtHfArw":{
			legend.shape("path", drawStraightWithArrow(30, 0, -30, 0, 10, 0, 0));
			break;
		};
		case "tapered":{
			legend.shape("path", drawTapered(30, 0, -30, 0, 10, 0, 0));
			break;
		};
		case "tearDrop":{
			legend.shape("tearDrop", drawTearDrop(30, 0, -30, 0, 10, 0, 0));
			break;
		};
	}
}

function addClassifiedFlowLegend(legendSVG, SVG_id, legendTitle, colorScheme, strokeColor, strokeWidth, classification, flowStyle, isColorless, decimalPlaces, manualBreaksMinMax){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG.append("g")
	  .attr("class", "legendQuant")
	  .attr("id", "g_FlowLegend")
	  .attr("transform", "translate(20, 30)");
	
	var legend;
	if(!isColorless && $("#Flow_DisplayAsAbs-CB").is(":checked")){
		return;
	}
	
	var labelTexts;
	switch(classification){
		case "Quantile":{
			labelTexts = flowWidthScale.quantiles();
			break;
		};
		case "EqualInterval":{
			labelTexts = flowWidthScale.thresholds();
			break;
		};
		case "ManualBreak":{
			labelTexts = flowWidthScale.domain();
			break;
		};
		case "NaturalBreak":{
			labelTexts = flowWidthScale.domain();
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
	  .range(buildLegendFlowSymbolsRange(flowStyle, flowWidthScale.range()));
	legend = d3.legendSymbol()
	  .title(legendTitle)
	  .titleWidth(flowMapSettings.titleWidth)
	  .labelOffset(flowMapSettings.labelOffset)
	  .labelFormat(d3.format(",." + decimalPlaces + "f"))
	  .scale(symbolScale)
	  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
		if (i === 0) {
			var min = d3.format(",." + decimalPlaces + "f")(d3.min(topVolumeList_modified));
			if(classification === "ManualBreak"){
				min = d3.format(",." + decimalPlaces + "f")(manualBreaksMinMax[0]);
			}
			var formatedNum = d3.format(",." + decimalPlaces + "f")(generatedLabels[i]);
		    return `${min} to ${formatedNum}`;
		}
		var formatedNum = d3.format(",." + decimalPlaces + "f")(generatedLabels[i - 1]);
		var formatedNum2 = d3.format(",." + decimalPlaces + "f")(generatedLabels[i]);
		
		if(classification === "ManualBreak" && i === genLength - 1){
			formatedNum2 = d3.format(",." + decimalPlaces + "f")(manualBreaksMinMax[1]);
		}
		return `${formatedNum} to ${formatedNum2}`;
	});
	
	legendSVG.select(".legendQuant")
	  .call(legend);
	
	
	legendSVG.selectAll("path")
	.attr("fill", d => colorScheme(d - 0.00000001))
	.style("stroke-width", strokeWidth)
	.style("stroke", strokeColor)
	.attr("fill-opacity", flowMapSettings.fillOpacity / 100);
	
	// Make the boundary box larger to display full legend.
	adjustSVGSize(legendSVG, $("#g_FlowLegend")[0].getBBox().width + 40, $("#g_FlowLegend")[0].getBBox().height + 30);
}

function addUnclassifiedFlowLegend(legendSVG, SVG_id, legendTitle, colorScheme, strokeColor, strokeWidth, classification, flowStyle, isDisplayedAsAbs, decimalPlaces, topFlows){
	removeOldLegendGraph(legendSVG);
	
	legendSVG.style("display", "block");
	
	legendSVG.append("g")
	  .attr("class", "legendLinear")
	  .attr("id", "g_FlowLegend")
	  .attr("transform", "translate(20, 30)");
	
	var legend;
	if(isDisplayedAsAbs){
		var flowWidthDomain, flowPaths;
		
		if(d3.min(topVolumeList) < 0){
			flowWidthDomain = [d3.min(topVolumeList), d3.max(topVolumeList)];
			var flowWidthArr = [flowWidthScale(Math.abs(d3.min(topVolumeList))), flowWidthScale(Math.abs(d3.max(topVolumeList)))];
			flowPaths = buildLegendFlowSymbolsRange(flowStyle, flowWidthArr);
		}else{
			flowWidthDomain = [d3.max(topVolumeList)];
			var flowWidthArr = [flowWidthScale(Math.abs(d3.max(topVolumeList)))];
			flowPaths = buildLegendFlowSymbolsRange(flowStyle, flowWidthArr);
		}
		
		var symbolScale =  d3.scaleOrdinal()
		  .domain(flowWidthDomain)
		  .range(flowPaths);
		
		
		legend = d3.legendSymbol()
		  .title(legendTitle)
		  .titleWidth(flowMapSettings.titleWidth)
		  .labelOffset(flowMapSettings.labelOffset)
		  .labelFormat(d3.format(",." + decimalPlaces + "f"))
		  .scale(symbolScale)
		  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
			  if(genLength == 1){
				  return `0 to ${d3.max(topVolumeList).toFixed(decimalPlaces)}`;
			  }else{
				  if (i === 0) {
				    return `${d3.min(topVolumeList).toFixed(decimalPlaces)} to 0`;
				  } 
				  return `0 to ${d3.max(topVolumeList).toFixed(decimalPlaces)}`;
			  }
			});
	}else{
		var flowWidthDomain, flowPaths;
		flowWidthDomain = [d3.min(topFlows), (d3.min(topFlows) + d3.max(topFlows))/2, d3.max(topFlows)];
		var flowWidthArr = [flowWidthScale(d3.min(topFlows)), flowWidthScale((d3.min(topFlows) + d3.max(topFlows))/2), flowWidthScale(d3.max(topFlows))];
		flowPaths = buildLegendFlowSymbolsRange(flowStyle, flowWidthArr);
		
		var symbolScale =  d3.scaleOrdinal()
		  .domain(flowWidthDomain)
		  .range(flowPaths);
		
		legend = d3.legendSymbol()
		  .title(legendTitle)
		  .titleWidth(flowMapSettings.titleWidth)
		  .labelOffset(flowMapSettings.labelOffset)
		  .scale(symbolScale)
		  .labels(function({i,genLength,generatedLabels,labelDelimiter}) {
			  	  var formatedNum = d3.format(",." + decimalPlaces + "f")(generatedLabels[i]);
				  return `${formatedNum}`;
			});
	}
	
	legendSVG.select(".legendLinear")
	  .call(legend);
	
	legendSVG.selectAll("path")
	.attr("fill", d => colorScheme(d))
	.style("stroke-width", strokeWidth)
	.style("stroke", strokeColor)
	.attr("fill-opacity", flowMapSettings.fillOpacity / 100);
	
	// Make the boundary box larger to display full legend.
	adjustSVGSize(legendSVG, $("#g_FlowLegend")[0].getBBox().width + 40, $("#g_FlowLegend")[0].getBBox().height + 30);
}