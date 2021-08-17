function downloadCSV(csvString, fileName){
	// Distinguish between geoJSON and topoJSON
	var parsedInput = d3.csvParse(csvString);
	var records = parsedInput;
	var attributes = parsedInput.columns;
	
	// Hard copy the input data.
    var rows = [];
    // Add the first row
    var firstRow = [];
    attributes.forEach(function(key){
    	firstRow.push(key);
    });
    rows.push(firstRow);
    
    records.forEach(function(record){
		var newRow = [];
		for (let attr of Object.values(attributes)) {
			newRow.push(record[attr]);
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
        navigator.msSaveBlob(blob, fileName + ".csv");
    } else {
        var link = document.getElementById('MapDownload-A');
        if (link.download !== undefined) { 
        	// feature detection
            // Browsers that support HTML5 download attribute
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download",  fileName + ".csv");
            link.style.visibility = 'hidden';
            link.click();
        }
    }
}

function sendToSl(slName, toolName, sentData, dataType, receiveType, sendType)
{
	var servletConnection = $.ajax({
		type: sendType,
		data:{
			sentData: sentData, type: dataType, toolName: toolName
		},
		url: slName,
		//!!The type of data that back from the server
		dataType: receiveType,
		success: function(result, textStatus, request){
			var fileName = "modularityflows";
			downloadCSV(result, fileName);
		},
		error: function (xhr, ajaxOptions, thrownError) {
			popErrorWindow("Normalize failed! Please make sure your file only contains three columns.");
	    }
	});
}