import adsk.core
import adsk.fusion
import math
import time
import traceback

def mm(val: float) -> float:
    """Convert millimeters to Fusion internal units (centimeters)."""
    return val / 10.0

def w2s(sketch: adsk.fusion.Sketch, wx: float, wy: float, wz: float) -> adsk.core.Point3D:
    """Convert a 3D World coordinate (in mm) directly into 2D Sketch space."""
    pt_world = adsk.core.Point3D.create(mm(wx), mm(wy), mm(wz))
    pt_sk = sketch.modelToSketchSpace(pt_world)
    return adsk.core.Point3D.create(pt_sk.x, pt_sk.y, 0.0)

def draw_polygon_yz(sketch: adsk.fusion.Sketch, wx: float, yz_points: list):
    """Draw a closed polygon on a YZ-parallel sketch using true World (Y, Z) coordinates."""
    lines = sketch.sketchCurves.sketchLines
    pts = [w2s(sketch, wx, wy, wz) for (wy, wz) in yz_points]
    for i in range(len(pts)):
        lines.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

def get_profile_with_loops(sketch: adsk.fusion.Sketch, expected_loops: int) -> adsk.fusion.Profile:
    """Find the sketch profile with the specified number of loops (e.g., 2 for a ring with 1 hole)."""
    for i in range(sketch.profiles.count):
        prof = sketch.profiles.item(i)
        if prof.profileLoops.count == expected_loops:
            return prof
    return sketch.profiles.item(0)

def create_color(design: adsk.fusion.Design, name: str, r: int, g: int, b: int, opacity: int = 255):
    """Safely create or retrieve a custom appearance color across all Fusion versions."""
    try:
        appearances = design.appearances
        try:
            existing = appearances.itemByName(name)
            if existing:
                return existing
        except:
            pass

        app = adsk.core.Application.get()
        base_appear = None

        if appearances.count > 0:
            try:
                base_appear = appearances.item(0)
            except:
                pass

        if not base_appear:
            for i in range(app.materialLibraries.count):
                lib = app.materialLibraries.item(i)
                if lib.appearances.count > 0:
                    for candidate in ['Paint - Enamel Glossy (White)', 'Plastic - Matte (White)', 'Steel - Satin', 'Opaque - Matte (White)']:
                        try:
                            found = lib.appearances.itemByName(candidate)
                            if found:
                                base_appear = found
                                break
                        except:
                            pass
                    if not base_appear:
                        try:
                            base_appear = lib.appearances.item(0)
                        except:
                            pass
                if base_appear:
                    break

        if not base_appear:
            return None

        appear = appearances.addByCopy(base_appear, name)
        for idx in range(appear.appearanceProperties.count):
            prop = appear.appearanceProperties.item(idx)
            if prop.objectType == adsk.core.ColorProperty.classType():
                color_prop = adsk.core.ColorProperty.cast(prop)
                if color_prop and not color_prop.isReadOnly:
                    color_prop.value = adsk.core.Color.create(r, g, b, opacity)
                    break
        return appear
    except:
        return None

def apply_color(body: adsk.fusion.BRepBody, appearance: adsk.core.Appearance, opacity: float = 1.0):
    if body:
        if appearance:
            try:
                body.appearance = appearance
            except:
                pass
        if opacity < 1.0:
            try:
                body.opacity = opacity
            except:
                pass

def extrude_profile(comp: adsk.fusion.Component, profile, distance_mm: float, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation):
    extrudes = comp.features.extrudeFeatures
    ext_input = extrudes.createInput(profile, operation)
    ext_input.setDistanceExtent(False, adsk.core.ValueInput.createByReal(mm(distance_mm)))
    return extrudes.add(ext_input)

def offset_plane(comp: adsk.fusion.Component, base_plane, offset_mm: float):
    planes = comp.constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(base_plane, adsk.core.ValueInput.createByReal(mm(offset_mm)))
    return planes.add(plane_input)

def add_point(comp: adsk.fusion.Component, wx: float, wy: float, wz: float, name: str) -> adsk.fusion.ConstructionPoint:
    pts = comp.constructionPoints
    pt_in = pts.createInput()
    pt_in.setByPoint(adsk.core.Point3D.create(mm(wx), mm(wy), mm(wz)))
    cp = pts.add(pt_in)
    cp.name = name
    cp.isLightBulbOn = False
    return cp

def add_cyl_x(comp: adsk.fusion.Component, x_start: float, length_x: float, wy: float, wz: float, radius: float, name: str, color, opacity: float = 1.0):
    """Create a solid cylinder along the World X-axis centered at World (wy, wz)."""
    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk, x_start, wy, wz), mm(radius))
    ext = extrude_profile(comp, sk.profiles.item(0), length_x)
    body = ext.bodies.item(0)
    body.name = name
    apply_color(body, color, opacity)
    return body

