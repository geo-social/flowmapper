function setSelectionAndTextBox(id, value){
	var elemt = document.getElementById(id);
	if(elemt){
		elemt.value = value;
		$("#"+id).change();
	}else{
		logProjectLoading(id);
	}
}

function setCheckBox(id, value){
	var elemt = document.getElementById(id);
	if(elemt){
		elemt.checked = value;
		$("#"+id).change();
	}else{
		logProjectLoading(id);
	}
}

function updateBaseMapSettingsFromProjectFile(project){
	// Inputs for base map.
	baseMapSettings.baseMap = project.onlineBaseMapSettings.baseMap;
	baseMapSettings.projection = project.onlineBaseMapSettings.projection;
	baseMapSettings.ifDisplayReferences = project.onlineBaseMapSettings.ifDisplayReferences;
	baseMapSettings.baseMapOpacity = +project.onlineBaseMapSettings.baseMapOpacity;
	baseMapSettings.ifAddTitle = project.onlineBaseMapSettings.ifAddTitle;
	baseMapSettings.title = project.onlineBaseMapSettings.title;
	baseMapSettings.ifAddNorthArrow = project.onlineBaseMapSettings.ifAddNorthArrow;
	baseMapSettings.ifAddProjectionLabel = project.onlineBaseMapSettings.ifAddProjectionLabel;
	
	// Reference:
	baseMapSettings.ifUploadReferences = project.onlineBaseMapSettings.ifUploadReferences;
	baseMapSettings.referenceField = project.onlineBaseMapSettings.referenceField;
	baseMapSettings.labelFontSize = project.onlineBaseMapSettings.labelFontSize;
	baseMapSettings.refRadius = project.onlineBaseMapSettings.refRadius;
	baseMapSettings.refColor = project.onlineBaseMapSettings.refColor;
	baseMapSettings.refOpacity = project.onlineBaseMapSettings.refOpacity;
	baseMapSettings.ifRefTop = project.onlineBaseMapSettings.ifRefTop;
	
	// Inputs for choroplethMap
	baseMapSettings.cfMethod =  project.selfDesignedBaseMapSettings.cfMethod; // Classification method.
	baseMapSettings.clrScheme =  project.selfDesignedBaseMapSettings.clrScheme; // Color scheme.
	baseMapSettings.minCustomColor = project.selfDesignedBaseMapSettings.minCustomColor;
	baseMapSettings.maxCustomColor = project.selfDesignedBaseMapSettings.maxCustomColor;
	baseMapSettings.ifFlipColor =  project.selfDesignedBaseMapSettings.ifFlipColor; // If to flip the color.
	baseMapSettings.decimalPlaces = project.selfDesignedBaseMapSettings.decimalPlaces;
	baseMapSettings.clsNum = project.selfDesignedBaseMapSettings.clsNum; // Number of classes
	baseMapSettings.fillOpacity = project.selfDesignedBaseMapSettings.fillOpacity;
	baseMapSettings.strokeColor = project.selfDesignedBaseMapSettings.strokeColor;
	baseMapSettings.strokeWidth = project.selfDesignedBaseMapSettings.strokeWidth;
	baseMapSettings.legendTitle = project.selfDesignedBaseMapSettings.legendTitle;
	baseMapSettings.breakInput = project.selfDesignedBaseMapSettings.breakInput; // Input for manual break.
	baseMapSettings.ifHideNull = project.selfDesignedBaseMapSettings.ifHideNull;
	
	if('choroplethMapData' in project){
		// Inputs for CSV data.
		baseMapSettings.CSVId =  project.choroplethMapSettings.CSVId; // ID for the CSV.
		baseMapSettings.geoId =  project.choroplethMapSettings.geoId; // ID for the base map polygons.
		baseMapSettings.value =  project.choroplethMapSettings.value; // Input for the value field from CSV data.
	}
}

