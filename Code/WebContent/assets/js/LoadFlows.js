function parseCSVFlowData(csvData){	
	var flowData = d3.csvParse(csvData);
	var keyNames = Object.keys(flowData[0]);
	updateSelectionBoxOptions("Flow_Volume-Select", keyNames);
	updateSelectionBoxOptions("Flow_SourceID-Select", keyNames);
	updateSelectionBoxOptions("Flow_TargetID-Select", keyNames);
	
	return flowData;
}


function calculateTopLinks(topNum, volumeList, volumeList_original, originList, destinationList){
	// iterate through the list, to pick the top flows
	// sort the data to make sure large flows are on top of small flows
	var topLinks = [];
	var topIdList = [];
	while(topVolumeList.length < topNum){
		var max, tempMax = Number.MIN_SAFE_INTEGER, tempMaxId = 0;
		if(topVolumeList.length == 0) {max = Number.MAX_SAFE_INTEGER;}
		else {max = Math.abs(topVolumeList[topVolumeList.length - 1]); tempMaxId = topVolumeList.length - 1;}
		for(var i = 0; i < volumeList.length; i++){
			if(volumeList[i] <= max && volumeList[i] > tempMax) {
				if(!topIdList.includes(i) && originList[i] != destinationList[i]){
					tempMax = volumeList[i];
					tempMaxId = i;
				}
			}
		}
		
		topVolumeList.push(volumeList_original[tempMaxId]);
		topIdList.push(tempMaxId);
		//pick links by origin or set links by origin as empty
		var links = linksByOrigin[originList[tempMaxId]] || (linksByOrigin[originList[tempMaxId]] = []);
		//create the links by inserting it in descending order, for the convenience of showing the top flows
		links.push({source: originList[tempMaxId], target: destinationList[tempMaxId], volume: volumeList_original[tempMaxId]});
		countByNodeID[originList[tempMaxId]] = (countByNodeID[originList[tempMaxId]] || 0) + 1;
		countByNodeID[destinationList[tempMaxId]] = (countByNodeID[destinationList[tempMaxId]] || 0) + 1;

		topLinks.unshift({source: originList[tempMaxId], target: destinationList[tempMaxId], volume: volumeList_original[tempMaxId]});
	}
	return topLinks;
}

function filterNodes(nodes, IDField, XField, YField, volumeField_Points){
	return nodes.filter(function(node) {
		if (node[volumeField_Points] && (!flowData || flowData && countByNodeID[node[IDField]])) {
			var location = [+node[XField], +node[YField]];
			// initialize the node location list
			locationByNodeID[node[IDField]] = location;

			// initialize the position list by project the location variables
			positions.push(location);
			// initialize the point size list by recalling data from file
			if(node[volumeField_Points]){
				volumeByNodeID[node[IDField]] = +node[volumeField_Points];
				nodesizeattribute.push(+node[volumeField_Points]);
			}
//			else{
//				volumeByNodeID[node[IDField]] = null;
//				nodesizeattribute.push(null);
//			}
			if(pointMapSettings.volume === "In-flow"){
				nodeFlowAttributeArr.push(inflowByNodeID[node[IDField]]);
			}else if(pointMapSettings.volume === "Out-flow"){
				nodeFlowAttributeArr.push(outflowByNodeID[node[IDField]]);
			}else if(pointMapSettings.volume === "Gross-flow"){
				nodeFlowAttributeArr.push(inflowByNodeID[node[IDField]] + outflowByNodeID[node[IDField]]);
			}else if(pointMapSettings.volume === "Net-flow"){
				nodeFlowAttributeArr.push(inflowByNodeID[node[IDField]] - outflowByNodeID[node[IDField]]);
			}else if(pointMapSettings.volume === "Gross-flow ratio"){
				nodeFlowAttributeArr.push((inflowByNodeID[node[IDField]] - outflowByNodeID[node[IDField]]) / (inflowByNodeID[node[IDField]] + outflowByNodeID[node[IDField]]));
			}else {
				nodeFlowAttributeArr = [];
			}
			
			return true;
		};
	});
}
