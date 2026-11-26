"""Project-file schema extracted from the FlowMapper sources.

GENERATED FILE - do not edit by hand. Regenerate with::

    python -m devtools.gen_schema

Each settings block maps a saved key to the interface element it is restored
into (``element``), the element type (``kind``) and its out-of-the-box value in
``index.html`` (``default``).
"""

SOURCE_HASH = 'bff839dc0327dac4'

SCHEMA = {
    "onlineBaseMapSettings": {
        "baseMap": {
            "element": "Online_BaseMap-Select",
            "default": "esriLightGray",
            "kind": "select",
            "options": [
                "esriLightGray",
                "esriDarkGray",
                "osm",
                "esriWorldImaginary",
                "esriWorldPhysical",
                "esriTerrain",
                "esriTopographic"
            ]
        },
        "projection": {
            "element": "MapProjection-Select",
            "default": "abEqAreaUS",
            "kind": "select",
            "options": [
                "abEqAreaUS",
                "laeaNA",
                "lccCanada",
                "abEqAreaAk",
                "abEqAreaEu",
                "laeaEurope",
                "ukBNG",
                "lccTurkey",
                "abEqAreaME",
                "abEqAreaRu",
                "abEqAreaCn",
                "abEqAreaIn",
                "abEqAreaAfc",
                "abEqAreaAs",
                "abEqAreaSthAm",
                "laeaArctic",
                "psAntarctic",
                "eqEarth",
                "robin",
                "moll",
                "gall",
                "webMct"
            ]
        },
        "ifDisplayReferences": {
            "element": "DisplayMapReference-CB",
            "default": False,
            "kind": "checkbox"
        },
        "baseMapOpacity": {
            "element": "CPM_BaseMapOpacity-Input",
            "default": 100,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "ifAddTitle": {
            "element": "AddTitle-CB",
            "default": False,
            "kind": "checkbox"
        },
        "title": {
            "element": "MapTitle-Input",
            "default": "Map Title",
            "kind": "text"
        },
        "ifAddNorthArrow": {
            "element": "AddNorthArrow-CB",
            "default": False,
            "kind": "checkbox"
        },
        "ifAddProjectionLabel": {
            "element": "AddProjectionLabel-CB",
            "default": False,
            "kind": "checkbox"
        },
        "ifUploadReferences": {
            "element": "UploadReference-CB",
            "default": False,
            "kind": "checkbox"
        },
        "description": {
            "element": "MapDescription-Input",
            "default": "Map Description",
            "kind": "text"
        },
        "ifAddDescription": {
            "element": "AddDescription-CB",
            "default": False,
            "kind": "checkbox"
        },
        "titleColor": {
            "element": "BaseMap_TitleColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "titleSize": {
            "element": "BaseMap_TitleSize-Input",
            "default": 30,
            "kind": "number"
        },
        "referenceField": {
            "element": "BaseMap_Reference-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "labelFontSize": {
            "element": "BaseMap_LabelFontSize-Input",
            "default": 10,
            "kind": "number"
        },
        "refRadius": {
            "element": "BaseMap_LabelRadius-Input",
            "default": 1,
            "kind": "number"
        },
        "refColor": {
            "element": "BaseMap_LabelColor-Input",
            "default": "#7D7D7D",
            "kind": "color"
        },
        "refOpacity": {
            "element": "BaseMap_LabelOpacity-Input",
            "default": 80,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "ifRefTop": {
            "element": "BaseMap_LebelTop-CB",
            "default": False,
            "kind": "checkbox"
        }
    },
    "selfDesignedBaseMapSettings": {
        "cfMethod": {
            "element": "CPM_Classification-Select",
            "default": "Quantile",
            "kind": "select",
            "options": [
                "Quantile",
                "EqualInterval",
                "NaturalBreak",
                "Linear",
                "ManualBreak",
                "Categorical"
            ]
        },
        "clrScheme": {
            "element": "CPM_ColorScheme-Select",
            "default": "Blues",
            "kind": "select",
            "options": [
                "Blues",
                "Greens",
                "Greys",
                "Oranges",
                "Purples",
                "Reds",
                "PuBu",
                "RdPu",
                "YlGn",
                "YlGnBu",
                "YlOrRd",
                "PiYG",
                "PRGn",
                "RdBu",
                "RdYlBu",
                "Custom"
            ]
        },
        "minCustomColor": {
            "element": "CPM_MinCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "maxCustomColor": {
            "element": "CPM_MaxCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "ifFlipColor": {
            "element": "CPM_FlipLgClr-CB",
            "default": False,
            "kind": "checkbox"
        },
        "decimalPlaces": {
            "element": "CPM_LegendDP-Input",
            "default": 0,
            "kind": "number",
            "min": "0",
            "max": "5"
        },
        "clsNum": {
            "element": "CPM_ClassNum-Input",
            "default": 5,
            "kind": "number",
            "min": "4",
            "max": "8"
        },
        "fillOpacity": {
            "element": "CPM_FillOpacity-Input",
            "default": 100,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "strokeColor": {
            "element": "CPM_StrokeColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "strokeWidth": {
            "element": "CPM_StrokeWidth-Input",
            "default": 0.5,
            "kind": "number",
            "min": "0",
            "max": "10"
        },
        "legendTitle": {
            "element": "CPM_LegendTitle-Input",
            "default": "Choropleth Map Legend",
            "kind": "text"
        },
        "breakInput": {
            "element": "CPM_ManualBreak-Input",
            "default": "",
            "kind": "text"
        },
        "ifHideNull": {
            "element": "CPM_HideNull-CB",
            "default": False,
            "kind": "checkbox"
        },
        "ifMapRegionAttribute": {
            "element": "CPM_MapRegionAttribute-CB",
            "default": False,
            "kind": "checkbox"
        },
        "fillColorNoAttr": {
            "element": "Region_FillColor_NoAttr-Input",
            "default": "#c2c2c2",
            "kind": "color"
        },
        "attrSource": {
            "element": "radio:CPM_AttrSource",
            "default": "csv",
            "kind": "radio",
            "options": [
                "polygon",
                "csv"
            ]
        }
    },
    "pointMapFileSettings": {
        "id": {
            "element": "Point_ID-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "X": {
            "element": "Point_X-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "Y": {
            "element": "Point_Y-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "volume": {
            "element": "Point_Volume-Select",
            "default": "14",
            "kind": "select",
            "options": [
                "14",
                "noAttr"
            ]
        },
        "ifMapAttribute": {
            "element": "Point_MapAttribute-CB",
            "default": False,
            "kind": "checkbox"
        },
        "cfMethod": {
            "element": "Point_Classification-Select",
            "default": "Proportional",
            "kind": "select",
            "options": [
                "Proportional",
                "Quantile",
                "EqualInterval",
                "NaturalBreak",
                "ManualBreak",
                "Categorical"
            ]
        },
        "clsNum": {
            "element": "Point_ClassNum-Input",
            "default": 5,
            "kind": "number",
            "min": "4",
            "max": "8"
        },
        "clrScheme": {
            "element": "Point_ColorScheme-Select",
            "default": "Black",
            "kind": "select",
            "options": [
                "Black",
                "Blues",
                "Greens",
                "Greys",
                "Oranges",
                "Purples",
                "Reds",
                "PuBu",
                "RdPu",
                "YlGn",
                "YlGnBu",
                "YlOrRd",
                "PiYG",
                "PRGn",
                "RdBu",
                "RdYlBu",
                "Custom"
            ]
        },
        "minCustomColor": {
            "element": "Point_MinCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "maxCustomColor": {
            "element": "Point_MaxCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "noAttrFillColor": {
            "element": "Point_FillColor_NoAttr-Input",
            "default": "#c2c2c2",
            "kind": "color"
        },
        "noAttrRadius": {
            "element": "Point_NoAttr_Radius-Input",
            "default": 12,
            "kind": "number",
            "min": "1"
        },
        "showNoFlowNodes": {
            "element": "Point_ShowNoFlow-CB",
            "default": False,
            "kind": "checkbox"
        },
        "fillOpacity": {
            "element": "Point_FillOpacity-Input",
            "default": 100,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "radiusMin": {
            "element": "Point_Radius_Min-Input",
            "default": 2,
            "kind": "number",
            "min": "1",
            "max": "30"
        },
        "radiusMax": {
            "element": "Point_Radius_Max-Input",
            "default": 20,
            "kind": "number",
            "min": "1",
            "max": "30"
        },
        "strokeColor": {
            "element": "Point_StrokeColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "ifFlipColor": {
            "element": "Point_FlipLgClr-CB",
            "default": False,
            "kind": "checkbox"
        },
        "strokeWidth": {
            "element": "Point_StrokeWidth-Input",
            "default": 0.5,
            "kind": "number",
            "min": "0",
            "max": "5"
        },
        "decimalPlaces": {
            "element": "Point_LegendDP-Input",
            "default": 0,
            "kind": "number",
            "min": "0",
            "max": "5"
        },
        "legendTitle": {
            "element": "Point_LegendTitle-Input",
            "default": "Node Legend",
            "kind": "text"
        },
        "breakInput": {
            "element": "Point_ManualBreak-Input",
            "default": "",
            "kind": "text"
        },
        "isDisplayedAsAbs": {
            "element": "Point_DisplayAsAbs-CB",
            "default": False,
            "kind": "checkbox"
        },
        "titleWidth": {
            "element": None,
            "default": 200,
            "kind": "constant"
        }
    },
    "flowMapFileSettings": {
        "origin": {
            "element": "Flow_SourceID-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "destination": {
            "element": "Flow_TargetID-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "volume": {
            "element": "Flow_Volume-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "flowStyleName": {
            "element": "Flow_Style-Select",
            "default": "nyt",
            "kind": "select",
            "options": [
                "nyt",
                "curve",
                "strtHfArw",
                "tapered",
                "tearDrop",
                "curveFull",
                "strtFull"
            ]
        },
        "cfMethod": {
            "element": "Flow_Classification-Select",
            "default": "Proportional",
            "kind": "select",
            "options": [
                "Proportional",
                "Quantile",
                "EqualInterval",
                "NaturalBreak",
                "ManualBreak"
            ]
        },
        "clrScheme": {
            "element": "Flow_ColorScheme-Select",
            "default": "Black",
            "kind": "select",
            "options": [
                "Black",
                "Blues",
                "Greens",
                "Greys",
                "Oranges",
                "Purples",
                "Reds",
                "PuBu",
                "RdPu",
                "YlGn",
                "YlGnBu",
                "YlOrRd",
                "PiYG",
                "PRGn",
                "RdBu",
                "RdYlBu",
                "LinGrad",
                "Custom"
            ]
        },
        "minCustomColor": {
            "element": "Flow_MinCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "maxCustomColor": {
            "element": "Flow_MaxCustomColor-Input",
            "default": "#000000",
            "kind": "color"
        },
        "fillOpacity": {
            "element": "Flow_FillOpacity-Input",
            "default": 100,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "ifFlipColor": {
            "element": "Flow_FlipLgClr-CB",
            "default": False,
            "kind": "checkbox"
        },
        "decimalPlaces": {
            "element": "Flow_LegendDP-Input",
            "default": 0,
            "kind": "number",
            "min": "0",
            "max": "5"
        },
        "clsNum": {
            "element": "Flow_ClassNum-Input",
            "default": 5,
            "kind": "number",
            "min": "4",
            "max": "8"
        },
        "numTopFlows": {
            "element": "Flow_TopFlowFromAllFlows-Input",
            "default": 100,
            "kind": "number",
            "min": "1",
            "max": "1000"
        },
        "breakInput": {
            "element": "Flow_ManualBreak-Input",
            "default": "",
            "kind": "text"
        },
        "widthMax": {
            "element": "Flow_FlowWidth_Max-Input",
            "default": 14,
            "kind": "number",
            "min": "1",
            "max": "20"
        },
        "widthMin": {
            "element": "Flow_FlowWidth_Min-Input",
            "default": 4,
            "kind": "number",
            "min": "1",
            "max": "20"
        },
        "strokeWidth": {
            "element": "Flow_StrokeWidth-Input",
            "default": 0.5,
            "kind": "number",
            "min": "0",
            "max": "5"
        },
        "strokeColor": {
            "element": "Flow_StrokeColor-Input",
            "default": "#ffffff",
            "kind": "color"
        },
        "legendTitle": {
            "element": "Flow_LegendTitle-Input",
            "default": "Flow Legend",
            "kind": "text"
        },
        "isDisplayedAsAbs": {
            "element": "Flow_DisplayAsAbs-CB",
            "default": False,
            "kind": "checkbox"
        },
        "originColor": {
            "element": "Flow_MinLinGradColor-Input",
            "default": "#0571b0",
            "kind": "color"
        },
        "destinationColor": {
            "element": "Flow_MaxLinGradColor-Input",
            "default": "#ca0020",
            "kind": "color"
        },
        "flowLinGradMiddleColor": {
            "element": "Flow_LinGradMiddleColor-Select",
            "default": "#ffffff",
            "kind": "color"
        },
        "flowLinGradMidFillOpacity": {
            "element": "Flow_LinGradMidFillOpacity-Input",
            "default": 100,
            "kind": "number",
            "min": "0",
            "max": "100"
        },
        "flowLinGradStops": {
            "element": "radio:Flow_LinGradStops",
            "default": "2",
            "kind": "radio",
            "options": [
                "2",
                "3"
            ]
        },
        "symbology": {
            "element": None,
            "default": None,
            "kind": None
        },
        "titleWidth": {
            "element": None,
            "default": 200,
            "kind": "constant"
        }
    },
    "choroplethMapSettings": {
        "CSVId": {
            "element": "CPM_CSVPK-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "geoId": {
            "element": "CPM_BMPK-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        },
        "value": {
            "element": "CPM_Value-Select",
            "default": None,
            "kind": "select",
            "options": [
                "14"
            ]
        }
    },
    "viewSettings": {
        "legendVisibility": {
            "element": None,
            "default": None,
            "kind": None
        },
        "drawingOrder": {
            "element": None,
            "default": None,
            "kind": None
        },
        "darkMode": {
            "element": None,
            "default": None,
            "kind": None
        },
        "northArrow": {
            "element": None,
            "default": None,
            "kind": None
        }
    }
}
