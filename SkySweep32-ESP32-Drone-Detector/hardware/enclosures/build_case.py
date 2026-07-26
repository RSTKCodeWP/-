#!/usr/bin/env python3
"""
SkySweep32 Pro Tier — FreeCAD Case Generator (Sentinel Style)
Generates a proper field-ready enclosure for the 120x80mm carrier PCB.

Sentinel specs (from enclosures.md):
  - Robust, industrial box
  - Material: ASA/PETG for outdoor use
  - 4x SMA/N-Type bulkhead connectors spread apart
  - Mounting brackets (wing ears) for pole/wall mount
  - Rear ventilation slots (Goretex-style)
  - OLED window on top panel
  - USB access port
  - M3 brass heat-set standoffs
  - Case halves joined with M3 screws
"""

import FreeCAD
import FreeCADGui
import Part
import sys
import traceback

def vec(x, y, z):
    return FreeCAD.Vector(x, y, z)

def rot_x(deg):
    pl = FreeCAD.Placement()
    pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), deg)
    return pl

def rot_y(deg):
    pl = FreeCAD.Placement()
    pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), deg)
    return pl

def rot_z(deg):
    pl = FreeCAD.Placement()
    pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), deg)
    return pl

def cylinder(r, h, pos, axis_rot=None):
    c = Part.makeCylinder(r, h)
    if axis_rot:
        c.Placement = axis_rot
    c.translate(FreeCAD.Vector(*pos))
    return c

def box(dx, dy, dz, pos=(0,0,0)):
    b = Part.makeBox(dx, dy, dz)
    b.translate(FreeCAD.Vector(*pos))
    return b

def fillet_edges(shape, radius, edge_indices=None):
    """Fillet all edges, or specific ones."""
    try:
        edges = []
        for i, edge in enumerate(shape.Edges):
            if edge_indices is None or i in edge_indices:
                edges.append(edge)
        if edges:
            return shape.makeFillet(radius, edges)
    except Exception:
        pass
    return shape