function updateBaseMapInterfaceFromProjectFile(project){
	setSelectionAndTextBox("Online_BaseMap-Select", project.onlineBaseMapSettings.baseMap);
	setSelectionAndTextBox("MapProjection-Select", project.onlineBaseMapSettings.projection);
	setCheckBox("DisplayMapReference-CB", project.onlineBaseMapSettings.ifDisplayReferences);
	setSelectionAndTextBox("CPM_BaseMapOpacity-Input", project.onlineBaseMapSettings.baseMapOpacity);
	setCheckBox("AddTitle-CB", project.onlineBaseMapSettings.ifAddTitle);
	setSelectionAndTextBox("MapTitle-Input", project.onlineBaseMapSettings.title);
	setCheckBox("AddNorthArrow-CB", project.onlineBaseMapSettings.ifAddNorthArrow);
	setCheckBox("AddProjectionLabel-CB", project.onlineBaseMapSettings.ifAddProjectionLabel);
	
	//Reference
	setCheckBox("UploadReference-CB", project.onlineBaseMapSettings.ifUploadReferences);
	if('refData' in project){
		updateSelectionBoxOptions("BaseMap_Reference-Select", Object.keys(project.refData.features[0].properties));
		setSelectionAndTextBox("BaseMap_Reference-Select", project.onlineBaseMapSettings.referenceField);
		setSelectionAndTextBox("BaseMap_LabelFontSize-Input", project.onlineBaseMapSettings.labelFontSize);
		setSelectionAndTextBox("BaseMap_LabelRadius-Input", project.onlineBaseMapSettings.refRadius);
		setSelectionAndTextBox("BaseMap_LabelColor-Input", project.onlineBaseMapSettings.refColor);
		setSelectionAndTextBox("BaseMap_LabelOpacity-Input", project.onlineBaseMapSettings.refOpacity);
		setCheckBox("BaseMap_LebelTop-CB", project.onlineBaseMapSettings.ifRefTop);
	}
	
	
	setSelectionAndTextBox("CPM_Classification-Select", project.selfDesignedBaseMapSettings.cfMethod);
	// Run this change function because the color scheme options are different for proportional and classified color scheme!
	// Don't run the change function will result in failures in some project settings.
	$("#CPM_Classification-Select").change();
	setSelectionAndTextBox("CPM_ColorScheme-Select", project.selfDesignedBaseMapSettings.clrScheme);
	setSelectionAndTextBox("CPM_MinCustomColor-Input", project.selfDesignedBaseMapSettings.minCustomColor);
	setSelectionAndTextBox("CPM_MaxCustomColor-Input", project.selfDesignedBaseMapSettings.maxCustomColor);
	setCheckBox("CPM_FlipLgClr-CB", project.selfDesignedBaseMapSettings.ifFlipColor);
	setSelectionAndTextBox("CPM_LegendDP-Input", project.selfDesignedBaseMapSettings.decimalPlaces);
	setSelectionAndTextBox("CPM_ClassNum-Input", project.selfDesignedBaseMapSettings.clsNum);
	setSelectionAndTextBox("CPM_FillOpacity-Input", project.selfDesignedBaseMapSettings.fillOpacity);
	setSelectionAndTextBox("CPM_StrokeColor-Input", project.selfDesignedBaseMapSettings.strokeColor);
	setSelectionAndTextBox("CPM_StrokeWidth-Input", project.selfDesignedBaseMapSettings.strokeWidth);
	setSelectionAndTextBox("CPM_LegendTitle-Input", project.selfDesignedBaseMapSettings.legendTitle);
	setSelectionAndTextBox("CPM_ManualBreak-Input", project.selfDesignedBaseMapSettings.breakInput);
	setCheckBox("CPM_HideNull-CB", project.selfDesignedBaseMapSettings.ifHideNull);
	
	// Reset the options of selection box in case further parameter changes.
	if('choroplethMapData' in project){
		$(".CPM_CSV-Row").css("display", "table-row");
		updateSelectionBoxOptions("CPM_CSVPK-Select", Object.keys(project.choroplethMapData[0]));
		updateSelectionBoxOptions("CPM_BMPK-Select", Object.keys(project.selfDesignedBaseMapData['features'][0].properties));
		updateSelectionBoxOptions("CPM_Value-Select", Object.keys(project.choroplethMapData[0]));
		setSelectionAndTextBox("CPM_CSVPK-Select", project.choroplethMapSettings.CSVId);
		setSelectionAndTextBox("CPM_BMPK-Select", project.choroplethMapSettings.geoId);
		setSelectionAndTextBox("CPM_Value-Select", project.choroplethMapSettings.value);
	}
}

