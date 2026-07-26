from flight_safety.geofence import inside_geofence

# A simple square around (0,0).
SQUARE = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]


def test_point_inside():
    assert inside_geofence(0.0, 0.0, SQUARE) is True


def test_point_outside():
    assert inside_geofence(2.0, 0.0, SQUARE) is False


def test_empty_geofence_allows_all():
    # No geofence configured => unconstrained (return True).
    assert inside_geofence(99.0, 99.0, []) is True


from flight_safety.geofence import project_latlon


def test_project_latlon_north():
    # heading 0 (north), 10 m/s forward, 1 s -> ~10 m north (~9e-5 deg lat)
    lat, lon = project_latlon(47.0, 8.0, yaw_deg=0.0, forward=10.0, right=0.0, dt=1.0)
    assert lon == 8.0
    assert abs((lat - 47.0) - (10.0 / 111320.0)) < 1e-7


def test_project_latlon_east_via_right():
    # heading 0, strafe right 10 m/s -> moves east
    lat, lon = project_latlon(47.0, 8.0, yaw_deg=0.0, forward=0.0, right=10.0, dt=1.0)
    assert abs(lat - 47.0) < 1e-9
    assert lon > 8.0
