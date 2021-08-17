function addNorthArrow(){
	removeNorthArrow();
    
	var unit = map.getView().getProjection().getUnits();
    var resolution = map.getView().getResolution();
    var inchesPerMetre = 39.37;
var dpi = 25.4 / 0.28;
    var test=  resolution * ol.proj.METERS_PER_UNIT[unit] * inchesPerMetre * dpi;
	
    var drag = d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended);
	
    var path1 = "M3527 6127 c-224 -452 -859 -1731 -1412 -2841 -625 -1256 -1005 -2030 -1005 -2048 0 -31 7 -35 24 -14 6 8 146 121 311 253 301 240 1042 840 1963 1588 271 220 497 401 501 403 5 1 641 -501 1415 -1117 911 -725 1413 -1118 1422 -1114 8 3 14 13 12 23 -4 22 -2811 5690 -2818 5689 -3 0 -188 -370 -413 -822z m398 -278 c-8 -552 -17 -1303 -19 -1669 l-4 -665 -433 -353 c-1019 -830 -2285 -1852 -2294 -1852 -3 0 246 503 553 1117 307 615 929 1864 1382 2775 453 912 825 1656 827 1654 2 -2 -3 -455 -12 -1007z"
    var path2 = "M3400 2520 l0 -50 85 0 85 0 0 -560 0 -560 -85 0 -85 0 0 -55 0 -55 235 0 235 0 0 55 0 55 -90 0 -90 0 0 480 c0 264 2 480 3 480 2 0 190 -245 418 -545 l414 -545 57 0 58 0 0 625 0 625 90 0 90 0 0 50 0 50 -235 0 -235 0 0 -50 0 -50 85 0 85 0 0 -457 c0 -385 -2 -455 -14 -443 -7 8 -181 237 -386 508 l-373 492 -174 0 -173 0 0 -50z";
    
    gNA.attr("transform", "translate("+ (window.innerWidth - 80) +"," + 80 + ") scale(0.005000,-0.006875)")
	  .style("cursor", "all-scroll")
	  .call(drag);
    
    var feature1 = gNA
	  .append("path")
	  .attr("d", path1)
	  
	var feature2 = gNA
	  .append("path")
	  .attr("d", path2)

    
    function dragstarted(event, d) {
    	removePanInteraction();
    }
    
    function dragged(event, d) {
    	var transform  = d3.select(this).attr("transform");
    	var translate = transform.substring(transform.indexOf("(")+1, transform.indexOf(")")).split(",");
    	d3.select(this).attr("transform", "translate("+ (+translate[0] + event.dx) +"," + (+translate[1]  + event.dy) + ") scale(0.005000,-0.006875)");
    }

    function dragended(event, d) {
    	if(baseMapSettings.projection != "robin")
    		addPanInteraction();
    }
}

function removeNorthArrow(){
	gNA.selectAll("path").remove();
}