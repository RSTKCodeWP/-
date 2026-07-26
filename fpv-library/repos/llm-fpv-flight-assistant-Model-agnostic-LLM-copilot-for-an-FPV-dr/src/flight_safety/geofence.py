from shapely.geometry import Point, Polygon


def inside_geofence(lat: float, lon: float, vertices: list[tuple[float, float]]) -> bool:
    """True if (lat, lon) is inside the polygon. Empty polygon => unconstrained (True)."""
    if not vertices:
        return True
    if len(vertices) < 3:
        return False  # a polygon needs >= 3 vertices; treat as invalid/forbidden
    poly = Polygon(vertices)
    return poly.covers(Point(lat, lon))  # covers() includes boundary


import math


def project_latlon(lat: float, lon: float, yaw_deg: float,
                   forward: float, right: float, dt: float) -> tuple[float, float]:
    """Project a lat/lon forward by a body-frame horizontal velocity over dt seconds.

    yaw_deg is heading (0 = North, clockwise). Body forward points along heading,
    body right is 90deg clockwise from forward. Flat-earth small-step approximation.
    """
    yaw = math.radians(yaw_deg)
    v_north = forward * math.cos(yaw) - right * math.sin(yaw)
    v_east = forward * math.sin(yaw) + right * math.cos(yaw)
    dlat = (v_north * dt) / 111320.0
    dlon = (v_east * dt) / (111320.0 * math.cos(math.radians(lat)) or 1e-9)
    return lat + dlat, lon + dlon
