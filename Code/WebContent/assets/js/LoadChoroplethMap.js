function parsePolygonDataOfChoroplethMap(jsonStr){
	var parsedInput = JSON.parse(jsonStr), jsonProperties, rsObject;
	if(isGeoJSON(jsonStr)){
		jsonProperties = Object.keys(JSON.parse(jsonStr).features[0].properties);
		rsObject = parsedInput;
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
		
		var jsonFeatures = topojson.feature(parsedInput, parsedInput.objects[featureKey]).features;
		jsonProperties = Object.keys(jsonFeatures[0].properties);
		rsObject = {features: jsonFeatures, type: "FeatureCollection", properties: jsonProperties};
	}
	
	updateSelectionBoxOptions("CPM_BMPK-Select", jsonProperties);
	return rsObject;
} 


function parseCSVDataOfChoroplethMap(data){
	var CSVData = d3.csvParse(data);
	var keyNames = Object.keys(CSVData[0]);
	
	updateSelectionBoxOptions("CPM_CSVPK-Select", keyNames);
	updateSelectionBoxOptions("CPM_Value-Select", keyNames);
	
	return CSVData;
}

function makeHashMapForChoroplethMap(CPMData){
	var selectedCSVID = baseMapSettings.CSVId;
	var selectedValue = baseMapSettings.value;
	var selectedGeomID = baseMapSettings.geoId;
	CPMIdValueMap = [];
	if(!Object.keys(CPMData[0]).includes(selectedCSVID)){
		alertFieldInputError("ID field of CSV data");
		return;
	}
	if(!Object.keys(baseMapData.features[0].properties).includes(selectedGeomID)) {
		alertFieldInputError("ID field of geometry data");
		return;
	}
	if(!Object.keys(CPMData[0]).includes(selectedValue)){
		alertFieldInputError("Field to Visualize");
		return;
	}
		
	CPMValue = [];
	var csv_data = [];
	CPMData.forEach(function (obj){
	    var pair = [obj[selectedCSVID], obj[selectedValue]];
	    csv_data.push(pair);
	    if(!obj[selectedValue])
	    	CPMValue.push(null);
	    else
	    	CPMValue.push(+obj[selectedValue]);
	});
	CPMIdValueMap = Object.assign(new Map(csv_data));
}