def add_ring_x(comp: adsk.fusion.Component, x_start: float, length_x: float, out_y: float, out_z: float, r_outer: float, in_y: float, in_z: float, r_inner: float, name: str, color, operation=adsk.fusion.FeatureOperations.NewBodyFeatureOperation):
    """Create a concentric or eccentric ring along X without using CutFeatureOperation."""
    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk, x_start, out_y, out_z), mm(r_outer))
    sk.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk, x_start, in_y, in_z), mm(r_inner))
    ring_prof = get_profile_with_loops(sk, 2)
    ext = extrude_profile(comp, ring_prof, length_x, operation)
    if ext.bodies.count > 0:
        body = ext.bodies.item(0)
        if operation == adsk.fusion.FeatureOperations.NewBodyFeatureOperation:
            body.name = name
        apply_color(body, color)
        return body
    return None

def add_box_x(comp: adsk.fusion.Component, x_start: float, length_x: float, y1: float, z1: float, y2: float, z2: float, name: str, color, opacity: float = 1.0):
    """Create a rectangular box extruded along the World X-axis."""
    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(
        w2s(sk, x_start, y1, z1),
        w2s(sk, x_start, y2, z2)
    )
    ext = extrude_profile(comp, sk.profiles.item(0), length_x)
    body = ext.bodies.item(0)
    body.name = name
    apply_color(body, color, opacity)
    return body

def add_spur_gear_x(comp: adsk.fusion.Component, x_start: float, thickness_x: float, wy: float, wz: float, pitch_radius: float, num_teeth: int, name: str, color_gear, color_hub):
    """Create a toothed spur gear + central hub along the World X-axis."""
    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    r_root = pitch_radius - 1.15
    r_tip = pitch_radius + 0.95
    yz_pts = []
    for i in range(num_teeth):
        a0 = (i / num_teeth) * 2.0 * math.pi
        a1 = ((i + 0.18) / num_teeth) * 2.0 * math.pi
        a2 = ((i + 0.46) / num_teeth) * 2.0 * math.pi
        a3 = ((i + 0.64) / num_teeth) * 2.0 * math.pi
        yz_pts.append((wy + r_root * math.cos(a0), wz + r_root * math.sin(a0)))
        yz_pts.append((wy + r_tip * math.cos(a1), wz + r_tip * math.sin(a1)))
        yz_pts.append((wy + r_tip * math.cos(a2), wz + r_tip * math.sin(a2)))
        yz_pts.append((wy + r_root * math.cos(a3), wz + r_root * math.sin(a3)))
    draw_polygon_yz(sk, x_start, yz_pts)
    ext = extrude_profile(comp, sk.profiles.item(0), thickness_x)
    gear_body = ext.bodies.item(0)
    gear_body.name = name
    apply_color(gear_body, color_gear)

    hub_r = max(4.5, pitch_radius * 0.42)
    add_cyl_x(comp, x_start - 1.5, thickness_x + 3.0, wy, wz, hub_r, f'{name}_Hub', color_hub)
    return gear_body

