function parseReferenceJSON(jsonStr){
	var parsedInput = JSON.parse(jsonStr), jsonProperties, rsObject;
	if(isGeoJSON(jsonStr)){
		jsonProperties = Object.keys(JSON.parse(jsonStr).features[0].properties);
		rsObject = parsedInput;
	}
	else{
		popErrorWindow("Please input GeoJSON as the reference.");
	}
	
	updateSelectionBoxOptions("BaseMap_Reference-Select", jsonProperties);
	return rsObject;
} 

function drawReference(){
	if(!refData)
		return;
	removeReference();
	updateBaseMapSettings();
	
    var features = gRef.selectAll("circle")
		.data(refData.features)
		.enter()
		
	features.append("text")
        .attr("dx", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[0] + 5;
        })
        .attr("dy", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[1];
        })
        .style("font-size", baseMapSettings.labelFontSize + "px")
        .style("opacity", +baseMapSettings.refOpacity / 100)
        .style("fill", baseMapSettings.refColor)
        .text(function(d){return d.properties[$("#BaseMap_Reference-Select").val()];});
    
	features.append("circle")
        //attr should be placed on the bottom of what you want to add otherwise it won't be added
        .attr("cx", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[0];
        })
        .attr("cy", function(d){
        	return projectToOnlineBaseMap(d.geometry.coordinates)[1];
        })
        .attr("r",  baseMapSettings.refRadius)
        .attr("fill", "black");
}

function removeReference(){
	gRef.selectAll("*").remove();
}