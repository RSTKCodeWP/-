import folium
import webbrowser

MAP_FILE = "uav_map.html"


def generate_map(latitude, longitude):

    uav_map = folium.Map(
        location=[latitude, longitude],
        zoom_start=16
    )

    folium.Marker(
        [latitude, longitude],
        popup="UAV Position"
    ).add_to(uav_map)

    uav_map.save(MAP_FILE)

    webbrowser.open(MAP_FILE)


if __name__ == "__main__":

    generate_map(
        28.6139,
        77.2090
    )
