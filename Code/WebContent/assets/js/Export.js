function exportPNG(){
	var mapCanvas = document.createElement('canvas');
    var size = map.getSize();
    mapCanvas.width = size[0];
    mapCanvas.height = size[1];
    var mapContext = mapCanvas.getContext('2d');
    Array.prototype.forEach.call(
      document.querySelectorAll('.ol-layer canvas'),
      function (canvas) {
        if (canvas.width > 0) {
          var opacity = canvas.parentNode.style.opacity;
          mapContext.globalAlpha = opacity === '' ? 1 : Number(opacity);
          var transform = canvas.style.transform;
          // Get the transform parameters from the style's transform matrix
          var matrix = transform
            .match(/^matrix\(([^\(]*)\)$/)[1]
            .split(',')
            .map(Number);
          // Apply the transform to the export map context
          CanvasRenderingContext2D.prototype.setTransform.apply(
            mapContext,
            matrix
          );
          mapContext.drawImage(canvas, 0, 0);
        }
      }
    );
    
    var svgs = document.querySelectorAll('svg');
    var xml = new XMLSerializer().serializeToString(svgs[0]);

	// make it base64
	var svg64 = btoa(xml);
	var b64Start = 'data:image/svg+xml;base64,';

	// prepend a "header"
	var image64 = b64Start + svg64;

	// set it as the source of the img element
    drawImage(image64, 0, 0);
    function drawImage(URL, width, height) {
      var img = new Image();
      img.moveX = width;
      img.moveY = height;
      img.crossOrigin = 'Anonymous';
      img.onload = function() {
    	  mapContext.drawImage(img, this.moveX, this.moveY);
		  if (navigator.msSaveBlob) {
 		      // link download attribute does not work on MS browsers
 		      navigator.msSaveBlob(mapCanvas.msToBlob(), 'map.png');
		  } else {
	    	html2canvas($("#Legend")[0]).then((canvas) => {
	    		var legendDiv = $("#Legend");
	    		var mapElem = $("#map");
	    		var offsets = legendDiv.offset();
	    		var top = offsets.top, left = offsets.left;
	    		var margin = (legendDiv.outerWidth(true) - legendDiv.outerWidth()) / 2.0;
			    $("#previewImage").append(canvas);
			    mapContext.drawImage(canvas, left, mapCanvas.height - canvas.height - margin);
			    
			    var link = document.getElementById('MapDownload-A');
			       link.href = mapCanvas.toDataURL();
		    	   link.download = "map.png";
			       link.click();
			       $("#previewImage").empty();
			       
			    html2canvas($("div.ol-scale-line.ol-unselectable")[0]).then((canvas) => {
		    		var scaleDiv = $("#ScaleBar-Div");
		    		var mapElem = $("#map");
		    		var margin = (scaleDiv.outerWidth(true) - scaleDiv.outerWidth()) / 2.0;
				    $("#previewImage").append(canvas);
				    mapContext.drawImage(canvas, 10, mapCanvas.height - 40);
				    var link = document.getElementById('MapDownload-A');
				       link.href = mapCanvas.toDataURL();
			    	   link.download = "map.png";
				       link.click();
				       $("#previewImage").empty();
				});
			});
	    	
			 
		  }
      };
      img.src = URL;
    }
}

function exportTIF(){
	var mapCanvas = document.createElement('canvas');
    var size = map.getSize();
    mapCanvas.width = size[0];
    mapCanvas.height = size[1];
    var mapContext = mapCanvas.getContext('2d');
    Array.prototype.forEach.call(
      document.querySelectorAll('.ol-layer canvas'),
      function (canvas) {
        if (canvas.width > 0) {
          var opacity = canvas.parentNode.style.opacity;
          mapContext.globalAlpha = opacity === '' ? 1 : Number(opacity);
          var transform = canvas.style.transform;
          // Get the transform parameters from the style's transform matrix
          var matrix = transform
            .match(/^matrix\(([^\(]*)\)$/)[1]
            .split(',')
            .map(Number);
          // Apply the transform to the export map context
          CanvasRenderingContext2D.prototype.setTransform.apply(
            mapContext,
            matrix
          );
          mapContext.drawImage(canvas, 0, 0);
        }
      }
    );
    
    var svgs = document.querySelectorAll('svg');
    var xml = new XMLSerializer().serializeToString(svgs[0]);

	    // make it base64
	    var svg64 = btoa(xml);
	    var b64Start = 'data:image/svg+xml;base64,';

	    // prepend a "header"
	    var image64 = b64Start + svg64;

	    // set it as the source of the img element
    drawImage(image64, 0, 0);
    function drawImage(URL, width, height) {
      var img = new Image();
      img.moveX = width;
      img.moveY = height;
      img.crossOrigin = 'Anonymous';
      img.onload = function() {
    	  mapContext.drawImage(img, this.moveX, this.moveY);
		  if (navigator.msSaveBlob) {
 		      // link download attribute does not work on MS browsers
 		      navigator.msSaveBlob(mapCanvas.msToBlob(), 'map.png');
		  } else {
	    	html2canvas($("#Legend")[0]).then((canvas) => {
	    		var legendDiv = $("#Legend");
	    		var mapElem = $("#map");
	    		var offsets = legendDiv.offset();
	    		var top = offsets.top, left = offsets.left;
	    		var margin = (legendDiv.outerWidth(true) - legendDiv.outerWidth()) / 2.0;
			    $("#previewImage").append(canvas);
			    mapContext.drawImage(canvas, left, mapCanvas.height - canvas.height - margin);
			    html2canvas($("div.ol-scale-line.ol-unselectable")[0]).then((canvas) => {
		    		var scaleDiv = $("#ScaleBar-Div");
		    		var mapElem = $("#map");
		    		var margin = (scaleDiv.outerWidth(true) - scaleDiv.outerWidth()) / 2.0;
				    $("#previewImage").append(canvas);
				    mapContext.drawImage(canvas, 10, mapCanvas.height - 40);
				    var link = document.getElementById('MapDownload-A');
				       link.href = mapCanvas.toDataURL();
			    	   link.download = "map.tif";
				       link.click();
				       $("#previewImage").empty();
				});
			});
		  }
      };
      img.src = URL;
    }
}

function exportJPG(){
	var mapCanvas = document.createElement('canvas');
    var size = map.getSize();
    mapCanvas.width = size[0];
    mapCanvas.height = size[1];
    var mapContext = mapCanvas.getContext('2d');
    Array.prototype.forEach.call(
      document.querySelectorAll('.ol-layer canvas'),
      function (canvas) {
        if (canvas.width > 0) {
          var opacity = canvas.parentNode.style.opacity;
          mapContext.globalAlpha = opacity === '' ? 1 : Number(opacity);
          var transform = canvas.style.transform;
          // Get the transform parameters from the style's transform matrix
          var matrix = transform
            .match(/^matrix\(([^\(]*)\)$/)[1]
            .split(',')
            .map(Number);
          // Apply the transform to the export map context
          CanvasRenderingContext2D.prototype.setTransform.apply(
            mapContext,
            matrix
          );
          mapContext.drawImage(canvas, 0, 0);
        }
      }
    );
    
    var svgs = document.querySelectorAll('svg');
    var xml = new XMLSerializer().serializeToString(svgs[0]);

	    // make it base64
	    var svg64 = btoa(xml);
	    var b64Start = 'data:image/svg+xml;base64,';

	    // prepend a "header"
	    var image64 = b64Start + svg64;

	    // set it as the source of the img element
    drawImage(image64, 0, 0);
    function drawImage(URL, width, height) {
      var img = new Image();
      img.moveX = width;
      img.moveY = height;
      img.crossOrigin = 'Anonymous';
      img.onload = function() {
    	  mapContext.drawImage(img, this.moveX, this.moveY);
		  if (navigator.msSaveBlob) {
 		      // link download attribute does not work on MS browsers
 		      navigator.msSaveBlob(mapCanvas.msToBlob(), 'map.png');
		  } else {
	    	html2canvas($("#Legend")[0]).then((canvas) => {
	    		var legendDiv = $("#Legend");
	    		var mapElem = $("#map");
	    		var offsets = legendDiv.offset();
	    		var top = offsets.top, left = offsets.left;
	    		var margin = (legendDiv.outerWidth(true) - legendDiv.outerWidth()) / 2.0;
			    $("#previewImage").append(canvas);
			    mapContext.drawImage(canvas, left, mapCanvas.height - canvas.height - margin);
			    html2canvas($("div.ol-scale-line.ol-unselectable")[0]).then((canvas) => {
		    		var scaleDiv = $("#ScaleBar-Div");
		    		var mapElem = $("#map");
		    		var margin = (scaleDiv.outerWidth(true) - scaleDiv.outerWidth()) / 2.0;
				    $("#previewImage").append(canvas);
				    mapContext.drawImage(canvas, 10, mapCanvas.height - 40);
				    var link = document.getElementById('MapDownload-A');
				       link.href = mapCanvas.toDataURL();
			    	   link.download = "map.jpg";
				       link.click();
				       $("#previewImage").empty();
				});
			});
		  }
      };
      img.src = URL;
    }
}

function exportSVG(epSVG, exportName){
	var html = epSVG
	   .attr("title", "svg_title")
	   .attr("version", 1.1)
	   .attr("xmlns", "http://www.w3.org/2000/svg")
	   .node().outerHTML;
	
	var link = document.createElement("a");
	link.setAttribute("href-lang", "image/svg+xml");
	link.setAttribute("href", "data:image/svg+xml;base64,\n" + btoa(unescape(encodeURIComponent(html))));
	link.setAttribute("download", exportName + ".svg");
	
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
}
