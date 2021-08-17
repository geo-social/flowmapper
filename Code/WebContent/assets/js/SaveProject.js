function getDate(){
	var today = new Date();
	var dd = String(today.getDate()).padStart(2, '0');
	var mm = String(today.getMonth() + 1).padStart(2, '0'); //January is 0!
	var yyyy = today.getFullYear();

	today = mm + '/' + dd + '/' + yyyy;
	return today;
}

function saveProject(){
	var page = {
    		projectName: "test project",
    		date: getDate()
	};
	
	// Save the most up-to-date interface settings to the project file.
	updateBaseMapSettings();
	updatePointMapSettings();
	updateFlowMapSettings();
	
	if(refData){
		page.refData = refData;
	}
	
	// Save choropleth map.
	var onlineBaseMapSettings = {
			baseMap: baseMapSettings.baseMap,
			projection: baseMapSettings.projection,
			ifDisplayReferences: baseMapSettings.ifDisplayReferences,
			baseMapOpacity: baseMapSettings.baseMapOpacity,
			ifAddTitle: baseMapSettings.ifAddTitle,
			title: baseMapSettings.title,
			ifAddNorthArrow:baseMapSettings.ifAddNorthArrow,
			ifAddProjectionLabel: baseMapSettings.ifAddProjectionLabel,
			ifUploadReferences: baseMapSettings.ifUploadReferences,
			
			//reference
			referenceField: baseMapSettings.referenceField,
			labelFontSize: baseMapSettings.labelFontSize,
			refRadius: baseMapSettings.refRadius,
			refColor: baseMapSettings.refColor,
			refOpacity: baseMapSettings.refOpacity,
			ifRefTop: baseMapSettings.ifRefTop
	}
	page.onlineBaseMapSettings = onlineBaseMapSettings;
	
	var selfDesignedBaseMapSettings = {
			cfMethod: baseMapSettings.cfMethod,
			clrScheme: baseMapSettings.clrScheme,
			minCustomColor: baseMapSettings.minCustomColor,
			maxCustomColor: baseMapSettings.maxCustomColor,
			ifFlipColor: baseMapSettings.ifFlipColor,
			decimalPlaces: baseMapSettings.decimalPlaces,
			clsNum: baseMapSettings.clsNum,
			fillOpacity: baseMapSettings.fillOpacity,
			strokeColor: baseMapSettings.strokeColor,
			strokeWidth: baseMapSettings.strokeWidth,
			legendTitle: baseMapSettings.legendTitle,
			breakInput: baseMapSettings.breakInput,
			ifHideNull: baseMapSettings.ifHideNull
	};
	page.selfDesignedBaseMapSettings = selfDesignedBaseMapSettings;
	
	if(baseMapData){
		page.selfDesignedBaseMapData = baseMapData;
	}
	
	if(CPMData){
		var choroplethMapSettings = {
				CSVId: baseMapSettings.CSVId,
				geoId: baseMapSettings.geoId,
				value: baseMapSettings.value
		};
		page.choroplethMapSettings = choroplethMapSettings;
		page.choroplethMapData = CPMData;
	}
	
	// Save point map:
	var pointMapFileSettings = {
			id: pointMapSettings.id,
			X: pointMapSettings.X,
			Y: pointMapSettings.Y,
			volume: pointMapSettings.volume,
			ifMapAttribute: pointMapSettings.ifMapAttribute,
			cfMethod: pointMapSettings.cfMethod, // Scaling for size.
			clsNum:  pointMapSettings.clsNum,
			clrScheme: pointMapSettings.clrScheme, // Node fill-color.
			minCustomColor: pointMapSettings.minCustomColor,
			maxCustomColor: pointMapSettings.maxCustomColor,
			noAttrFillColor: pointMapSettings.noAttrFillColor,
			fillOpacity: pointMapSettings.fillOpacity,
			radiusMin: pointMapSettings.radiusMin,
			radiusMax: pointMapSettings.radiusMax,
			strokeColor: pointMapSettings.strokeColor,
			ifFlipColor: pointMapSettings.ifFlipColor,
			strokeWidth: pointMapSettings.strokeWidth,
			decimalPlaces: pointMapSettings.decimalPlaces,
			legendTitle: pointMapSettings.legendTitle,
			breakInput: pointMapSettings.breakInput,
			isDisplayedAsAbs: pointMapSettings.isDisplayedAsAbs, // Display as absolute (it is temporarily hidden from the interface).
			// Legend settings:
			titleWidth: 200
	};
	
	page.pointMapFileSettings = pointMapFileSettings;
	
	if(pointData){
		page.pointData = pointData;
	}
	
	// Save flow map:
	var flowMapFileSettings = {
			origin: flowMapSettings.origin,
			destination: flowMapSettings.destination,
			volume: flowMapSettings.volume,
			flowStyleName: flowMapSettings.flowStyleName, // Name of flow style.
			cfMethod: flowMapSettings.cfMethod,
			clrScheme: flowMapSettings.clrScheme,
			minCustomColor: flowMapSettings.minCustomColor,
			maxCustomColor: flowMapSettings.maxCustomColor,
			fillOpacity: flowMapSettings.fillOpacity,
			ifFlipColor: flowMapSettings.ifFlipColor,
			decimalPlaces: flowMapSettings.decimalPlaces,
			clsNum: flowMapSettings.clsNum,
			numTopFlows: flowMapSettings.numTopFlows,
			breakInput: flowMapSettings.breakInput,
			widthMax: flowMapSettings.widthMax,
			widthMin: flowMapSettings.widthMin,
			strokeWidth: flowMapSettings.strokeWidth,
			strokeColor: flowMapSettings.strokeColor,
			legendTitle: flowMapSettings.legendTitle,
			isDisplayedAsAbs: flowMapSettings.isDisplayedAsAbs, // Display as absolute (it is temporarily hidden from the interface).
			
			// Legend settings:
			titleWidth: 200
	};
	
	page.flowMapFileSettings = flowMapFileSettings;
	
	if(flowData){
		page.flowData = flowData;
	}
	
	const a = document.createElement("a");
	a.href = URL.createObjectURL(new Blob([JSON.stringify(page, null, 2)], {
	  type: "text/plain"
	}));
	a.setAttribute("download", "projectfile.json");
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
}