def add_nema17_stator_x(comp: adsk.fusion.Component, x_mount_face: float, body_extends_positive_x: bool, wy: float, wz: float, name_prefix: str, col_black, col_alu):
    """Build stationary NEMA 17 Stepper Motor body (42x42mm frame)."""
    half = 21.0
    if body_extends_positive_x:
        add_box_x(comp, x_mount_face, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_FrontCap', col_alu)
        add_box_x(comp, x_mount_face + 7.0, 24.0, wy - half + 0.8, wz - half + 0.8, wy + half - 0.8, wz + half - 0.8, f'{name_prefix}_StatorStack', col_black)
        add_box_x(comp, x_mount_face + 31.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_RearCap', col_alu)
        add_cyl_x(comp, x_mount_face - 2.0, 2.0, wy, wz, 11.0, f'{name_prefix}_PilotBoss', col_alu)
    else:
        add_box_x(comp, x_mount_face - 7.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_FrontCap', col_alu)
        add_box_x(comp, x_mount_face - 31.0, 24.0, wy - half + 0.8, wz - half + 0.8, wy + half - 0.8, wz + half - 0.8, f'{name_prefix}_StatorStack', col_black)
        add_box_x(comp, x_mount_face - 38.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_RearCap', col_alu)
        add_cyl_x(comp, x_mount_face, 2.0, wy, wz, 11.0, f'{name_prefix}_PilotBoss', col_alu)

def add_belt_drive_x(comp: adsk.fusion.Component, x_start: float, width_x: float, y1: float, z1: float, y2: float, z2: float, r_pulley: float, name_prefix: str, col_pulley, col_belt):
    """Build 2 Timing Pulleys and a closed Timing Belt connecting (y1,z1) and (y2,z2)."""
    add_cyl_x(comp, x_start - 1.0, width_x + 2.0, y1, z1, r_pulley + 1.5, f'{name_prefix}_Pulley_1_Flange', col_pulley)
    add_cyl_x(comp, x_start - 1.0, width_x + 2.0, y2, z2, r_pulley + 1.5, f'{name_prefix}_Pulley_2_Flange', col_pulley)

    dy = y2 - y1
    dz = z2 - z1
    dist = math.hypot(dy, dz)
    ny = -dz / dist
    nz = dy / dist
    t = 1.8

    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    draw_polygon_yz(sk, x_start, [
        (y1 + ny * r_pulley, z1 + nz * r_pulley),
        (y2 + ny * r_pulley, z2 + nz * r_pulley),
        (y2 + ny * (r_pulley + t), z2 + nz * (r_pulley + t)),
        (y1 + ny * (r_pulley + t), z1 + nz * (r_pulley + t))
    ])
    draw_polygon_yz(sk, x_start, [
        (y1 - ny * r_pulley, z1 - nz * r_pulley),
        (y2 - ny * r_pulley, z2 - nz * r_pulley),
        (y2 - ny * (r_pulley + t), z2 - nz * (r_pulley + t)),
        (y1 - ny * (r_pulley + t), z1 - nz * (r_pulley + t))
    ])
    for i in range(sk.profiles.count):
        ext = extrude_profile(comp, sk.profiles.item(i), width_x)
        ext.bodies.item(0).name = f'{name_prefix}_TimingBelt_Span_{i + 1}'
        apply_color(ext.bodies.item(0), col_belt)

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root = design.rootComponent

        # Color Palette matching the Canon Finetech Nisca video & close-up screenshots
        col_steel = create_color(design, 'Nisca_Steel', 195, 202, 210)
        col_chrome = create_color(design, 'Nisca_Chrome_Block', 215, 222, 232)
        col_alu = create_color(design, 'Nisca_Aluminum', 205, 210, 218)
        col_brass_gear = create_color(design, 'Nisca_Brass_Gear', 220, 178, 62)
        col_dark_frame = create_color(design, 'Nisca_Channel_Grey', 95, 102, 112)
        col_dark_cam = create_color(design, 'Nisca_Dark_Cam', 45, 48, 55)
        col_tray_dark = create_color(design, 'Nisca_Tray_Charcoal', 48, 52, 58)
        col_chute_guide = create_color(design, 'Nisca_Chute_Silver', 160, 168, 175)
        col_black = create_color(design, 'Nisca_Black_Roller', 30, 33, 38)
        col_blue_cam = create_color(design, 'Nisca_Highlight_Blue', 72, 132, 202)
        col_blue_rotor = create_color(design, 'Nisca_Highlight_Blue_Light', 110, 168, 230)
        col_coupler_blue = create_color(design, 'Nisca_Coupler_Anodized', 35, 115, 210)
        col_white = create_color(design, 'Nisca_White_Roller', 242, 242, 246)
        col_pcb_green = create_color(design, 'Nisca_Sensor_PCB', 22, 145, 58)
        col_led_green = create_color(design, 'Nisca_Ready_LED', 40, 235, 80)
        col_sensor_red = create_color(design, 'Nisca_Sensor_LED', 220, 35, 40)
        col_stopper_amber = create_color(design, 'Nisca_Stopper_Guide', 230, 160, 35)
        col_diverter_orange = create_color(design, 'Nisca_Diverter_Gate', 235, 110, 30)
        col_paper = create_color(design, 'Nisca_Paper', 248, 250, 255)

        # Core Kinematic Parameters for the Off-Center Eccentric Punch Mechanism (in mm)
        punch_x_coords = [-120.0, -40.0, 40.0, 120.0]
        sensor_x_coords = [-80.0, 0.0, 80.0]

        Z_SHAFT = 49.0        # Fixed height of the continuous off-center rotating drive shaft (Y = 0)
        ECCENTRICITY = 4.0    # Off-center distance between shaft axis and stepped flange center (stroke = 2*e = 8.0 mm)
        Z_CAM_TDC = Z_SHAFT + ECCENTRICITY  # 53.0 mm at Top Dead Center (theta = 0)
        Z_WRIST_TDC = 34.0    # Clevis wrist pin height at Top Dead Center
        L_STRAP = Z_CAM_TDC - Z_WRIST_TDC   # 19.0 mm center-to-center length of the clevis strap

        # =====================================================================
        # 1. STATIONARY BASE FRAME & LINEAR RAILS (Grounded)
        # =====================================================================
        base_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        base_comp = base_occ.component
        base_comp.name = '01_Stationary_Frame_And_Rails'
        base_occ.isGrounded = True

        for side_x, suffix in [(-205.0, 'Left'), (195.0, 'Right')]:
            add_box_x(base_comp, side_x, 10.0, -110.0, -52.0, 42.0, 68.0, f'Side_Frame_{suffix}', col_dark_frame, opacity=0.28)

        add_cyl_x(base_comp, -222.0, 422.0, -8.0, -20.0, 4.5, 'Lateral_Lead_Screw', col_steel)
        add_cyl_x(base_comp, -200.0, 400.0, 14.0, -20.0, 4.5, 'Linear_Guide_Rod', col_steel)

        # =====================================================================
        # 2. REVERSIBLE SWITCHBACK ROLLERS & DIVERTER GATE
        # =====================================================================
        rollers_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        rollers_comp = rollers_occ.component
        rollers_comp.name = '02_Switchback_Rollers_And_Diverter'

        add_cyl_x(rollers_comp, -200.0, 428.0, -55.0, 11.0, 3.5, 'Upper_Switchback_Shaft', col_steel)
        add_cyl_x(rollers_comp, -200.0, 418.0, -55.0, -11.0, 3.5, 'Lower_Pinch_Shaft', col_steel)

        for rx in [-68.0, 32.0]:
            add_cyl_x(rollers_comp, rx, 36.0, -55.0, 11.0, 11.0, f'White_Switchback_Roller_{int(rx)}', col_white)
            add_cyl_x(rollers_comp, rx, 36.0, -55.0, -11.0, 11.0, f'Black_Pinch_Roller_{int(rx)}', col_black)

        pl_throat = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -155.0)
        sk_throat = rollers_comp.sketches.add(pl_throat)
        draw_polygon_yz(sk_throat, -155.0, [(-41.0, 4.5), (-15.0, 4.5), (-15.0, 6.5), (-41.0, 6.5)])
        draw_polygon_yz(sk_throat, -155.0, [(-41.0, -6.5), (-15.0, -6.5), (-15.0, -4.5), (-41.0, -4.5)])
        for i, gname in enumerate(['Upper_Throat_Guide', 'Lower_Throat_Guide']):
            ext_g = extrude_profile(rollers_comp, sk_throat.profiles.item(i), 310.0)
            ext_g.bodies.item(0).name = gname
            apply_color(ext_g.bodies.item(0), col_chute_guide, opacity=0.55)

        add_cyl_x(rollers_comp, -160.0, 372.0, -82.0, 4.0, 2.0, 'Diverter_Pivot_Shaft', col_steel)
        pl_div = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -150.0)
        sk_div = rollers_comp.sketches.add(pl_div)
        draw_polygon_yz(sk_div, -150.0, [(-82.0, 5.5), (-66.0, -1.5), (-68.0, -3.5), (-83.0, 2.5)])
        ext_div = extrude_profile(rollers_comp, sk_div.profiles.item(0), 300.0)
        ext_div.bodies.item(0).name = 'OneWay_Switchback_Diverter_Gate'
        apply_color(ext_div.bodies.item(0), col_diverter_orange)

        # =====================================================================
        # 3. PUNCH SLIDE UNIT CARRIAGE (C-Channel Die + Chrome Square Guide Blocks)
        # =====================================================================
        slide_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        slide_comp = slide_occ.component
        slide_comp.name = '03_Punch_Slide_Unit_Carriage'

        pl_chan = offset_plane(slide_comp, slide_comp.yZConstructionPlane, -170.0)
        sk_chan = slide_comp.sketches.add(pl_chan)
        draw_polygon_yz(sk_chan, -170.0, [
            (-14.0, -10.0), (15.0, -10.0), (15.0, 10.0), (-14.0, 10.0),
            (-14.0, 4.5), (10.0, 4.5), (10.0, -4.5), (-14.0, -4.5)
        ])
        ext_chan = extrude_profile(slide_comp, sk_chan.profiles.item(0), 340.0)
        chan_body = ext_chan.bodies.item(0)
        chan_body.name = 'C_Channel_Die_Beam'
        apply_color(chan_body, col_dark_frame)

        # Left and Right Carriage Gantry End-Plates supporting the Off-Center Cam Shaft (Z=49) & Stepper Motor (Y=18, Z=25)
        add_box_x(slide_comp, -170.0, 6.0, -10.0, 10.0, 15.0, 60.0, 'Carriage_Left_Bearing_Plate', col_dark_frame)
        add_box_x(slide_comp, 164.0, 6.0, -10.0, 10.0, 40.0, 60.0, 'Carriage_Right_Motor_Plate', col_dark_frame)

        # Under-carriage Bearing Blocks riding on the Lead Screw & Guide Rod
        for bx in [-140.0, 110.0]:
            pl_bb = offset_plane(slide_comp, slide_comp.yZConstructionPlane, bx)
            sk_bb = slide_comp.sketches.add(pl_bb)
            sk_bb.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_bb, bx, -14.0, -26.0),
                w2s(sk_bb, bx, 20.0, -10.0)
            )
            extrude_profile(slide_comp, sk_bb.profiles.item(0), 30.0, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        # 4 Metallic Chrome Square Guide Blocks with central pin bore (drawn as 2-loop profiles without CutFeatureOperation)
        pl_top = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 10.0)
        for idx, px in enumerate(punch_x_coords):
            sk_blk = slide_comp.sketches.add(pl_top)
            sk_blk.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_blk, px - 8.5, -8.5, 10.0),
                w2s(sk_blk, px + 8.5, 8.5, 10.0)
            )
            sk_blk.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_blk, px, 0.0, 10.0), mm(3.8))
            prof_blk = get_profile_with_loops(sk_blk, 2)
            ext_blk = extrude_profile(slide_comp, prof_blk, 13.0, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            blk_body = ext_blk.bodies.item(0)
            blk_body.name = f'Chrome_Punch_Guide_Block_{idx + 1}'
            apply_color(blk_body, col_blue_rotor if idx == 2 else col_chrome)

            # Top circular boss collar on each Square Guide Block (Z = 23.0 to 24.5 mm)
            pl_boss = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 23.0)
            sk_boss = slide_comp.sketches.add(pl_boss)
            sk_boss.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_boss, px, 0.0, 23.0), mm(5.6))
            sk_boss.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_boss, px, 0.0, 23.0), mm(3.8))
            prof_boss = get_profile_with_loops(sk_boss, 2)
            ext_boss = extrude_profile(slide_comp, prof_boss, 1.5, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            ext_boss.bodies.item(0).name = f'Guide_Block_Collar_{idx + 1}'
            apply_color(ext_boss.bodies.item(0), col_blue_rotor if idx == 2 else col_chrome)

        # =====================================================================
        # 4A. ONE-PIECE CONTINUOUS DRIVE SHAFT & FIXED STEPPED ECCENTRIC FLANGES
        # =====================================================================
        cam_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_comp = cam_occ.component
        cam_comp.name = '04A_Continuous_Shaft_And_Stepped_Flanges'

        # 1) Single, unbroken, continuous cylindrical steel rod from X = -175 to +182 mm at (Y = 0, Z = 49.0 mm)
        add_cyl_x(cam_comp, -175.0, 357.0, 0.0, Z_SHAFT, 4.0, 'Upper_OffCenter_Drive_Shaft', col_steel)

        # 2) 4 Fixed Eccentric Stepped Cam Flanges mounted around the continuous shaft (NO cuts on the shaft!)
        # At Top Dead Center (theta = 0), each Stepped Flange center is at (Y = 0, Z = 53.0 mm), while its shaft bore is at (Y = 0, Z = 49.0 mm)
        for idx, px in enumerate(punch_x_coords):
            rotor_color = col_blue_rotor if idx == 2 else col_dark_cam

            # Part A: Cylindrical Bearing Journal (X = px - 6.0 to px + 4.0 mm, width 10.0 mm, R_out = 11.5 mm, R_shaft_bore = 4.0 mm)
            # The Clevis Strap Ring rides freely on this cylindrical journal!
            add_ring_x(
                cam_comp, px - 6.0, 10.0,
                0.0, Z_CAM_TDC, 11.5,
                0.0, Z_SHAFT, 4.0,
                f'Eccentric_Cam_Journal_{idx + 1}', rotor_color,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )

            # Part B: Stepped Retaining Flange Shoulder on +X side (X = px + 4.0 to px + 8.5 mm, width 4.5 mm, R_out = 13.8 mm, R_shaft_bore = 4.0 mm)
            add_ring_x(
                cam_comp, px + 4.0, 4.5,
                0.0, Z_CAM_TDC, 13.8,
                0.0, Z_SHAFT, 4.0,
                f'Eccentric_Stepped_Flange_{idx + 1}', rotor_color,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )

            # Part C: Subtle Rear Retaining Collar on -X side (X = px - 7.5 to px - 6.0 mm, width 1.5 mm, R_out = 12.8 mm, R_shaft_bore = 4.0 mm)
            add_ring_x(
                cam_comp, px - 7.5, 1.5,
                0.0, Z_CAM_TDC, 12.8,
                0.0, Z_SHAFT, 4.0,
                f'Eccentric_Rear_Lip_{idx + 1}', rotor_color,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )

        # 3) 28-Tooth Driven Bull Gear keyed to the right end of the Continuous Drive Shaft (X = +173..+180 mm)
        add_spur_gear_x(cam_comp, 173.0, 7.0, 0.0, Z_SHAFT, 20.0, 28, 'Cam_Shaft_Driven_Bull_Gear', col_brass_gear, col_steel)

        # =====================================================================
        # 4B. FREE-MOVING ECCENTRIC CLEVIS STRAP RINGS (Ride on Stepped Flange Journal)
        # =====================================================================
        strap_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        strap_comp = strap_occ.component
        strap_comp.name = '04B_Eccentric_Clevis_Straps'

        for idx, px in enumerate(punch_x_coords):
            strap_color = col_blue_cam if idx == 2 else col_dark_cam

            # Upper Circular Strap Ring riding around the R=11.5mm Eccentric Cam Journal (X = px - 6.0 to px + 4.0 mm)
            add_ring_x(
                strap_comp, px - 6.0, 10.0,
                0.0, Z_CAM_TDC, 15.0,
                0.0, Z_CAM_TDC, 11.55,
                f'Eccentric_Strap_Ring_{idx + 1}', strap_color,
                adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )

            # Two Bottom Clevis Fork Ears hanging down from the ring (Z = 40.5 down to 31.0 mm) straddling the Silver Punch Pin
            # Drawn with the Wrist Pin hole (R = 1.4 mm at Y = 0, Z = 34.0 mm) directly inside the sketch!
            for ear_x, ear_side in [(px - 6.0, 'Left'), (px + 1.5, 'Right')]:
                pl_ear = offset_plane(strap_comp, strap_comp.yZConstructionPlane, ear_x)
                sk_ear = strap_comp.sketches.add(pl_ear)
                draw_polygon_yz(sk_ear, ear_x, [
                    (-5.8, 40.5),
                    (5.8, 40.5),
                    (3.8, 30.8),
                    (-3.8, 30.8)
                ])
                sk_ear.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_ear, ear_x, 0.0, Z_WRIST_TDC), mm(1.4))
                ear_prof = get_profile_with_loops(sk_ear, 2)
                ext_ear = extrude_profile(strap_comp, ear_prof, 2.5, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
                ear_body = ext_ear.bodies.item(0)
                ear_body.name = f'Clevis_Fork_Ear_{idx + 1}_{ear_side}'
                apply_color(ear_body, strap_color)

        # =====================================================================
        # 5. VERTICAL SILVER PUNCH PINS & CLEVIS WRIST PINS (4 Stations)
        # =====================================================================
        pins_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        pins_comp = pins_occ.component
        pins_comp.name = '05_Vertical_Punch_Pins'

        pl_pin_base = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 3.5)
        sk_pins = pins_comp.sketches.add(pl_pin_base)
        for px in punch_x_coords:
            sk_pins.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_pins, px, 0.0, 3.5), mm(3.7))
        for i in range(sk_pins.profiles.count):
            ext_pin = extrude_profile(pins_comp, sk_pins.profiles.item(i), 28.0)
            ext_pin.bodies.item(0).name = f'Silver_Punch_Pin_{i + 1}'
            apply_color(ext_pin.bodies.item(0), col_chrome)

        for idx, px in enumerate(punch_x_coords):
            add_box_x(pins_comp, px - 3.3, 4.6, -3.5, 31.5, 3.5, 37.0, f'Punch_Pin_Clevis_Tang_{idx + 1}', col_chrome)
            add_cyl_x(pins_comp, px - 6.2, 10.4, 0.0, Z_WRIST_TDC, 1.4, f'Clevis_Wrist_Pin_{idx + 1}', col_steel)

        # =====================================================================
        # 6. REAR PAPER POSITION & SKEW CHECK MECHANISM
        # =====================================================================
        check_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        check_comp = check_occ.component
        check_comp.name = '06_Rear_Position_Check_Mechanism'

        pl_rpcb = offset_plane(check_comp, check_comp.xYConstructionPlane, -7.0)
        sk_rpcb = check_comp.sketches.add(pl_rpcb)
        sk_rpcb.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_rpcb, -110.0, 15.0, -7.0),
            w2s(sk_rpcb, 165.0, 38.0, -7.0)
        )
        ext_rpcb = extrude_profile(check_comp, sk_rpcb.profiles.item(0), 2.5)
        ext_rpcb.bodies.item(0).name = 'Rear_Position_Verification_PCB'
        apply_color(ext_rpcb.bodies.item(0), col_pcb_green)

        add_cyl_x(check_comp, -95.0, 190.0, 14.0, 12.0, 1.8, 'Stopper_Lever_Pivot_Shaft', col_steel)

        for idx, sx in enumerate(sensor_x_coords):
            pl_lev = offset_plane(check_comp, check_comp.yZConstructionPlane, sx - 2.5)
            sk_lev = check_comp.sketches.add(pl_lev)
            draw_polygon_yz(sk_lev, sx - 2.5, [
                (7.5, -3.5), (10.5, -3.5), (12.5, 1.5), (29.0, 1.5),
                (29.0, 4.5), (15.5, 5.5), (15.5, 13.5), (11.5, 13.5), (7.5, 4.0)
            ])
            ext_lev = extrude_profile(check_comp, sk_lev.profiles.item(0), 5.0)
            ext_lev.bodies.item(0).name = f'Position_Stopper_Trigger_Lever_{idx + 1}'
            apply_color(ext_lev.bodies.item(0), col_stopper_amber)

            for arm_offset, arm_side in [(-6.5, 'L'), (3.5, 'R')]:
                add_box_x(check_comp, sx + arm_offset, 3.0, 21.0, -4.5, 33.0, 8.5, f'Optical_Interrupter_{idx + 1}_{arm_side}', col_black)

            pl_led = offset_plane(check_comp, check_comp.xYConstructionPlane, -4.5)
            sk_led = check_comp.sketches.add(pl_led)
            sk_led.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_led, sx + 14.0, 30.0, -4.5), mm(2.2))
            ext_led = extrude_profile(check_comp, sk_led.profiles.item(0), 2.5)
            ext_led.bodies.item(0).name = f'Position_Ready_LED_{idx + 1}'
            apply_color(ext_led.bodies.item(0), col_led_green)

        pl_lat = offset_plane(check_comp, check_comp.xYConstructionPlane, -4.5)
        sk_lat = check_comp.sketches.add(pl_lat)
        sk_lat.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_lat, 148.5, 22.0, -4.5), mm(4.5))
        ext_lat = extrude_profile(check_comp, sk_lat.profiles.item(0), 3.0)
        ext_lat.bodies.item(0).name = 'Side_Edge_Optical_Sensor'
        apply_color(ext_lat.bodies.item(0), col_sensor_red)

        # =====================================================================
        # 7. UPPER INPUT PAPER TRAY & PICK-UP ROLLER (310 mm wide for 297 mm A4)
        # =====================================================================
        in_tray_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        in_tray_comp = in_tray_occ.component
        in_tray_comp.name = '07_Upper_Input_Tray_And_PickRoller'

        pl_ut = offset_plane(in_tray_comp, in_tray_comp.yZConstructionPlane, -155.0)
        sk_ut = in_tray_comp.sketches.add(pl_ut)
        draw_polygon_yz(sk_ut, -155.0, [
            (-280.0, 20.0), (-115.0, 20.0), (-68.0, 1.0),
            (-68.0, 3.5), (-115.0, 23.0), (-280.0, 23.0)
        ])
        ext_ut = extrude_profile(in_tray_comp, sk_ut.profiles.item(0), 310.0)
        ext_ut.bodies.item(0).name = 'Upper_Input_Tray_Bed'
        apply_color(ext_ut.bodies.item(0), col_tray_dark)

        for gx, gside in [(-155.0, 'Left'), (152.0, 'Right')]:
            add_box_x(in_tray_comp, gx, 3.0, -275.0, 23.0, -120.0, 36.0, f'Upper_Tray_Side_Guide_{gside}', col_dark_frame)

        add_cyl_x(in_tray_comp, -160.0, 388.0, -175.0, 37.0, 3.0, 'Pickup_Roller_Shaft', col_steel)
        for prx in [-55.0, 25.0]:
            add_cyl_x(in_tray_comp, prx, 30.0, -175.0, 37.0, 11.5, f'Sheet_Pickup_Roller_{int(prx)}', col_black)

        # =====================================================================
        # 8. LOWER OUTPUT TRAY & RETURN CHUTE (310 mm wide for 297 mm A4)
        # =====================================================================
        out_tray_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        out_tray_comp = out_tray_occ.component
        out_tray_comp.name = '08_Lower_Output_Tray_And_Chute'

        pl_lt = offset_plane(out_tray_comp, out_tray_comp.yZConstructionPlane, -155.0)
        sk_lt = out_tray_comp.sketches.add(pl_lt)
        draw_polygon_yz(sk_lt, -155.0, [
            (-68.0, -4.5), (-68.0, -7.5), (-125.0, -45.0), (-290.0, -45.0),
            (-290.0, -32.0), (-286.0, -32.0), (-286.0, -42.0), (-125.0, -42.0)
        ])
        ext_lt = extrude_profile(out_tray_comp, sk_lt.profiles.item(0), 310.0)
        ext_lt.bodies.item(0).name = 'Lower_Switchback_Output_Tray'
        apply_color(ext_lt.bodies.item(0), col_tray_dark)

        pl_rc = offset_plane(out_tray_comp, out_tray_comp.yZConstructionPlane, -150.0)
        sk_rc = out_tray_comp.sketches.add(pl_rc)
        draw_polygon_yz(sk_rc, -150.0, [(-80.0, -3.5), (-125.0, -33.0), (-125.0, -31.0), (-80.0, -1.5)])
        ext_rc = extrude_profile(out_tray_comp, sk_rc.profiles.item(0), 300.0)
        ext_rc.bodies.item(0).name = 'Lower_Return_Chute_Roof'
        apply_color(ext_rc.bodies.item(0), col_chute_guide, opacity=0.5)

        # =====================================================================
        # 9. PAPER SHEETS AT ALL 3 STAGES (297 mm wide A4, Zero Cut Operations!)
        # =====================================================================
        paper_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        paper_comp = paper_occ.component
        paper_comp.name = '09_Paper_Flow_Stages'

        # Stage 1: Input Stack in Upper Tray
        pl_p1 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, 23.0)
        sk_p1 = paper_comp.sketches.add(pl_p1)
        sk_p1.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p1, -148.5, -275.0, 23.0),
            w2s(sk_p1, 148.5, -120.0, 23.0)
        )
        ext_p1 = extrude_profile(paper_comp, sk_p1.profiles.item(0), 2.5)
        ext_p1.bodies.item(0).name = 'Stage1_Upper_Tray_Paper_Stack'
        apply_color(ext_p1.bodies.item(0), col_paper)

        # Stage 2: Sheet Registered Inside Punch Throat
        pl_p2 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, -0.3)
        sk_p2 = paper_comp.sketches.add(pl_p2)
        sk_p2.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p2, -148.5, -135.0, -0.3),
            w2s(sk_p2, 148.5, 7.5, -0.3)
        )
        ext_p2 = extrude_profile(paper_comp, sk_p2.profiles.item(0), 0.6)
        ext_p2.bodies.item(0).name = 'Stage2_Sheet_At_Punch_Registration'
        apply_color(ext_p2.bodies.item(0), col_paper, opacity=0.85)

        # Stage 3: Punched Sheet in Lower Output Tray (Rectangle + 4 Holes in same sketch -> 5 loops)
        pl_p3 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, -42.0)
        sk_p3 = paper_comp.sketches.add(pl_p3)
        sk_p3.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p3, -148.5, -284.0, -42.0),
            w2s(sk_p3, 148.5, -134.0, -42.0)
        )
        for px in punch_x_coords:
            sk_p3.sketchCurves.sketchCircles.addByCenterRadius(
                w2s(sk_p3, px, -144.0, -42.0), mm(3.2)
            )
        p3_prof = get_profile_with_loops(sk_p3, 5)
        ext_p3 = extrude_profile(paper_comp, p3_prof, 0.8)
        p3_body = ext_p3.bodies.item(0)
        p3_body.name = 'Stage3_Lower_Tray_Punched_Sheet'
        apply_color(p3_body, col_paper)

        # =====================================================================
        # 10. LATERAL LEAD-SCREW STEPPER DRIVE (Left Frame Side)
        # =====================================================================
        lat_drive_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        lat_drive_comp = lat_drive_occ.component
        lat_drive_comp.name = '10_Lateral_LeadScrew_Stepper_Drive'

        add_box_x(lat_drive_comp, -242.0, 4.0, -30.0, -42.0, 14.0, 2.0, 'LeadScrew_Motor_Mount_Plate', col_dark_frame)
        for sy, sz in [(-25.0, -37.0), (9.0, -37.0), (-25.0, -3.0), (9.0, -3.0)]:
            add_cyl_x(lat_drive_comp, -238.0, 33.0, sy, sz, 2.5, 'Motor_Standoff_Pillar', col_alu)
        add_cyl_x(lat_drive_comp, -232.0, 20.0, -8.0, -20.0, 9.5, 'Flexible_Shaft_Coupler', col_coupler_blue)
        add_nema17_stator_x(lat_drive_comp, -242.0, False, -8.0, -20.0, 'Lateral_Reg_Stepper', col_black, col_alu)
        add_cyl_x(lat_drive_comp, -242.0, 22.0, -8.0, -20.0, 2.5, 'Lateral_Reg_Stepper_Shaft', col_steel)

        # =====================================================================
        # 11A & 11B. CAM PUNCH STEPPER MOTOR STATOR & SPINNING ROTOR/PINION GEAR
        # =====================================================================
        Y_CAM_MOTOR = 18.0
        Z_CAM_MOTOR = 25.0

        cam_stator_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_stator_comp = cam_stator_occ.component
        cam_stator_comp.name = '11A_Cam_Punch_Motor_Stator'
        add_nema17_stator_x(cam_stator_comp, 164.0, False, Y_CAM_MOTOR, Z_CAM_MOTOR, 'Punch_Cam_Stepper', col_black, col_alu)

        cam_rotor_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_rotor_comp = cam_rotor_occ.component
        cam_rotor_comp.name = '11B_Cam_Motor_Rotor_And_Pinion'
        add_cyl_x(cam_rotor_comp, 164.0, 20.0, Y_CAM_MOTOR, Z_CAM_MOTOR, 2.5, 'Cam_Motor_Output_Shaft', col_steel)
        add_spur_gear_x(cam_rotor_comp, 173.0, 7.0, Y_CAM_MOTOR, Z_CAM_MOTOR, 10.0, 14, 'Cam_Motor_14T_Pinion_Gear', col_brass_gear, col_steel)

        # =====================================================================
        # 12. ROLLER STEPPER DRIVE, 3-GEAR TRAIN & PICKUP TIMING BELT
        # =====================================================================
        roller_drive_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        roller_drive_comp = roller_drive_occ.component
        roller_drive_comp.name = '12_Roller_And_Belt_Drive_System'

        add_nema17_stator_x(roller_drive_comp, 195.0, False, -80.0, -11.0, 'Switchback_Roller_Stepper', col_black, col_alu)
        add_cyl_x(roller_drive_comp, 195.0, 24.0, -80.0, -11.0, 2.5, 'Switchback_Motor_Shaft', col_steel)
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -80.0, -11.0, 14.0, 18, 'Roller_Motor_Drive_Gear', col_brass_gear, col_steel)
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -55.0, -11.0, 11.0, 15, 'Lower_Pinch_Transfer_Gear', col_brass_gear, col_steel)
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -55.0, 11.0, 11.0, 15, 'Upper_Switchback_Driven_Gear', col_brass_gear, col_steel)
        add_belt_drive_x(roller_drive_comp, 219.0, 6.0, -55.0, 11.0, -175.0, 37.0, 7.5, 'Pickup_Roller_Drive', col_alu, col_black)

        # =====================================================================
        # 13. DIVERTER GATE ROTARY SOLENOID ACTUATOR
        # =====================================================================
        sol_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        sol_comp = sol_occ.component
        sol_comp.name = '13_Diverter_Gate_Solenoid'

        add_cyl_x(sol_comp, 205.0, 18.0, -82.0, 4.0, 9.0, 'Diverter_Rotary_Solenoid_Body', col_coupler_blue)
        add_cyl_x(sol_comp, 223.0, 3.0, -82.0, 4.0, 5.0, 'Solenoid_Armature_Hub', col_steel)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

        # =====================================================================