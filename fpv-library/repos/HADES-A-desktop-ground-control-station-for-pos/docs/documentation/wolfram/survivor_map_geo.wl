(* HADES hero visual 2 of 3: geospatial survivor map with uncertainty ellipses.

   Plots the localizer's real contacts from the baked demo mission on a geographic map: a pin
   per survivor, ringed by its R95 uncertainty circle (the honest "how sure are we" radius).
   Reads data/mission_contacts.csv (real Fuser output; scene synthetic, median error 1.1 m vs
   known truth). CUE_ONLY contacts have a null coordinate and are listed off-map, not faked
   onto it. This is where Wolfram beats matplotlib: true GeoGraphics with a real basemap and
   metric-radius geo disks.

   Run (from this directory, after make_mission_contacts.py has written the CSV):
     wolframscript -file survivor_map_geo.wl
   Writes: ../figures/hero-survivor-map.png
*)

here = If[$InputFileName === "", Directory[], DirectoryName[$InputFileName]];
dataDir = FileNameJoin[{here, "..", "data"}];
figDir = FileNameJoin[{here, "..", "figures"}];
csv = Import[FileNameJoin[{dataDir, "mission_contacts.csv"}], "CSV"];
rows = Rest[csv];

(* Parse: {track, lat, lon, r95, class}. Keep only contacts with a real coordinate. *)
parse[r_] := <|
   "track" -> r[[1]],
   "lat" -> ToExpression[r[[2]]],
   "lon" -> ToExpression[r[[3]]],
   "r95" -> ToExpression[r[[4]]],
   "class" -> r[[5]]
|>;
contacts = parse /@ rows;
located = Select[contacts, NumberQ[#["lat"]] && NumberQ[#["lon"]] &];
cueOnly = Select[contacts, ! (NumberQ[#["lat"]] && NumberQ[#["lon"]]) &];

(* HADES status palette: PINPOINT green, SWEEP amber, anything else stale violet. *)
classColor[c_] := Switch[c,
   "PINPOINT", RGBColor[47/255, 182/255, 124/255],
   "SWEEP", RGBColor[230/255, 162/255, 60/255],
   "AREA", RGBColor[232/255, 83/255, 31/255],
   _, RGBColor[126/255, 120/255, 168/255]];

(* A pin + its R95 uncertainty disk (GeoDisk takes a metric radius -> honest on the map). *)
markers = Flatten[Map[
   Function[c, {
     Opacity[0.18], classColor[c["class"]],
     GeoDisk[GeoPosition[{c["lat"], c["lon"]}], Quantity[c["r95"], "Meters"]],
     Opacity[1.0], classColor[c["class"]], PointSize[0.02],
     Point[GeoPosition[{c["lat"], c["lon"]}]],
     Text[Style[c["class"] <> "  R95 " <> ToString[Round[c["r95"]]] <> " m",
        10, White], GeoPosition[{c["lat"], c["lon"]}], {0, -1.6}]
   }], located]];

center = GeoPosition[{Mean[located[[All, "lat"]]], Mean[located[[All, "lon"]]]}];

map = GeoGraphics[
   markers,
   GeoCenter -> center,
   GeoRange -> Quantity[400, "Meters"],
   GeoBackground -> GeoStyling["StreetMapNoLabels"],
   ImageSize -> 1000,
   PlotLabel -> Style[
      "HADES survivor map - real localizer output (scene synthetic, median err 1.1 m)",
      White, 14],
   Background -> RGBColor[11/255, 14/255, 20/255],
   GeoGridLines -> None
];

note = Style[
   "Pins + R95 circles are live Fuser output. " <>
   ToString[Length[cueOnly]] <> " CUE_ONLY contact(s) have no coordinate and are not plotted.",
   White, 11];

out = FileNameJoin[{figDir, "hero-survivor-map.png"}];
Export[out, Column[{map, note}, Center], "PNG", ImageResolution -> 200];
Print["wrote " <> out];