def generate():
    FreeCADGui.showMainWindow()
    doc = FreeCAD.newDocument("SkySweep32_Pro_Case")

    # ── DIMENSIONS ──────────────────────────────────────────────────────────
    PCB_W  = 120.0   # PCB width
    PCB_H  = 80.0    # PCB height (depth)
    PCB_T  = 1.6     # PCB thickness

    WALL   = 3.0     # Wall thickness
    FLOOR  = 3.0     # Bottom floor thickness
    LID    = 3.0     # Lid thickness

    # PCB sits on 5mm standoffs from the floor
    STANDOFF_H = 5.0
    # Max component height above PCB (NRF24 antenna + SMA body)
    COMP_H = 22.0
    # Total inner height needed
    INNER_H = STANDOFF_H + PCB_T + COMP_H  # ~28.6mm
    # Outer box height (bottom shell)
    BOT_H = FLOOR + INNER_H  # ~31.6mm → round to 32
    BOT_H = 32.0
    # Lid height
    LID_H = 12.0

    OUTER_W = PCB_W + 2 * WALL   # 126
    OUTER_D = PCB_H + 2 * WALL   # 86
    OUTER_H = BOT_H + LID_H      # 44mm total

    FILLET_R = 4.0   # Corner fillet radius

    # PCB corner mounting hole positions (relative to PCB origin at inner corner)
    # PCB holes at (5,5), (115,5), (5,75), (115,75) of 120×80mm board
    MH = [(5, 5), (115, 5), (5, 75), (115, 75)]

    # ── ① BOTTOM SHELL ──────────────────────────────────────────────────────
    # Outer solid
    bot_outer = box(OUTER_W, OUTER_D, BOT_H)

    # Inner cavity (remove to leave walls + floor)
    bot_inner = box(PCB_W, PCB_H, BOT_H - FLOOR,
                    pos=(WALL, WALL, FLOOR))

    bottom = bot_outer.cut(bot_inner)

    # Fillet exterior vertical edges (top view corners)
    bottom = fillet_edges(bottom, FILLET_R)

    # ── Mounting standoffs (M3 brass insert style) ────────────────────────
    # Standoff: OD=6mm, height=5mm, inner hole for M3 insert (Ø4.6mm×4mm)
    for (hx, hy) in MH:
        # Solid standoff pillar
        stoff = cylinder(3.5, STANDOFF_H, (WALL + hx, WALL + hy, FLOOR))
        # Hole for M3 heat-set insert (Ø3.2mm drill, user presses insert in)
        ins_hole = cylinder(1.6, STANDOFF_H + 1, (WALL + hx, WALL + hy, FLOOR - 0.5))
        stoff = stoff.cut(ins_hole)
        bottom = bottom.fuse(stoff)

    # ── Corner screw bosses on bottom shell for lid joining ───────────────
    # 4 corner posts on the top rim for M3 screws to hold lid
    boss_h = 5.0
    for (bx, by) in [(0, 0), (OUTER_W, 0), (0, OUTER_D), (OUTER_W, OUTER_D)]:
        # Small boss cylinder at each corner inside
        boss = cylinder(4.0, boss_h, (bx + (5 if bx == 0 else -5),
                                       by + (5 if by == 0 else -5),
                                       BOT_H))
        screw_hole = cylinder(1.5, boss_h + 1, (bx + (5 if bx == 0 else -5),
                                                  by + (5 if by == 0 else -5),
                                                  BOT_H - 1))
        boss = boss.cut(screw_hole)
        bottom = bottom.fuse(boss)

    # ── USB-C / Micro-USB port cutout (left wall, aligned with ESP32) ─────
    # ESP32 USB is at the left end of the module, ~x=0 on PCB, y center ~28mm from PCB edge
    # On the box: left wall is at x=0, port is at inner x=0 (PCB left edge)
    # Port is ~9mm wide × 4mm tall, USB-C spec
    usb_cut = box(WALL + 2, 10, 4.5, pos=(-1, WALL + 10, FLOOR + STANDOFF_H + PCB_T + 1))
    bottom = bottom.cut(usb_cut)

    # ── Ventilation slots on rear wall (y = OUTER_D) ─────────────────────
    # 8 slots: 25mm long, 2.5mm wide, 3mm apart, horizontally on rear wall
    slot_w = 2.5
    slot_l = 30.0
    slot_start_x = WALL + 10
    slot_z_base  = FLOOR + 5
    for i in range(8):
        sz = slot_z_base + i * 3.2
        if sz + slot_w > BOT_H - 2:
            break
        slot = box(slot_l, WALL + 2, slot_w,
                   pos=(slot_start_x, OUTER_D - 1, sz))
        bottom = bottom.cut(slot)

    # ── SMA bulkhead holes (right wall at x=OUTER_W) ──────────────────────
    # 4 connectors at y-positions spread evenly, z at mid-height of component area
    sma_ys = [WALL + 12, WALL + 30, WALL + 50, WALL + 68]
    sma_z  = FLOOR + STANDOFF_H + PCB_T + 8   # z-center of SMA holes
    for sy in sma_ys:
        # SMA through-hole: Ø6.5mm for M-type nut
        sma_hole_ax = rot_y(90)
        sma_h = cylinder(3.25, WALL + 2, (OUTER_W - 1, sy, sma_z), axis_rot=sma_hole_ax)
        # Actually make it a simple box drill through the wall:
        sma_cyl = Part.makeCylinder(3.25, WALL + 2)
        sma_cyl.Placement = rot_y(90)
        sma_cyl.translate(vec(OUTER_W - 1, sy, sma_z))
        bottom = bottom.cut(sma_cyl)

    # ── Wing mounting brackets (for pole/wall mount) ───────────────────────
    for side in [-1, 1]:
        ear_y = OUTER_D / 2
        ear_x = OUTER_W/2 + side * (OUTER_W/2 + 12)
        # Flat wing ear: 24×8×40mm
        ear = box(8, 40, 8, pos=(ear_x - (8 if side > 0 else 0), ear_y - 20, BOT_H - 8))
        # Slot hole for U-bolt / zip-tie: 6mm × 20mm
        ear_slot = box(6, 20, 10, pos=(ear_x - (7 if side > 0 else 1), ear_y - 10, BOT_H - 9))
        ear = ear.cut(ear_slot)
        bottom = bottom.fuse(ear)

    # ── ② LID / TOP SHELL ───────────────────────────────────────────────────
    lid_outer = box(OUTER_W, OUTER_D, LID_H, pos=(0, 0, BOT_H))

    # Inner cavity (leave 3mm ceiling)
    lid_inner = box(PCB_W - 2, PCB_H - 2, LID_H - LID,
                    pos=(WALL + 1, WALL + 1, BOT_H + LID))
    lid = lid_outer.cut(lid_inner)

    # Fillet lid exterior
    lid = fillet_edges(lid, FILLET_R)

    # ── OLED window (top face of lid) ────────────────────────────────────
    # OLED 0.96" display: visible area ~21.7mm × 10.8mm
    # On PCB the OLED header (J_OLED) is at x=20, the display is roughly at PCB x=23-47, y=0-27
    # On the box lid (top face), that translates to: x=(WALL+23) to (WALL+47), y=(WALL+0) to (WALL+14)
    oled_w = 26.0
    oled_h = 14.0
    oled_x = WALL + 23
    oled_y = WALL + 5
    oled_cut = box(oled_w, oled_h, LID + 2, pos=(oled_x, oled_y, BOT_H - 1))
    lid = lid.cut(oled_cut)

    # Small ledge/frame around OLED window (0.5mm raised edge so OLED glass rests in)
    oled_frame_outer = box(oled_w + 2, oled_h + 2, 1.2, pos=(oled_x - 1, oled_y - 1, BOT_H + LID_H - 1.2))
    oled_frame_inner = box(oled_w, oled_h, 1.5, pos=(oled_x, oled_y, BOT_H + LID_H - 1.5))
    oled_frame = oled_frame_outer.cut(oled_frame_inner)
    lid = lid.fuse(oled_frame)

    # ── Top ventilation slots (3 slots, GPS area, smaller) ───────────────
    for i in range(3):
        tv_x = WALL + 70 + i * 8
        tv_slot = box(3, 25, LID + 2, pos=(tv_x, WALL + 27, BOT_H - 1))
        lid = lid.cut(tv_slot)

    # ── Screw holes in lid corners (M3 through holes) ─────────────────────
    for (bx, by) in [(0, 0), (OUTER_W, 0), (0, OUTER_D), (OUTER_W, OUTER_D)]:
        screw_th = cylinder(1.6, LID_H + 2,
                             (bx + (5 if bx == 0 else -5),
                              by + (5 if by == 0 else -5),
                              BOT_H - 1))
        lid = lid.cut(screw_th)

    # ── GPS SMA hole in lid (top, for GPS patch antenna cable) ───────────
    gps_ant_cut = cylinder(4.5, LID + 2, (WALL + 100, WALL + 65, BOT_H - 1))
    lid = lid.cut(gps_ant_cut)

    # ── ③ VISUAL CARRIER PCB PLACEHOLDER ────────────────────────────────
    pcb_vis = box(PCB_W, PCB_H, PCB_T,
                  pos=(WALL, WALL, FLOOR + STANDOFF_H))

    # ── ADD TO DOCUMENT ────────────────────────────────────────────────────
    bot_obj = doc.addObject("Part::Feature", "Case_Bottom")
    bot_obj.Shape = bottom
    bot_obj.ViewObject.ShapeColor = (0.18, 0.22, 0.28)  # Dark military grey-blue
    bot_obj.ViewObject.Transparency = 0

    lid_obj = doc.addObject("Part::Feature", "Case_Lid")
    lid_obj.Shape = lid
    lid_obj.ViewObject.ShapeColor = (0.22, 0.27, 0.33)
    lid_obj.ViewObject.Transparency = 35

    pcb_obj = doc.addObject("Part::Feature", "PCB_Placeholder")
    pcb_obj.Shape = pcb_vis
    pcb_obj.ViewObject.ShapeColor = (0.05, 0.45, 0.05)  # PCB green
    pcb_obj.ViewObject.Transparency = 0

    doc.recompute()

    # ── EXPORT STL FILES ──────────────────────────────────────────────────
    out_dir = "f:/Projects/skysweep32/hardware/enclosures"

    Part.export([bot_obj], f"{out_dir}/skysweep32_pro_case_bottom.stl")
    print(f"[OK] Exported: case_bottom.stl")

    Part.export([lid_obj], f"{out_dir}/skysweep32_pro_case_lid.stl")
    print(f"[OK] Exported: case_lid.stl")

    # ── RENDER VIEWS ──────────────────────────────────────────────────────
    view = FreeCADGui.activeDocument().activeView()

    # Isometric view — full assembly
    view.viewIsometric()
    view.fitAll()
    view.saveImage(f"{out_dir}/preview_assembly_iso.png", 1920, 1080, "Transparent")
    print(f"[OK] Rendered: preview_assembly_iso.png")

    # Top view (lid visible)
    view.viewTop()
    view.fitAll()
    view.saveImage(f"{out_dir}/preview_top.png", 1280, 720, "Transparent")
    print(f"[OK] Rendered: preview_top.png")

    # Bottom shell without lid, rotated to show interior
    lid_obj.Visibility = False
    pcb_obj.Visibility = True
    view.viewIsometric()
    view.fitAll()
    view.saveImage(f"{out_dir}/preview_interior.png", 1920, 1080, "Transparent")
    print(f"[OK] Rendered: preview_interior.png")

    # Restore lid visibility
    lid_obj.Visibility = True

    # Side view showing SMA holes
    view.viewRight()
    view.fitAll()
    view.saveImage(f"{out_dir}/preview_side_sma.png", 1280, 720, "Transparent")
    print(f"[OK] Rendered: preview_side_sma.png")

    print(f"\n[DONE] All files written to {out_dir}/")
    sys.exit(0)


try:
    generate()
except Exception as e:
    err_path = "f:/Projects/skysweep32/hardware/enclosures/fc_error.log"
    with open(err_path, "w") as f:
        f.write(str(e) + "\n\n" + traceback.format_exc())
    print(f"[ERROR] See {err_path}")
    sys.exit(1)
