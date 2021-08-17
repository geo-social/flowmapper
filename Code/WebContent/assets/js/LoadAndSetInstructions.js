var helpXML;
loadHelpXML()
function loadHelpXML(){
	// Load XML by HTTP get.
	var request = new XMLHttpRequest();
	request.open("GET", "./assets/xml/instructions.xml", false);
	request.send();
	helpXML = request.responseXML;
}

function setInstructionBox(group, tabName, rowName){
	// Set HTML content by using the XML.
	var help = helpXML.getElementsByTagName(group);
	for(var i = 0; i < help.length; i++) {
		var tab = help[i].getElementsByTagName(tabName);
		if(tab.length != 1){
			popErrorWindow("Unable to find instructions for the tab.");
			return;
		}
		for(var j = 0; j < tab.length; j++){
			if(tab[j].getElementsByTagName(rowName).length != 1 || tab[j].getElementsByTagName(rowName)[0].children.length != 2){
				popErrorWindow("Unable to find instruction for the parameter.");
				return;
			}
			var head = tab[j].getElementsByTagName(rowName)[0].children[0].textContent;
			var content = tab[j].getElementsByTagName(rowName)[0].children[1].textContent;
			document.getElementById("Instructions-H").innerHTML = head;
			document.getElementById("Instructions-P").innerHTML = content;
		}
	}
	magnificPopupWindow("Instructions-Block", "mfp-zoom-in");
}

$(document).ready(function(){
	$('.Help-Btn').on('click', function (e) {
		var id = $(this).attr('id');
		if(id.split("_").length < 2 || id.split("_")[1].split("Instruction-Btn") < 2){
			popErrorWindow("Errors in loading help window.");
			return;
		}
		var type = id.split("_")[1].split("Instruction-Btn")[0];
		if($(this).hasClass('BaseMap')){
			setInstructionBox('help', 'baseMapTab', type);
		}else if($(this).hasClass('Regions')){
			setInstructionBox('help', 'regions', type);
		}else if($(this).hasClass('Nodes')){
			setInstructionBox('help', 'nodes', type);
		}else if($(this).hasClass('Flows')){
			setInstructionBox('help', 'flows', type);
		}
	});
});