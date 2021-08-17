function generateCentroidsFromJSONToCSV(jsonInput){
	// Distinguish between geoJSON and topoJSON
	var parsedInput = JSON.parse(jsonInput);
	var features;
	var properties;
	// If it is geoJSON:
	if(JSON.parse(jsonInput).features){
		features = JSON.parse(jsonInput).features;
		properties = Object.keys(JSON.parse(jsonInput).features[0].properties);
	}
	// If it is topoJSON:
	else{
		
		let featureKey = null;
		for (var key in parsedInput.objects) {
			if (parsedInput.objects[key].type != null)
				featureKey = key;
		}
		if (!featureKey) {
			addMessage("No data.objects Features Object");
			return;
		}
		
		features = topojson.feature(parsedInput, parsedInput.objects[featureKey]).features;
		properties = Object.keys(features[0].properties);
	}
	
	// Hard copy the input data.
    var rows = [];
    // Add the first row
    var firstRow = [];
    properties.forEach(function(key){
    	firstRow.push(key);
    });
    firstRow.push('x');
    firstRow.push('y');
    rows.push(firstRow);
    
	features.forEach(function(feature){
		// Add properties of this feature:
		var newRow = [];
		var properties = feature.properties;
		for (let value of Object.values(properties)) {
			newRow.push(value);
		}
		
		// Add coordinates of this feature:
		var centroidInPixel = pathOnOBM.centroid(feature);
		var centroid = map.getCoordinateFromPixel(centroidInPixel);
		if(baseMap.projection != "EPSG:4326"){
			var centroidIn4326 = ol.proj.transform(centroid, baseMap.projection, "EPSG:4326");
			newRow.push(centroidIn4326[0]);
			newRow.push(centroidIn4326[1]);
		}
		rows.push(newRow);
	})
	
	var processRow = function (row) {
        var finalVal = '';
        for (var j = 0; j < row.length; j++) {
            var innerValue = row[j] === null ? '' : row[j].toString();
            if (row[j] instanceof Date) {
                innerValue = row[j].toLocaleString();
            };
            var result = innerValue.replace(/"/g, '""');
            if (result.search(/("|,|\n)/g) >= 0)
                result = '"' + result + '"';
            if (j > 0)
                finalVal += ',';
            finalVal += result;
        }
        return finalVal + '\n';
    };

    var csvFile = '';
    for (var i = 0; i < rows.length; i++) {
        csvFile += processRow(rows[i]);
    }

    var blob = new Blob([csvFile], { type: 'text/csv;charset=utf-8;' });
    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, "data.csv");
    } else {
        var link = document.getElementById('MapDownload-A');
        if (link.download !== undefined) { 
        	// feature detection
            // Browsers that support HTML5 download attribute
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download",  "centroids.csv");
            link.style.visibility = 'hidden';
            link.click();
        }
    }
}