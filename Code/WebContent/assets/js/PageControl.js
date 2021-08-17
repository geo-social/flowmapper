var getCanvas;
$(document).ready(function(){
	// draw div
//    var legendDiv = $("#Legend");
//    $('document').ready(function(){
//	      html2canvas(legendDiv, {
//	        onrendered: function (canvas) {
//	          $("#previewImage").append(canvas);
//	          getCanvas = canvas;
//	        }
//	      });
//    });
	
	$('#File-Dropdown').on('click', function (e) {
		if($(e.target).parents('#File-Menu').length > 0){
			return; 
		}
		
		if(!$('#File-Menu').hasClass('open') ){
			$('#File-Menu').toggleClass('open');
		}else{
			$('#File-Menu').removeClass('open');
		}
	});
	
	$('body, a').on('click', function (e) {
	    if (!$('#File-Dropdown').is(e.target) 
	        && $('#File-Dropdown').has(e.target).length === 0 
	       // && $('.show').has(e.target).length === 0 
	    ) {
	        $('#File-Menu').removeClass('open');
	    }
	    
	    if (!$('#View-Dropdown').is(e.target) 
		        && $('#View-Dropdown').has(e.target).length === 0 
		       // && $('.show').has(e.target).length === 0 
		    ) {
		        $('#View-Menu').removeClass('open');
		    }
	});
	
	$('#View-Dropdown').on('click', function (e) {
		if($(e.target).parents('#View-Menu').length > 0){
			return; 
		}
		
		if(!$('#View-Menu').hasClass('open') ){
			$('#View-Menu').toggleClass('open');
		}else{
			$('#View-Menu').removeClass('open');
		}
	});
	
      $("#Online_BaseMap-Select").change(function(){
    	  baseMapSettings.baseMap = $('#Online_BaseMap-Select').val();
    	  switchBaseMapLayer(baseMapSettings.baseMap);
    	  if(baseMapSettings.baseMap == "stamenLite" || baseMapSettings.baseMap == "osm" || baseMapSettings.baseMap == "esriTopographic"){
    		  $('#DisplayMapReferences-Div').css("display", "none");
    	  }else{
    		  $('#DisplayMapReferences-Div').css("display", "inline");
    	  }
    });
      
      $("#DisplayMapReference-CB").change(function(){
    	  baseMapSettings.ifDisplayReferences = $('#Online_BaseMap-Select').is(":checked");
    	  if($('#DisplayMapReference-CB').is(":checked")){
    		  map.addLayer(referenceLayer);
    	  }else{
    		  map.removeLayer(referenceLayer);
    	  }
      });
      
      $("#UploadReference-CB").change(function(){
    	  baseMapSettings.ifUploadReferences = $('#Online_BaseMap-Select').is(":checked");
    	  if($(this).is(":checked")){
    		  $('.UploadReference-Rows').css("display", "table-row");
    		  if(refData){
    			  $('.BaseMap_Reference-Rows').css("display", "table-row");
    			  drawReference();
    		  }
    	  }else{
    		  removeReference();
    		  $('.UploadReference-Rows').css("display", "none");
    		  $('.BaseMap_Reference-Rows').css("display", "none");
    	  }
      });
      
      $(".CPM_StyleSettings").change(function(){
		  if(document.getElementById("CPM_Classification-Select").value != "ManualBreak"){
			  $("#CPM_ClassNum-Row").css("display","table-row");
			  $(".CMP_MBStRows").css("display","none");
    	  }else{
    		  $("#CPM_ClassNum-Row").css("display","none");
			  $(".CMP_MBStRows").css("display","table-row");
    	  }
      });
      
      $("#Flow_Style-Select").change(function(){
    	  if(document.getElementById("Flow_Style-Select").value == "straight"){
    		  setPathstyle_straight();
    	  }
          else if(document.getElementById("Flow_Style-Select").value == "arc"){
        	  setPathstyle_Arc();
          }
          else if(document.getElementById("Flow_Style-Select").value == "straightWithHalfArrow"){
        	  setPathstyle_straightwitharrow();
          }
          else if(document.getElementById("Flow_Style-Select").value == "curve"){
        	  setPathstyle_curve();
          }
    });
      
      $(".StrokeWidthControl").change(function(){
          $("#Flow_FlowWidth_Max-Input").change(function(){
          	$("#Flow_FlowWidth_Min-Input").attr({
          	       "max" : +document.getElementById("Flow_FlowWidth_Max-Input").value - 2
          	    });
          	});
          
          $("#Flow_FlowWidth_Min-Input").change(function(){
          	$("#Flow_FlowWidth_Max-Input").attr({
          	       "min" : +document.getElementById("Flow_FlowWidth_Min-Input").value + 2
          	    });
          	}); 
      });
      
      $("#Flow_Stroke-CB").change(function(){
    	  if($("#Flow_Stroke-CB").is(":checked")) {
    		  $("#Flow_StrokeWidth-Row").css("display","table-row");
    		}
	      	else{
	      		$("#Flow_StrokeWidth-Row").css("display","none");
	      	}
      });
      
      $("#Flow_TopFlowFromAllFlows-Input").change(function(){
    	  if(+document.getElementById("Flow_TopFlowFromAllFlows-Input").value > maxNumOfTopLinks){
    		  alertMaxTopFlows();
    		  document.getElementById("Flow_TopFlowFromAllFlows-Input").value = maxNumOfTopLinks;
    	  }
      });
      
      $(".PointRadiusControl").change(function(){
          $("#Point_Radius_Max-Input").change(function(){
          	$("#Point_Radius_Min-Input").attr({
          	       "max" : +document.getElementById("Point_Radius_Max-Input").value - 2
          	    });
          	});
          
          $("#Point_Radius_Min-Input").change(function(){
          	$("#Point_Radius_Max-Input").attr({
          	       "min" : +document.getElementById("Point_Radius_Min-Input").value + 2
          	    });
          	}); 
          
          if(flowData && flowWidthScale)
        	  flowWidthScale.range(getFlowWidthRange());
      });
      
      $('#CPM_Classification-Select').change(function(e){
    	  if($('#CPM_Classification-Select').val() == "ManualBreak" || $('#CPM_Classification-Select').val() == "Proportional"){
    		  $(".CPM_ClassNum-Rows").css("display","none");
    	  }else{
    		  $(".CPM_ClassNum-Rows").css("display","table-row");
    	  }
      });
      
      $("#Point_Classification-Select").change(function(e){
    	  if(document.getElementById("Point_Classification-Select").value == "ManualBreak" && pointMapSettings.ifMapAttribute){
    		  $(".Point_MBStRows").css("display","table-row");
    	  }else{
			  $(".Point_MBStRows").css("display","none");
    	  }
    	  
    	  if($('#Point_Classification-Select').val() == "ManualBreak" || $('#Point_Classification-Select').val() == "Proportional"){
    		  $(".Point_ClassNum-Rows").css("display","none");
    	  }else{
    		  if(pointMapSettings.ifMapAttribute){
    			  $(".Point_ClassNum-Rows").css("display","table-row");
    		  }
    	  }
      });
      
      $('#Flow_Classification-Select').change(function(e){
    	  if($('#Flow_Classification-Select').val() == "ManualBreak"){
    		  $(".Flow_MBStRows").css("display","table-row");
    	  }else{
    		  $(".Flow_MBStRows").css("display","none");
    	  }
    	  
    	  if($('#Flow_Classification-Select').val() == "ManualBreak" || $('#Flow_Classification-Select').val() == "Proportional"){
    		  $(".Flow_ClassNum-Rows").css("display","none");
    	  }else{
    		  $(".Flow_ClassNum-Rows").css("display","table-row");
    	  }
      });
      
      //--------------------------------------Below is for old color scheme choice for classified and unclassified classification------------------------
//	  $("#CPM_Classification-Select").data('oldVal', $("#CPM_Classification-Select").val());	
//      $("#CPM_Classification-Select").change(function(){
//    	  const classifiedColorNameList = ["Yellow-Green-Blue", "Purple-Blue", "Red-Purple",
//    		  "Greys", "Greens", "Reds", 
//    		  "Red-Blue", "Purple-Green", "Purple-Orange"];
//    	  const classifiedColorValueList = ["YlGnBu", "PuBu", "RdPu",
//    		  "Greys", "Greens", "Reds",
//    		  "RdBu", "PRGn", "PuOr"];
//    	  const proportionalColorNameList = ["Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  const proportionalColorValueList = ["Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  var $this = $(this);
//    	  if($this.data('oldVal') != "Linear" &&  $this.val() != "Linear" || $this.data('oldVal') == "Linear" &&  $this.val() == "Linear"){
//    		  $("#CPM_Classification-Select").data('oldVal', $this.val());
//    		  return;
//    	  }
//    	  
//    	  removeOptions("CPM_ColorScheme-Select");
//    	  if(document.getElementById("CPM_Classification-Select").value == "Linear"){
//    		  for(var i = 0; i < proportionalColorNameList.length; i++){
//    			  addOption("CPM_ColorScheme-Select", proportionalColorNameList[i], proportionalColorValueList[i]);
//    		  }
//    	  }else{
//    		  for(var i = 0; i < classifiedColorNameList.length; i++){
//    			  addOption("CPM_ColorScheme-Select", classifiedColorNameList[i], classifiedColorValueList[i]);
//    		  }
//    		  $("#CPM_CustomColor-Row").css("display","none");
//    	  }
//    	  $("#CPM_Classification-Select").data('oldVal', $this.val());
//      });
	  
	  
//      $("#Point_Classification-Select").data('oldVal', $("#Point_Classification-Select").val());	
//      $("#Point_Classification-Select").change(function(){
//    	  const classifiedColorNameList = ["All Black", "Yellow-Green-Blue", "Purple-Blue", "Red-Purple",
//    		  "Greys", "Greens", "Reds", 
//    		  "Red-Blue", "Purple-Green", "Purple-Orange"];
//    	  const classifiedColorValueList = ["Black", "YlGnBu", "PuBu", "RdPu",
//    		  "Greys", "Greens", "Reds",
//    		  "RdBu", "PRGn", "PuOr"];
//    	  const proportionalColorNameList = ["All Black", "Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  const proportionalColorValueList = ["Black", "Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  var $this = $(this);
//    	  if($this.data('oldVal') != "Proportional" &&  $this.val() != "Proportional" || $this.data('oldVal') == "Proportional" &&  $this.val() == "Proportional"){
//    		  $("#Point_Classification-Select").data('oldVal', $this.val());
//    		  return;
//    	  }
//    	  
//    	  removeOptions("Point_ColorScheme-Select");
//    	  if(document.getElementById("Point_Classification-Select").value == "Proportional"){
//    		  for(var i = 0; i < proportionalColorNameList.length; i++){
//    			  addOption("Point_ColorScheme-Select", proportionalColorNameList[i], proportionalColorValueList[i]);
//    		  }
//    	  }else{
//    		  for(var i = 0; i < classifiedColorNameList.length; i++){
//    			  addOption("Point_ColorScheme-Select", classifiedColorNameList[i], classifiedColorValueList[i]);
//    		  }
//    		  $(".Point_CustomColor-Rows").css("display","none");
//    	  }
//    	  $("#Point_Classification-Select").data('oldVal', $this.val());
//      });
      
//      $("#Flow_Classification-Select").data('oldVal', $("#Flow_Classification-Select").val());	
//      $("#Flow_Classification-Select").change(function(){
//    	  const classifiedColorNameList = ["All Black", "Yellow-Green-Blue", "Purple-Blue", "Red-Purple",
//    		  "Greys", "Greens", "Reds", 
//    		  "Red-Blue", "Purple-Green", "Purple-Orange"];
//    	  const classifiedColorValueList = ["Black", "YlGnBu", "PuBu", "RdPu",
//    		  "Greys", "Greens", "Reds",
//    		  "RdBu", "PRGn", "PuOr"];
//    	  const proportionalColorNameList = ["All Black", "Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  const proportionalColorValueList = ["Black", "Greys", "Greens", "Reds", 
//    		  "Blues", "Purples", "Custom"];
//    	  
//    	  if(document.getElementById("Flow_Classification-Select").value != "ManualBreak"){
//    		  if(document.getElementById("Flow_Classification-Select").value != "Proportional")
//    			  $(".Flow_ClsfdStRows").css("display","table-row");
//    		  else
//    			  $(".Flow_ClsfdStRows").css("display","none");
//			  $(".Flow_MBStRows").css("display","none");
//    	  }else{
//    		  $(".Flow_ClsfdStRows").css("display","none");
//			  $(".Flow_MBStRows").css("display","table-row");
//    	  }
//    	  
//    	  var $this = $(this);
//    	  if($this.data('oldVal') != "Proportional" &&  $this.val() != "Proportional" || $this.data('oldVal') == "Proportional" &&  $this.val() == "Proportional"){
//    		  $("#Flow_Classification-Select").data('oldVal', $this.val());
//    		  return;
//    	  }
//    	  
//    	  removeOptions("Flow_ColorScheme-Select");
//    	  if(document.getElementById("Flow_Classification-Select").value == "Proportional"){
//    		  for(var i = 0; i < proportionalColorNameList.length; i++){
//    			  addOption("Flow_ColorScheme-Select", proportionalColorNameList[i], proportionalColorValueList[i]);
//    		  }
//    	  }else{
//    		  for(var i = 0; i < classifiedColorNameList.length; i++){
//    			  addOption("Flow_ColorScheme-Select", classifiedColorNameList[i], classifiedColorValueList[i]);
//    		  }
//    		  $("#Flow_CustomColor-Row").css("display","none");
//    	  }
//    	  $("#Flow_Classification-Select").data('oldVal', $this.val());
//      });
      
//      $("#Flow_Classification-Select").change(function(){
//    	  var method = $(this).val();
//    	  switch(method){
//    	  	case "Proportional":{
//    	  		$(".Point_ProportionalColorOptions").css("display","block");
//    	  		$(".Point_ClassifiedColorOptions").css("display","none");
//    	  		break;
//    	  	};
//    	  	case "ManualBreak":{
//    	  		$(".Point_ProportionalColorOptions").css("display","none");
//    	  		$(".Point_ClassifiedColorOptions").css("display","block");
//    	  		break;
//    	  	};
//    	  }
//      });
      
      $("#CPM_ColorScheme-Select").change(function(){
    	  if(document.getElementById("CPM_ColorScheme-Select").value == "Custom"){
    		  $(".CPM_CustomColor-Rows").css("display","table-row");
    	  }else{
    		  $(".CPM_CustomColor-Rows").css("display","none");
    	  }
      });
      
      $("#Point_ColorScheme-Select").change(function(){
    	  if(document.getElementById("Point_ColorScheme-Select").value == "Custom" && $("#Point_MapAttribute-CB").is(":checked")){
    		  $(".Point_CustomColor-Rows").css("display","table-row");
    	  }else{
    		  $(".Point_CustomColor-Rows").css("display","none");
    	  }
      });

	  $("#Flow_ColorScheme-Select").change(function(){
		  if(document.getElementById("Flow_ColorScheme-Select").value == "Custom"){
    		  $(".Flow_CustomColor-Rows").css("display","table-row");
    	  }else{
    		  $(".Flow_CustomColor-Rows").css("display","none");
    	  }
	  });
      
//      $(".Flow_StyleSettings").change(function(){
//    	  // Prevent the typing value exceeds the bound.
//          var inputNum = parseInt($(this).val());
//          var maxNum = parseInt($(this).attr('max'));
//          var minNum = parseInt($(this).attr('min'));
//          if(inputNum > maxNum)
//        	  $(this).val(maxNum);
//          else if(inputNum < minNum)
//        	  $(this).val(minNum);
////    	  resetColorSchemeAndLegendForFlows();
//      });
      
      $("#Flow_DisplayAsAbs-CB").change(function(){
    	  if($("#Flow_DisplayAsAbs-CB").is(":checked")){
    		  if(document.getElementById("Flow_ColorScheme-Select").value != "black" && document.getElementById("Flow_Classification-Select").value != "Proportional"){
	    			popErrorWindow('Change flow map does not support classified method currently. Please try proportional classification method.');
	    			return;
	    		}
    	  }
      });
      
      $("#Flow_DisplayAsAbs-CB").change(function(){
    	  if(document.getElementById("Flow_Classification-Select").value != "Proportional"){
    		  $("#Flow_NumOfClasses-Row").css("display","table-row");
    	  }else{
    		  $("#Flow_NumOfClasses-Row").css("display","none");
    	  }
      });
      
      $("#AddTitle-CB").change(function(){
    	  if($("#AddTitle-CB").is(":checked")){
    		  $(".MapTitle-Row").css("display","table-row");
    		  drawTitle();
    	  }else{
    		  $(".MapTitle-Row").css("display","none");
    		  removeTitle();
    	  }
      });
      
      $("#AddNorthArrow-CB").change(function(){
    	  if($("#AddNorthArrow-CB").is(":checked")){
    		  addNorthArrow();
    	  }
    	  else{
    		  removeNorthArrow();
    	  }
      });
      
      $("#AddProjectionLabel-CB").change(function(){
    	  if($("#AddProjectionLabel-CB").is(":checked")){
    		  addProjectionLabel();
    	  }
    	  else{
    		  removeProjectionLabel();
    	  }
      });
      
      $(".Point_StyleSettings").change(function(e){
    	// Prevent the typing value exceeds the bound.
    	  var inputNum = parseInt($(this).val());
          var maxNum = parseInt($(this).attr('max'));
          var minNum = parseInt($(this).attr('min'));
          if(inputNum > maxNum)
        	  $(this).val(maxNum);
          else if(inputNum < minNum)
        	  $(this).val(minNum);
//    	  resetColorSchemeAndLegendForPoints();
      });
      
      $('#BaseMap_File-Input').change(function (e) {
      	var reader = new FileReader();
      	var file1 = document.getElementById("BaseMap_File-Input").files[0];
      	reader.readAsText(file1);
      	reader.onload = function(e) {
      		baseMapSettings.areNewFilesLoaded = true;
      	    baseMapData = parsePolygonDataOfChoroplethMap(reader.result);
      	    if(baseMapData){
      	    	baseMapSettings.hasNewData = true;
      	    	drawChoroplethMapPolygons(baseMapData);
      	    }
      	};
      });
      
      $('#CPM_CSV-Input').change(function (e) {
      	var reader = new FileReader();
      	var file1 = document.getElementById("CPM_CSV-Input").files[0];
      	reader.readAsText(file1);
      	reader.onload = function(e) {
      		baseMapSettings.areNewFilesLoaded = true;
      		CPMData = parseCSVDataOfChoroplethMap(reader.result);
      		if(CPMData){
      			$('.CPM_CSV-Row').css("display", "table-row");
      		}else{
      			alertCSVLoadingError();
      		}
      	};
      });

      $('#CPM_BMPK-Select').change(function (e) {
  	    baseMapSettings.areNewFilesLoaded = true;
      });
     
      $('#CPM_CSVPK-Select').change(function (e) {
   	    baseMapSettings.areNewFilesLoaded = true;
      });
      
      $('#Point_File-Input').change(function (e) {
      	var reader = new FileReader();
      	var file1 = document.getElementById("Point_File-Input").files[0];
      	reader.readAsText(file1);
      	reader.onload = function(e) {
      		pointData = parseCSVPointData(reader.result);
      		if(pointData){
      			pointMapSettings.hasNewData = true;
      		}
      	};
      });
      
      $('#Flow_File-Input').change(function (e) {
      	var reader = new FileReader();
      	var file1 = document.getElementById("Flow_File-Input").files[0];
      	reader.readAsText(file1);
      	reader.onload = function(e) {
      		flowData = parseCSVFlowData(reader.result);
      		if(flowData){
      			flowMapSettings.hasNewData = true;
      		}
      	};
      });
      
      $('#BaseMap_Reference-Input').change(function (e) {
      	var reader = new FileReader();
      	var file1 = document.getElementById("BaseMap_Reference-Input").files[0];
      	reader.readAsText(file1);
      	reader.onload = function(e) {
      		refData = parseReferenceJSON(reader.result);
      		if(refData){
      			$('.BaseMap_Reference-Rows').css("display", "table-row");
      		}else{
      			popErrorWindow("Reference file loading failed. Please check your file is usable point JSON and your field inputs are correct.");
      			return;
      		}
      	};
      });
      
      $('.RefFields').change(function (e) {
    	  drawReference();
      });
      
      $('#SpatialAnalysis_File-Input').change(function (e) {
    	  var reader = new FileReader();
    	  var file1 = document.getElementById("SpatialAnalysis_File-Input").files[0];
    	  var fileName = document.getElementById("SpatialAnalysis_File-Input").files[0].name;
    	  var fileType = fileName.split('.').pop();
    	  reader.readAsText(file1);
    	  reader.onload = function(e) {
    		  sendToSl("SpatialAnalysis", "statistics", reader.result, fileType, "text", "post");
    	  }
      });
      
      $('#TestServerConnection-Btn').click(function (e) {
    	  // Servlet name, tool name, data sent to backend, data type, allowed receive type, send type
		  sendToSl("SpatialAnalysis", "normalizeFlows", "", "string", "text", "post");
      });
      
      var originIdField, destinationIdField, volumeField_Flows, IDField_Points, XField_Points, YField_Points, volumeField_Points;
      $(".PointAndFlowMapBtns").click(function(){
    	  makePointAndFlowMap();
	  });
      
//      $(".ManualBreak_Help-Btn").click(function(){
////    	  $("#ManualInput-Block").css("display","block");
//    	  magnificPopupWindow("ManualInput-Block", "mfp-zoom-in");
//      });
      
      $("#ManualInput_close-Btn").click(function(){
    	  $("#ManualInput-Block").css("display","none");
      });
      
      $("#CleanChoroplethMap-Btn").click(function(){
    	  g1.selectAll("*").remove();
    	  removeOldLegendGraph(svg_CPMLegend);
      });
      
      $("#CleanPoints-Btn").click(function(){
    	  g2.selectAll("*").remove();
    	  removeOldLegendGraph(svg_PointLegend);
      });
      
      $("#CleanFlows-Btn").click(function(){
    	  g3.selectAll("*").remove();
    	  removeOldLegendGraph(svg_FlowLegend);
      });
      
//      $("#RemoveFlowData-Btn").click(function(){
//    	  flowData = null;
//    	  $("#Flow_File-Input").val('');
//    	  magnificCloseWindow("FlowUnmatched-Block");
//      });
      // Inline popups
      $('.inline-popups').magnificPopup({
        delegate: 'a',
        removalDelay: 500, //delay removal by X to allow out-animation
        callbacks: {
          beforeOpen: function() {
             this.st.mainClass = this.st.el.attr('data-effect');
          }
        },
        midClick: true // allow opening popup on middle mouse click. Always set it to true if you don't provide alternative source.
      });
      
      $('#CPM-CB').click(function (e) {
    	  if(baseMapData == null || baseMapData == undefined){
    		   popErrorWindow("please input your base map file first");
    	       $('#CPM-CB').removeProp('checked');
    	       return false;
    	    }
        });
      
      $('#CPM-CB').change(function (e) {
        	if($("#CPM-CB").is(":checked")) {
        		$("#CPM-Table").css("display","inline-block");
        		$("#CPM_Style-Table").css("display","inline-block");
//        		resetColorSchemeAndLegendForChoroplethMap();
        		}
        	else {
        		$("#CPM-Table").css("display","none");
        		$("#CPM_Style-Table").css("display","none");
        	}
        });
      
//      $('#CMP_LegendShow-CB').change(function (e) {
//      	if($("#CMP_LegendShow-CB").is(":checked")) {
//      		$("#svg_CPMLegend").css("display","block");
//      		}
//      	else {
//      		$("#svg_CPMLegend").css("display","none");
//      	}
//      });
//      
//      $('#Point_LegendShow-CB').change(function (e) {
//        	if($("#Point_LegendShow-CB").is(":checked")) {
//        		$("#svg_PointLegend").css("display","block");
//        		}
//        	else {
//        		$("#svg_PointLegend").css("display","none");
//        	}
//        });
//      
//      $('#Flow_LegendShow-CB').change(function (e) {
//        	if($("#Flow_LegendShow-CB").is(":checked")) {
//        		$("#svg_FlowLegend").css("display","block");
//        		}
//        	else {
//        		$("#svg_FlowLegend").css("display","none");
//        	}
//        });
//      
//      $('#FlowIntegration-CB').change(function (e) {
//    	  if($("#FlowIntegration-CB").is(":checked")) {
//    		  $(".flowIntegration").css("display","table-row");
//    		  $("#Flow_Style-Table").css("display","block");
//    		  }
//	      	else{
//	      		$(".flowIntegration").css("display","none");
//	      		$("#Flow_Style-Table").css("display","none");
//	      	}
//      });
      
      $('#MakeCPM-Btn').click(function (e) {
    	  makeChoroplethMap();
      });
      
      $('#ZoomToExtent-Btn').click(function (e) {
    	  
      });
      
      $('#Export-Btn').click(function (e) {
    	  $("#Export-Block").css("display", "block");
        });
      
      $('#EpBlkClose-Btn').click(function (e) {
    	  $("#Export-Block").css("display", "none");
        });
      
      $('#SaveProject-Btn').click(function (e) {
    	  saveProject();
      });
      
      $('#LoadProject-Btn').click(function (e) {
    	  var file = document.createElement("input");
    	  file.setAttribute("type", "file");
    	  file.setAttribute("id", "Temp-Input");
    	  document.body.appendChild(file);
    	  file.click();
    	  $('#Temp-Input').change(function (e) {
    		  var reader = new FileReader();
        	  reader.readAsText(file.files[0]);
        	  reader.onload = function(e) {
        		  loadProject(reader.result);
        	  };
	      });
    	  document.body.removeChild(file);
      })
      
      $('#ExportMap-Btn').click(function (e) {
    	  switch($('#ExportFormat-Select').val()){
    	  	case "png":{
    	  		exportPNG();
    	  		break;
    	  	}
    	  	case "svg":{
    	  		var choroplethMapCount = g1.selectAll("path").size();
		    	var pointCount = g1.selectAll("circle").size();
		    	var flowCount = g1.selectAll("path").size();
		    	if(!choroplethMapCount && !pointCount && !flowCount){
		    		popErrorWindow("Error: No map element can be exported!");
		    		return;
		    	}else{
		        	exportSVG(svg_user_painting, "map");
		    	}
		    	  
		    	var ifCPMLegend = svg_CPMLegend.selectAll("g").size() >= 1 ? true : false;
		    	var ifPointLegend = svg_PointLegend.selectAll("g").size() >= 1 ? true : false;
		    	var ifFlowLegend = svg_FlowLegend.selectAll("g").size() >= 1 ? true : false;
		    	  
		    	if(ifCPMLegend){
		    		exportSVG(svg_CPMLegend, "ChoroplethMapLegend");
		    	}
		    	  
		    	if(ifPointLegend){
		    		exportSVG(svg_PointLegend, "PointLegend");  
				}
				
		    	if(ifFlowLegend){
		    		exportSVG(svg_FlowLegend, "FlowLegend");
		    	}
    	  		break;
    	  	}
    	  }
        });
      
      $('#ExportSVG-Btn').click(function (e) {
    	    var choroplethMapCount = g1.selectAll("path").size();
	    	var pointCount = g2.selectAll("circle").size();
	    	var flowCount = g3.selectAll("path").size();
	    	if(!choroplethMapCount && !pointCount && !flowCount){
	    		popErrorWindow("Error: No map element can be exported!");
	    		return;
	    	}else{
	        	exportSVG(svg_user_painting, "map");
	    	}
	    	  
	    	var ifCPMLegend = svg_CPMLegend.selectAll("g").size() >= 1 ? true : false;
	    	var ifPointLegend = svg_PointLegend.selectAll("g").size() >= 1 ? true : false;
	    	var ifFlowLegend = svg_FlowLegend.selectAll("g").size() >= 1 ? true : false;
	    	  
	    	if(ifCPMLegend){
	    		exportSVG(svg_CPMLegend, "ChoroplethMapLegend");
	    	}
	    	  
	    	if(ifPointLegend){
	    		exportSVG(svg_PointLegend, "PointLegend");  
			}
			
	    	if(ifFlowLegend){
	    		exportSVG(svg_FlowLegend, "FlowLegend");
	    	}
      });
      
      $('#ExportPNG-Btn').click(function (e) {
    	  exportPNG();
      });
      
      $('#ExportTIF-Btn').click(function (e) {
    	  exportTIF();
      });
      
      $('#ExportJPG-Btn').click(function (e) {
    	  exportJPG();
      });
      
      $('#MapProjection-Select').change(function (e) {
    	  baseMapSettings.projection = $("#MapProjection-Select").val();
    	  switchMapProjection(baseMapSettings.projection);
      });

      $('#Legend').draggable();
      
      $('#PolygonsToPoints-Input').change(function (e) {
//	      var file = document.createElement("input");
//		  file.setAttribute("type", "file");
//		  file.setAttribute("id", "Temp-Input");
//		  file.setAttribute("accept",".json");
//		  document.body.appendChild(file);
//		  file.click();
//		  $('#Temp-Input').change(function (e) {
//			  var reader = new FileReader();
//	    	  reader.readAsText(file.files[0]);
//	    	  reader.onload = function(e) {
//	    		  generateCentroidsFromJSONToCSV(reader.result);
//	    	  };
//	      });
//		  document.body.removeChild(file);
    	  
    	  var reader = new FileReader();
    	  reader.readAsText(document.getElementById("PolygonsToPoints-Input").files[0]);
    	  reader.onload = function(e) {
    		  generateCentroidsFromJSONToCSV(reader.result);
    	  };
    	  
      });
      
      $('#SideBar-Btn').click(function(e){
    	  if($("#SideBar-Div").css("width") == "0px"){
    		  $("#SideBar-Div").css("width", "259px");
    		  $("#SideBarBtnContainer-Div").css("width", "259px");
    		  $("#SideBar-Btn").html("<");
    		  $(".ol-scale-line").css("left", "269px");
//    		  $("#ScaleBar-Div div").addClass("LeftLimit");
    	  }else{
    		  $("#SideBar-Div").css("min-width", "0px");
    		  $("#SideBar-Div").css("width", "0px");
    		  $("#SideBarBtnContainer-Div").css("min-width", "0px");
    		  $("#SideBarBtnContainer-Div").css("width", "0px");
    		  $("#SideBar-Btn").html(">");
    		  $(".ol-scale-line").css("left", "10px");
//    		  $("#ScaleBar-Div div").removeClass("LeftLimit");
    	  }
      });
      
      $('#Point_MapAttribute-CB').change(function(e){
    	  pointMapSettings.ifMapAttribute = $('#Point_MapAttribute-CB').is(":checked");
    	  if(pointMapSettings.ifMapAttribute){
    		  $('.Point_Attributes-Rows').css("display", "table-row");
    		  $('.PointNoAttr').css("display", "none");
    	  }else{
    		  $('.Point_Attributes-Rows').css("display", "none");
    		  $('.PointNoAttr').css("display", "table-row");
    	  }
    	  
    	  $('#Point_ColorScheme-Select').change();
    	  $("#Point_Classification-Select").change();
      });
      
      $('#CPM_BaseMapOpacity-Input').change(function(e){
    	  baseMapSettings.baseMapOpacity = +$("#CPM_BaseMapOpacity-Input").val();
    	  onlineLayer.setOpacity(baseMapSettings.baseMapOpacity / 100);
    	  referenceLayer.setOpacity(baseMapSettings.baseMapOpacity / 100);
    	  otherTerrainLayer.setOpacity(baseMapSettings.baseMapOpacity / 100);
      });
      
      $("#SkipTutorial-Btn").click(function(e){
    	  magnificCloseWindow("Welcome-Block");
      });
//      
      $("#GetStarted-Btn").click(function(e){
//      	  magnificCloseWindow("Welcome-Block");
    	  magnificPopupWindow("VideoTutorial-Block", 'mfp-zoom-in');
    	  e.stopPropagation();
      });
      
      $("#NormalizeFlows-Btn").click(function(e){
    	  var reader = new FileReader();
    	  reader.readAsText(document.getElementById("NormalizeFlows-Input").files[0]);
    	  reader.onload = function(e) {
    		  if(reader.result){
    			  // Servlet name, tool name, data sent to backend, data type, allowed receive type, send type
    			  sendToSl("SpatialAnalysis", "normalizeFlows", reader.result, "string", "text", "post");
    		  }else{
    			  popErrorWindow("No input data for Normalize Flows!")
    		  }
    	  };
      })
      
      $("#MapTitle-Input").change(function(e){
    	  baseMapSettings.title = document.getElementById("MapTitle-Input").value;
    	  gTitle.select("text").text(baseMapSettings.title);
      });
      
      $(".Tabs-A").mouseover(function(e){
    	  $("#TabHelper-Block")
    	  .css("opacity", 1)
    	  .css("left", ($(this).offset().left + 20) + "px")
          .css("top", ($(this).offset().top + 22) + "px");
    	  
    	  if($(this).attr("id") === "BaseMap-A"){
    		  $("#TabHelper-Block").html("FlowMapper provides base maps produced by ESRI, Stamen and OpenStreetMap with different map projections. " +
    		  "For ESRI base maps you may add reference labels for places.");
    	  }else if($(this).attr("id") === "Regions-A"){
    		  $("#TabHelper-Block").html("Regions choropleth map is NOT required. But regions may support contextualizing of flow patterns with " + 
    		  "regional characteristics such as net-flow ratio, and population density.");
    	  }else if($(this).attr("id") === "Nodes-A"){
    		  $("#TabHelper-Block").html("Nodes are the coordinates of origin and destination locations for flows. " +
    		  "Nodes CSV data must include ID, X (longitude), and Y (latitude) fields and are required to make a flow map. ");
    	  }else if($(this).attr("id") === "Flows-A"){
    		  $("#TabHelper-Block").html("Flow CSV data should include origin, destination and volume columns to make a flow map. " + 
    		  "ID values in origin and destination fields must match ID values in nodes CSV data.");
    	  }
    	  
      });
      
      $(".Tabs-A").mouseout(function(e){
    	  $("#TabHelper-Block")
    	  .css("opacity", 0);
      });
      
      $("#BaseMap_LebelTop-CB").change(function(e){
    	  if($(this).is(":checked"))
    		  gRef.raise();
    	  else{
    		  gRef.lower();
    		  g1.lower();
    	  }
      });
      
      $("#FlowsOnTop-Btn").click(function(e){
    	  g3.raise();
      });
      
      $("#NodesOnTop-Btn").click(function(e){
    	  g2.raise();
      });
});