function updatePointMapSettingsFromProjectFile(project){
	pointMapSettings.id = project.pointMapFileSettings.id;
	pointMapSettings.X = project.pointMapFileSettings.X;
	pointMapSettings.Y = project.pointMapFileSettings.Y;
	pointMapSettings.volume = project.pointMapFileSettings.volume;
	pointMapSettings.ifMapAttribute = project.pointMapFileSettings.ifMapAttribute;
	pointMapSettings.cfMethod = project.pointMapFileSettings.cfMethod; // Scaling for size.
	pointMapSettings.clsNum = project.pointMapFileSettings.clsNum; 
	pointMapSettings.clrScheme = project.pointMapFileSettings.clrScheme; // Node fill-color.
	pointMapSettings.minCustomColor = project.pointMapFileSettings.minCustomColor;
	pointMapSettings.maxCustomColor = project.pointMapFileSettings.maxCustomColor;
	pointMapSettings.noAttrFillColor = project.pointMapFileSettings.noAttrFillColor;
	pointMapSettings.fillOpacity = project.pointMapFileSettings.fillOpacity;
	pointMapSettings.radiusMin = project.pointMapFileSettings.radiusMin;
	pointMapSettings.radiusMax = project.pointMapFileSettings.radiusMax;
	pointMapSettings.strokeColor = project.pointMapFileSettings.strokeColor;
	pointMapSettings.ifFlipColor = project.pointMapFileSettings.ifFlipColor;
	pointMapSettings.strokeWidth = project.pointMapFileSettings.strokeWidth;
	pointMapSettings.decimalPlaces = project.pointMapFileSettings.decimalPlaces;
	pointMapSettings.breakInput = project.pointMapFileSettings.breakInput;
	pointMapSettings.legendTitle = project.pointMapFileSettings.legendTitle;
//	pointMapSettings.isDisplayedAsAbs = project.pointMapFileSettings.isDisplayedAsAbs; // Display as absolute (it is temporarily hidden from the interface).
}

