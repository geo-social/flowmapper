function drawTitle(){
	removeTitle();
    
    var drag = d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended);
	
    var feature = gTitle
	  .append("text")
	  .attr("x", window.innerWidth / 2)
	  .attr("y", "65")
	  .style("cursor", "all-scroll")
	  .style("font-size", "30px")
	  .style("font-family", "Arial,sans-serif")
	  .text(baseMapSettings.title)
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

function removeTitle(){
    gTitle.selectAll("text").remove();
}