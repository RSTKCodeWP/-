import folium
import webbrowser

MAP_FILE = "uav_map.html"

latitude = 28.6139
longitude = 77.2090

uav_map = folium.Map(
    location=[latitude, longitude],
    zoom_start=15
)

folium.Marker(
    [latitude, longitude],
    popup="UAV Position"
).add_to(uav_map)

uav_map.save(MAP_FILE)

webbrowser.open(MAP_FILE)

print("Map Generated")