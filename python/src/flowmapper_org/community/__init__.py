"""Regionalization (community detection) of flow networks, as on FlowMapper.org.

Ports ``CommunityDetection.js`` (Tools > Regionalization): Leiden and Louvain
modularity optimisation, the spatially constrained variants ScLeiden/ScLouvain
(Wang, Wang & Onega 2021), region boundaries (Voronoi cells or dissolved
polygons), representative region nodes, region-to-region flows and the result
as a new FlowMapper project. A given seed gives the same partition as the web
application (FlowMapper's ``mulberry32`` PRNG and iteration order are
reproduced exactly).

>>> from flowmapper_org import Project                         # doctest: +SKIP
>>> from flowmapper_org.community import detect_communities    # doctest: +SKIP
>>> res = detect_communities(Project.load("projectfile.json"), method="leiden", seed=1)  # doctest: +SKIP
>>> res.region_nodes, res.region_flows, res.modularity     # doctest: +SKIP
>>> res.to_project().save("regions.json")                  # doctest: +SKIP

Low-level: :func:`make_graph`, :func:`leiden`, :func:`louvain`, :func:`modularity`.
"""
from .boundaries import (dissolve_rings, point_in_geometry_xy, point_in_ring_xy, polygon_boundaries,
                         ring_area_xy, rings_to_multipolygon, voronoi_boundaries)
from .delaunay import Delaunay, Voronoi
from .graph import (Graph, aggregate_graph, leiden, leiden_local_moving, leiden_refine, louvain,
                    louvain_local_moving, make_graph, modularity, mulberry32, relabel, shuffled)
from .regionalize import (REGION_METHODS, CommunityResult, build_region_project, choose_polygon_field,
                          detect_communities, region_field_names, representative_locations)
from .spatial import (SpatialAdjacency, SpatialConstraintResult, build_spatial_adjacency, delaunay_neighbours,
                      enforce_spatial_constraint)
from .topojson import feature as topojson_feature
from .topojson import merge as topojson_merge

__all__ = [
    "detect_communities", "CommunityResult", "REGION_METHODS", "build_region_project",
    "Graph", "make_graph", "leiden", "louvain", "modularity", "mulberry32", "shuffled",
    "leiden_local_moving", "louvain_local_moving", "leiden_refine", "relabel", "aggregate_graph",
    "build_spatial_adjacency", "delaunay_neighbours", "enforce_spatial_constraint",
    "SpatialAdjacency", "SpatialConstraintResult",
    "ring_area_xy", "point_in_ring_xy", "point_in_geometry_xy", "dissolve_rings", "rings_to_multipolygon",
    "voronoi_boundaries", "polygon_boundaries", "representative_locations", "choose_polygon_field",
    "region_field_names", "Delaunay", "Voronoi", "topojson_feature", "topojson_merge",
]
