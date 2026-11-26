"""FlowMapper's Tools menu and field auto-fill.

=====================================  ================================================
:mod:`~flowmapper_org.tools.centroids`     Polygons to Points (centroids as FlowMapper draws them)
:mod:`~flowmapper_org.tools.matrix`        Flow Matrix to Flow List
:mod:`~flowmapper_org.tools.coords`        Flow Coordinates to Nodes (T-39)
:mod:`~flowmapper_org.tools.normalize`     Normalize Flows (modularity flows; Java servlet)
:mod:`~flowmapper_org.tools.network`       Calculate Node Measures (Java servlet)
:mod:`~flowmapper_org.tools.fields`        field guessing after a file is loaded
=====================================  ================================================
"""
from .centroids import generate_centroids_csv, path_centroid, polygon_centroids, topojson_features
from .coords import FLOW_COORD_PATTERNS, FlowCoordsResult, convert_flow_coordinates_to_nodes, guess_flow_coord_columns
from .fields import (FIELD_HINTS, column_range, column_values, guess_flow_fields, guess_node_fields,
                     guess_region_join, is_numeric_column, overlap_share, region_field_names)
from .matrix import convert_flow_matrix_to_flow_list, flow_matrix_to_flow_list
from .network import NETWORK_MEASURES, network_node_measures, node_measures_csv
from .normalize import modularity_flows, normalize_flows_csv

__all__ = [
    "generate_centroids_csv", "path_centroid", "polygon_centroids", "topojson_features",
    "FLOW_COORD_PATTERNS", "FlowCoordsResult", "convert_flow_coordinates_to_nodes", "guess_flow_coord_columns",
    "FIELD_HINTS", "column_range", "column_values", "guess_flow_fields", "guess_node_fields",
    "guess_region_join", "is_numeric_column", "overlap_share", "region_field_names",
    "convert_flow_matrix_to_flow_list", "flow_matrix_to_flow_list",
    "NETWORK_MEASURES", "network_node_measures", "node_measures_csv",
    "modularity_flows", "normalize_flows_csv",
]
