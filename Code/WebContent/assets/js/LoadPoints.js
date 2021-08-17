function parseCSVPointData(csvData){
	var nodes = d3.csvParse(csvData);
	var keyNames = Object.keys(nodes[0]);
	
	// Clone and push no attribute to the end.
	updateSelectionBoxOptions("Point_Volume-Select", keyNames);
	updateSelectionBoxOptions("Point_ID-Select", keyNames);
	updateSelectionBoxOptions("Point_X-Select", keyNames);
	updateSelectionBoxOptions("Point_Y-Select", keyNames);
//	updateSelectionBoxOptions("Point_Volume-Select", "In-flow");
//	updateSelectionBoxOptions("Point_Volume-Select", "Out-flow");
//	updateSelectionBoxOptions("Point_Volume-Select", "Net-flow");
//	updateSelectionBoxOptions("Point_Volume-Select", "Gross-flow");
//	updateSelectionBoxOptions("Point_Volume-Select", "Net-flow ratio");

	return nodes;
}

