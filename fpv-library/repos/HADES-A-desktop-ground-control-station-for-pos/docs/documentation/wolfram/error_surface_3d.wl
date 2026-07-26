(* HADES hero visual 1 of 3: localization error surface (3D).

   Renders the localization meter-error as a smooth surface over the (slant range x camera
   pitch-from-nadir) plane. Reads the REAL sim grid in data/localization_surface.csv (each
   cell is the median error of real Fuser runs against known ground truth, kind=sim) and
   interpolates a surface across the populated cells. This is where Wolfram beats matplotlib:
   a lit, interpolated 3D surface with a clean color ramp.

   HONESTY: every height is a (sim) number from the calibrated synthetic simulator. Real-flight
   numbers will move when the magnetometer-less heading distribution is measured.

   Run (from this directory, after make_surface_data.py has written the CSV):
     wolframscript -file error_surface_3d.wl
   Writes: ../figures/hero-loc-error-surface.png
*)

(* Resolve paths relative to this script (works under `wolframscript -file`). *)
here = If[$InputFileName === "", Directory[], DirectoryName[$InputFileName]];
dataDir = FileNameJoin[{here, "..", "data"}];
figDir = FileNameJoin[{here, "..", "figures"}];
csv = Import[FileNameJoin[{dataDir, "localization_surface.csv"}], "CSV"];

(* Drop the header, keep only populated cells: {slant, pitch, err}. Import already
   numericizes "25.0" -> 25.; NaN cells stay the string "NaN", so NumberQ drops them. *)
rows = Rest[csv];
pts = Select[rows[[All, {1, 2, 3}]], NumberQ[#[[3]]] &];

(* Interpolation (NOT ListInterpolation) is the scattered-data path: it takes {x,y,z}
   triples directly and triangulates. Only 21 of 70 cells are populated, so the surface is
   defined within the convex hull; Quiet suppresses the outside-hull warnings at the corners.
   Older Wolfram (<13) fallback: ResourceFunction["RBFInterpolation"][pts]. *)
surface = Interpolation[pts, InterpolationOrder -> 1] // Quiet;

(* HADES palette: charcoal canvas, cyan->amber->orange error ramp. *)
bg = RGBColor[11/255, 14/255, 20/255];
ramp = Blend[{{0, RGBColor[51/255, 197/255, 224/255]},
              {0.5, RGBColor[230/255, 162/255, 60/255]},
              {1, RGBColor[232/255, 83/255, 31/255]}}, #] &;

slantRange = MinMax[pts[[All, 1]]];
pitchRange = MinMax[pts[[All, 2]]];

plot = Plot3D[
   surface[s, p],
   {s, slantRange[[1]], slantRange[[2]]},
   {p, pitchRange[[1]], pitchRange[[2]]},
   PlotRange -> All,
   ColorFunction -> (ramp[#3 / Max[pts[[All, 3]]]] &),
   ColorFunctionScaling -> False,
   AxesLabel -> {Style["slant range (m)", White, 12],
                 Style["pitch from nadir (deg)", White, 12],
                 Style["error (m, sim)", White, 12]},
   PlotLabel -> Style["HADES localization error surface (sim)", White, 16],
   Background -> bg,
   Boxed -> True,
   BoxStyle -> Directive[RGBColor[51/255, 69/255, 106/255]],
   ImageSize -> 1100,
   Lighting -> "Neutral",
   Mesh -> None,
   PlotPoints -> 40
];

(* Overlay the real sample points so the viewer sees the surface is data, not fantasy. *)
samples = Graphics3D[{RGBColor[230/255, 237/255, 243/255], PointSize[0.012],
   Point[pts]}];

out = FileNameJoin[{figDir, "hero-loc-error-surface.png"}];
Export[out, Show[plot, samples], "PNG", ImageResolution -> 200];
Print["wrote " <> out];
