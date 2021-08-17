function popErrorWindow(message){
	$("#ErrorMessage-P").html(message);
	magnificPopupWindow("Error-Block", 'mfp-zoom-in');
}

function alertFieldInputError(fieldName){
	popErrorWindow("Error: please make sure you have chosen the correct " + fieldName + "!");
}

function alertMaxNumOfFlowError(flowNum){
	popErrorWindow("Error: You data only contains " + flowNum + " flows. You can only show "+ flowNum + " flows in maximum.");
}

function alertCSVLoadingError(){
	popErrorWindow("CSV loading failed.");
}

function alertManualBreakInputError(){
	popErrorWindow("Manual break setting can not be empty.");
}

function alertMaxTopFlows(){
	popErrorWindow("The maximum number of flow is " + maxNumOfTopLinks + ".");
}

function logProjectLoading(id){
	console.log("Project loading error: element ID: "+ id + " can not be found.");
}

function checkFieldInput(checkedData, fieldName, fieldValue){
	if(checkedData.length <= 0){
		alert("You data have no record. Please check your data.");
		return false;
	}
	  
	if(!Object.keys(checkedData[0]).includes(fieldValue)) {
		alertFieldInputError(fieldName);
		return false;
    }
	return true;
}

function checkLegendInput(legendId, legendName){
	var legendValue = document.getElementById(legendId).value;
	if(legendValue.charAt(0) == ' '){
		alert(legendName + " legend title can not start with a space!");
		return false;
	}
	return true;
}

function checkChangeMap(){
	if($("#Flow_DisplayAsAbs-CB").is(":checked")){
		if(document.getElementById("Flow_ColorScheme-Select").value != "black" && document.getElementById("Flow_Classification-Select").value != "Proportional"){
			alert('Change flow map does not support classified method currently. Please try proportional classification method.');
  			$("#Flow_DisplayAsAbs-CB").prop('checked', false);
  			return false;
  		}
	}
	return true;
}