"""Unit tests: survey grid generation algorithm (Python mirror of survey.ts)."""

import math

M_PER_DEG_LAT = 111320


def m_per_deg_lon(lat):
    return 111320 * math.cos(lat * math.pi / 180)


def to_local(p, origin):
    return (
        (p["lon"] - origin["lon"]) * m_per_deg_lon(origin["lat"]),
        (p["lat"] - origin["lat"]) * M_PER_DEG_LAT,
    )


def to_geo(x, y, origin):
    return {
        "lat": origin["lat"] + y / M_PER_DEG_LAT,
        "lon": origin["lon"] + x / m_per_deg_lon(origin["lat"]),
    }


def rotate_point(x, y, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (x * c - y * s, x * s + y * c)


def generate_survey_grid(polygon, angle, spacing, alt, overshoot=10):
    if len(polygon) < 3:
        return []
    origin = polygon[0]
    angle_rad = angle * math.pi / 180
    local = [to_local(p, origin) for p in polygon]
    rotated = [rotate_point(x, y, -angle_rad) for x, y in local]

    min_y = min(y for _, y in rotated)
    max_y = max(y for _, y in rotated)

    lines = []
    y = min_y + spacing / 2
    while y < max_y:
        intersections = []
        for i in range(len(rotated)):
            j = (i + 1) % len(rotated)
            x1, y1 = rotated[i]
            x2, y2 = rotated[j]
            if (y1 <= y < y2) or (y2 <= y < y1):
                x = x1 + (y - y1) / (y2 - y1) * (x2 - x1)
                intersections.append(x)
        intersections.sort()
        for k in range(0, len(intersections) - 1, 2):
            lines.append(
                [
                    rotate_point(intersections[k] - overshoot, y, angle_rad),
                    rotate_point(intersections[k + 1] + overshoot, y, angle_rad),
                ]
            )
        y += spacing

    waypoints = []
    reverse = False
    for line in lines:
        pts = [line[1], line[0]] if reverse else [line[0], line[1]]
        for x, y in pts:
            geo = to_geo(x, y, origin)
            waypoints.append({"lat": geo["lat"], "lon": geo["lon"], "alt": alt})
        reverse = not reverse
    return waypoints


def polygon_area(polygon):
    if len(polygon) < 3:
        return 0
    origin = polygon[0]
    local = [to_local(p, origin) for p in polygon]
    area = 0
    for i in range(len(local)):
        j = (i + 1) % len(local)
        area += local[i][0] * local[j][1]
        area -= local[j][0] * local[i][1]
    return abs(area) / 2


class TestSurveyGrid:
    def _square(self, size=100):
        lat, lon = 34.258, 108.942
        d_lat = size / M_PER_DEG_LAT
        d_lon = size / m_per_deg_lon(lat)
        return [
            {"lat": lat, "lon": lon},
            {"lat": lat, "lon": lon + d_lon},
            {"lat": lat + d_lat, "lon": lon + d_lon},
            {"lat": lat + d_lat, "lon": lon},
        ]

    def test_generates_waypoints(self):
        poly = self._square(100)
        wps = generate_survey_grid(poly, angle=0, spacing=20, alt=30)
        assert len(wps) > 0
        assert len(wps) % 2 == 0

    def test_all_waypoints_have_altitude(self):
        poly = self._square(100)
        wps = generate_survey_grid(poly, angle=0, spacing=20, alt=50)
        for wp in wps:
            assert wp["alt"] == 50

    def test_waypoints_near_polygon(self):
        poly = self._square(100)
        wps = generate_survey_grid(poly, angle=0, spacing=20, alt=30, overshoot=0)
        for wp in wps:
            assert abs(wp["lat"] - 34.258) < 0.002
            assert abs(wp["lon"] - 108.942) < 0.002

    def test_spacing_affects_count(self):
        poly = self._square(200)
        wps_10 = generate_survey_grid(poly, angle=0, spacing=10, alt=30)
        wps_50 = generate_survey_grid(poly, angle=0, spacing=50, alt=30)
        assert len(wps_10) > len(wps_50)

    def test_angle_changes_pattern(self):
        poly = self._square(100)
        wps_0 = generate_survey_grid(poly, angle=0, spacing=20, alt=30)
        wps_90 = generate_survey_grid(poly, angle=90, spacing=20, alt=30)
        assert len(wps_0) > 0
        assert len(wps_90) > 0
        assert wps_0[0]["lat"] != wps_90[0]["lat"] or wps_0[0]["lon"] != wps_90[0]["lon"]

    def test_too_few_points(self):
        assert generate_survey_grid([], angle=0, spacing=20, alt=30) == []
        assert generate_survey_grid([{"lat": 0, "lon": 0}], angle=0, spacing=20, alt=30) == []

    def test_serpentine_pattern(self):
        poly = self._square(100)
        wps = generate_survey_grid(poly, angle=0, spacing=20, alt=30, overshoot=0)
        if len(wps) >= 4:
            lon_0 = wps[0]["lon"]
            lon_1 = wps[1]["lon"]
            lon_2 = wps[2]["lon"]
            lon_3 = wps[3]["lon"]
            dir1 = lon_1 - lon_0
            dir2 = lon_3 - lon_2
            assert dir1 * dir2 < 0 or abs(dir1) < 1e-8


class TestPolygonArea:
    def test_square_area(self):
        lat, lon = 34.258, 108.942
        size = 100
        d_lat = size / M_PER_DEG_LAT
        d_lon = size / m_per_deg_lon(lat)
        poly = [
            {"lat": lat, "lon": lon},
            {"lat": lat, "lon": lon + d_lon},
            {"lat": lat + d_lat, "lon": lon + d_lon},
            {"lat": lat + d_lat, "lon": lon},
        ]
        area = polygon_area(poly)
        assert abs(area - 10000) < 100

    def test_empty(self):
        assert polygon_area([]) == 0
        assert polygon_area([{"lat": 0, "lon": 0}]) == 0