function updatePointMapInterfaceFromProjectFile(project){
	if(project.pointData){
		updateSelectionBoxOptions("Point_ID-Select", Object.keys(project.pointData[0]));
		updateSelectionBoxOptions("Point_X-Select", Object.keys(project.pointData[0]));
		updateSelectionBoxOptions("Point_Y-Select", Object.keys(project.pointData[0]));
		updateSelectionBoxOptions("Point_Volume-Select", Object.keys(project.pointData[0]));
	}
	setSelectionAndTextBox("Point_ID-Select", project.pointMapFileSettings.id);
	setSelectionAndTextBox("Point_X-Select", project.pointMapFileSettings.X);
	setSelectionAndTextBox("Point_Y-Select", project.pointMapFileSettings.Y);
	setSelectionAndTextBox("Point_Volume-Select", project.pointMapFileSettings.volume);
	setCheckBox("Point_MapAttribute-CB", project.pointMapFileSettings.ifMapAttribute);
	setSelectionAndTextBox("Point_Classification-Select", project.pointMapFileSettings.cfMethod);
	$("#Point_Classification-Select").change();
	setSelectionAndTextBox("Point_ColorScheme-Select", project.pointMapFileSettings.clrScheme);
	setSelectionAndTextBox("Point_MinCustomColor-Input", project.pointMapFileSettings.minCustomColor);
	setSelectionAndTextBox("Point_MaxCustomColor-Input", project.pointMapFileSettings.maxCustomColor);
	setSelectionAndTextBox("Point_FillColor_NoAttr-Input", project.pointMapFileSettings.noAttrFillColor);
	setSelectionAndTextBox("Point_FillOpacity-Input", project.pointMapFileSettings.fillOpacity);
	setSelectionAndTextBox("Point_ClassNum-Input", project.pointMapFileSettings.clsNum);
	setSelectionAndTextBox("Point_Radius_Min-Input", project.pointMapFileSettings.radiusMin);
	setSelectionAndTextBox("Point_Radius_Max-Input", project.pointMapFileSettings.radiusMax);
	setSelectionAndTextBox("Point_StrokeColor-Input", project.pointMapFileSettings.strokeColor);
	setCheckBox("Point_FlipLgClr-CB", project.pointMapFileSettings.ifFlipColor);
	setSelectionAndTextBox("Point_StrokeWidth-Input", project.pointMapFileSettings.strokeWidth);
	setSelectionAndTextBox("Point_LegendDP-Input", project.pointMapFileSettings.decimalPlaces);
	setSelectionAndTextBox("Point_ManualBreak-Input", project.pointMapFileSettings.breakInput);
	setSelectionAndTextBox("Point_LegendTitle-Input", project.pointMapFileSettings.legendTitle);
//	setCheckBox("Point_DisplayAsAbs-CB", project.pointMapFileSettings.isDisplayedAsAbs);
}

function updateFlowMapSettingsFromProjectFile(project){
	flowMapSettings.origin = project.flowMapFileSettings.origin;
	flowMapSettings.destination = project.flowMapFileSettings.destination;
	flowMapSettings.volume = project.flowMapFileSettings.volume;
	flowMapSettings.flowStyleName = project.flowMapFileSettings.flowStyleName; // Name of flow style.
	flowMapSettings.cfMethod = project.flowMapFileSettings.cfMethod;
	flowMapSettings.clrScheme = project.flowMapFileSettings.clrScheme;
	flowMapSettings.minCustomColor = project.flowMapFileSettings.minCustomColor;
	flowMapSettings.maxCustomColor = project.flowMapFileSettings.maxCustomColor;
	flowMapSettings.fillOpacity = project.flowMapFileSettings.fillOpacity; 
	flowMapSettings.ifFlipColor = project.flowMapFileSettings.ifFlipColor;
	flowMapSettings.decimalPlaces = project.flowMapFileSettings.decimalPlaces;
	flowMapSettings.clsNum = project.flowMapFileSettings.clsNum;
	flowMapSettings.numTopFlows = project.flowMapFileSettings.numTopFlows;
	flowMapSettings.breakInput = project.flowMapFileSettings.breakInput;
	flowMapSettings.widthMax = project.flowMapFileSettings.widthMax;
	flowMapSettings.widthMin = project.flowMapFileSettings.widthMin;
	flowMapSettings.strokeWidth = project.flowMapFileSettings.strokeWidth;
	flowMapSettings.strokeColor = project.flowMapFileSettings.strokeColor;
	flowMapSettings.legendTitle = project.flowMapFileSettings.legendTitle;
//	flowMapSettings.isDisplayedAsAbs = project.flowMapFileSettings.isDisplayedAsAbs; // Display as absolute (it is temporarily hidden from the interface).
	
	flowMapSettings.flowStyle = chooseFlowStyle();
}

