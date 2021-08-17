function addProjectionLabel(){
	if(!gPrj){
		gPrj = svg_user_painting.append("g");
	}
	
	removeProjectionLabel();
    
    var drag = d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended);
	
    var prjName;
    switch(baseMapSettings.projection){
		case "webMct":{
			prjName = "Web Mercator - WGS84";
			break;
		};
		case "abEqAreaUS":{
			prjName = "Albers Equal Area U.S. - WGS84";
			break;
		};
		case "abEqAreaAfc":{
			prjName = "Albers Equal Area Africa - WGS84";
			break;
		};
		case "abEqAreaAs":{
			prjName = "Albers Equal Area Austrilia - WGS84";
			break;
		};
		case "abEqAreaCn":{
			prjName = "Albers Equal Area China - WGS84";
			break;
		};
		case "abEqAreaEu":{
			prjName = "Albers Equal Area Europe - WGS84";
			break;
		};
		case "abEqAreaSthAm":{
			prjName = "Albers Equal Area South America - WGS84";
			break;
		};
		case "robin":{
			prjName = "Robinson Projection - WGS84";
			break;
		};
		case "gall":{
			prjName = "Gall Peters Projection - WGS84";
			break;
		};
		default:{
			prjName = "Unknown Projection";
			break;
		}
    }
    
    gPrj
	  .append("text")
	  .attr("x", window.innerWidth - 480)
	  .attr("y", window.innerHeight - 62)
	  .style("cursor", "all-scroll")
	  .style("font-size", "0.8em")
	  .style("font-family", "Arial,sans-serif")
	  .text("Projection: " + prjName)
	  .call(drag);
    
    function dragstarted(event, d) {
    	d3.select(this).raise().attr("stroke", "black");
    	
    	removePanInteraction();
    }

    function dragged(event, d) {
    	d3.select(this).attr("x", +d3.select(this).attr("x") + event.dx).attr("y",  +d3.select(this).attr("y") + event.dy);
    }

    function dragended(event, d) {
    	d3.select(this).attr("stroke", null);
    	
    	if(baseMapSettings.projection != "robin")
    		addPanInteraction();
    }
    
    resetMapOverlay();
}

function removeProjectionLabel(){
	gPrj.selectAll("text").remove();
}