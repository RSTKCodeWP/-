from flight_safety.config import Limits, Settings


def test_limits_defaults_are_sane():
    lim = Limits()
    assert lim.max_alt_m > lim.min_alt_m >= 0
    assert lim.max_speed_ms > 0
    assert 0 <= lim.min_battery_pct <= 1.0


def test_settings_parses_geofence_from_list():
    s = Settings(geofence=[[47.397, 8.545], [47.398, 8.545], [47.398, 8.546]])
    assert len(s.geofence) == 3
    assert s.geofence[0] == (47.397, 8.545)


def test_settings_has_connection_default():
    s = Settings()
    assert "14540" in s.mavlink_address
