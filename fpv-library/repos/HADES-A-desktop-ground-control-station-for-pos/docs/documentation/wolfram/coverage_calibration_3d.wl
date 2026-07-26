(* HADES hero visual 3 of 3: coverage calibration as a 3D bar field.

   Renders the uncertainty-calibration matrix as 3D bars: each (sim, fuser) noise pairing is a
   bar whose height is empirical coverage, colored by how far it sits from the 95% target.
   Reads data/coverage_matrix.csv (8 real rows, run at seed=0). The story reads at a glance:
   the matched control and benign mismatches sit near 95% (the arithmetic is right), and the
   out-of-schema time-sync rows collapse (the non-tautology proof the metric measures the
   world, not its own math). This is where Wolfram beats matplotlib: a lit 3D bar field with a
   target plane the bars visibly punch through or fall under.

   HONESTY: all (sim). The collapse is the headline - it is the system being honest about a
   failure mode the Monte Carlo cannot model.

   Run (from this directory):
     wolframscript -file coverage_calibration_3d.wl
   Writes: ../figures/hero-coverage-3d.png
*)

here = If[$InputFileName === "", Directory[], DirectoryName[$InputFileName]];
dataDir = FileNameJoin[{here, "..", "data"}];
figDir = FileNameJoin[{here, "..", "figures"}];
csv = Import[FileNameJoin[{dataDir, "coverage_matrix.csv"}], "CSV"];
rows = Rest[csv];

names = rows[[All, 1]];
coverage = ToExpression /@ rows[[All, 2]];
n = Length[rows];

target = 0.95;

(* Color ramp: near/over target = structural blue, dipping = amber, collapse = magenta. *)
barColor[c_] := Which[
   c >= 0.90, RGBColor[59/255, 123/255, 200/255],
   c >= 0.60, RGBColor[230/255, 162/255, 60/255],
   True, RGBColor[245/255, 50/255, 107/255]];

(* One 3D bar per row, laid out along x; depth axis unused (single series). *)
bars = Table[
   With[{c = coverage[[i]]},
     {barColor[c], EdgeForm[RGBColor[51/255, 69/255, 106/255]],
      Cuboid[{i - 0.4, -0.4, 0}, {i + 0.4, 0.4, c}]}],
   {i, n}];

(* The 95% target plane the bars are measured against. *)
targetPlane = {Opacity[0.25], RGBColor[232/255, 83/255, 31/255],
   Polygon[{{0.3, -0.5, target}, {n + 0.7, -0.5, target},
            {n + 0.7, 0.5, target}, {0.3, 0.5, target}}]};

labels = Table[
   Text[Style[names[[i]], White, 9], {i, 0.9, 0}], {i, n}];

scene = Graphics3D[
   Join[bars, targetPlane, labels],
   Background -> RGBColor[11/255, 14/255, 20/255],
   Boxed -> True,
   BoxStyle -> Directive[RGBColor[51/255, 69/255, 106/255]],
   Axes -> {False, False, True},
   AxesLabel -> {"", "", Style["coverage", White, 12]},
   AxesStyle -> White,
   PlotLabel -> Style["HADES uncertainty calibration (sim) - matched ~95%, time-sync collapses",
      White, 15],
   ImageSize -> 1100,
   ViewPoint -> {1.6, -2.4, 1.3},
   Lighting -> "Neutral"
];

out = FileNameJoin[{figDir, "hero-coverage-3d.png"}];
Export[out, scene, "PNG", ImageResolution -> 200];
Print["wrote " <> out];