function updateFlowMapInterfaceFromProjectFile(project){
	if(project.flowData){
		updateSelectionBoxOptions("Flow_SourceID-Select", Object.keys(project.flowData[0]));
		updateSelectionBoxOptions("Flow_TargetID-Select", Object.keys(project.flowData[0]));
		updateSelectionBoxOptions("Flow_Volume-Select", Object.keys(project.flowData[0]));
	}
	setSelectionAndTextBox("Flow_SourceID-Select", project.flowMapFileSettings.origin);
	setSelectionAndTextBox("Flow_TargetID-Select", project.flowMapFileSettings.destination);
	setSelectionAndTextBox("Flow_Volume-Select", project.flowMapFileSettings.volume);
	setSelectionAndTextBox("Flow_Classification-Select", project.flowMapFileSettings.cfMethod);
	$("#Flow_Classification-Select").change();
	setSelectionAndTextBox("Flow_Style-Select", project.flowMapFileSettings.flowStyleName);
	setSelectionAndTextBox("Flow_ColorScheme-Select", project.flowMapFileSettings.clrScheme);
	setSelectionAndTextBox("Flow_MinCustomColor-Input", project.flowMapFileSettings.minCustomColor);
	setSelectionAndTextBox("Flow_MaxCustomColor-Input", project.flowMapFileSettings.maxCustomColor);
	setSelectionAndTextBox("Flow_FillOpacity-Input", project.flowMapFileSettings.fillOpacity);
	setCheckBox("Flow_FlipLgClr-CB", project.flowMapFileSettings.ifFlipColor);
	setSelectionAndTextBox("Flow_LegendDP-Input", project.flowMapFileSettings.decimalPlaces);
	setSelectionAndTextBox("Flow_ClassNum-Input", project.flowMapFileSettings.clsNum);
	setSelectionAndTextBox("Flow_TopFlowFromAllFlows-Input", project.flowMapFileSettings.numTopFlows);
	setSelectionAndTextBox("Flow_ManualBreak-Input", project.flowMapFileSettings.breakInput);
	setSelectionAndTextBox("Flow_FlowWidth_Max-Input", project.flowMapFileSettings.widthMax);
	setSelectionAndTextBox("Flow_FlowWidth_Min-Input", project.flowMapFileSettings.widthMin);
	setSelectionAndTextBox("Flow_StrokeWidth-Input", project.flowMapFileSettings.strokeWidth);
	setSelectionAndTextBox("Flow_StrokeColor-Input", project.flowMapFileSettings.strokeColor);
	setSelectionAndTextBox("Flow_LegendTitle-Input", project.flowMapFileSettings.legendTitle);
//	setCheckBox("Flow_DisplayAsAbs-CB", project.flowMapFileSettings.isDisplayedAsAbs);
}

function loadProject(jsonStr){
	var project = JSON.parse(jsonStr);
	updateBaseMapSettingsFromProjectFile(project);
	updateBaseMapInterfaceFromProjectFile(project);
	updatePointMapSettingsFromProjectFile(project);
	updatePointMapInterfaceFromProjectFile(project);
	updateFlowMapSettingsFromProjectFile(project);
	updateFlowMapInterfaceFromProjectFile(project);
	switchBaseMapLayer(baseMapSettings.baseMap);
	switchMapProjection(baseMapSettings.projection);
	
	if('refData' in project){
		refData = project.refData;
		$('.BaseMap_Reference-Rows').css("display", "table-row");
		drawReference();
	}
	
	if('selfDesignedBaseMapData' in project){
		baseMapData = project.selfDesignedBaseMapData;
		// Draw the base map polygons (not including assigning the styles to the map).
		drawChoroplethMapPolygons(baseMapData);
		baseMapSettings.hasNewData = true;
		if('choroplethMapData' in project){
			CPMData = project.choroplethMapData;
			pointMapSettings.hasNewData = true;
			makeChoroplethMap();
		}
	}
	
	if('pointData' in project){
		pointData = project.pointData;
		if('flowData' in project){
			flowData = project.flowData;
			flowMapSettings.hasNewData = true;
		}
		makePointAndFlowMap();
	}
}