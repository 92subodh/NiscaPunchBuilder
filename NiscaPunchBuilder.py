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
    """Create a cylinder along the World X-axis centered at World (wy, wz)."""
    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    sk.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk, x_start, wy, wz), mm(radius))
    ext = extrude_profile(comp, sk.profiles.item(0), length_x)
    body = ext.bodies.item(0)
    body.name = name
    apply_color(body, color, opacity)
    return body

def add_tube_x(comp: adsk.fusion.Component, x_start: float, length_x: float, wy: float, wz: float, r_outer: float, r_inner: float, name: str, color, opacity: float = 1.0):
    """Create a hollow tube along the World X-axis by extruding outer cylinder then cutting inner bore."""
    body = add_cyl_x(comp, x_start, length_x, wy, wz, r_outer, name, color, opacity)
    pl_cut = offset_plane(comp, comp.yZConstructionPlane, x_start - 0.5)
    sk_cut = comp.sketches.add(pl_cut)
    sk_cut.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_cut, x_start - 0.5, wy, wz), mm(r_inner))
    extrude_profile(comp, sk_cut.profiles.item(0), length_x + 1.0, adsk.fusion.FeatureOperations.CutFeatureOperation)
    return body

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
        col_blue_cam = create_color(design, 'Nisca_Highlight_Blue', 78, 138, 205)
        col_blue_rotor = create_color(design, 'Nisca_Highlight_Blue_Light', 105, 162, 225)
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

        Z_SHAFT = 49.0        # Fixed height of the off-center rotating drive shaft (Y = 0)
        ECCENTRICITY = 4.0    # Off-center distance between shaft axis and cam rotor center (stroke = 2*e = 8.0 mm)
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

        pl_throat = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -135.0)
        sk_throat = rollers_comp.sketches.add(pl_throat)
        draw_polygon_yz(sk_throat, -135.0, [(-41.0, 4.5), (-15.0, 4.5), (-15.0, 6.5), (-41.0, 6.5)])
        draw_polygon_yz(sk_throat, -135.0, [(-41.0, -6.5), (-15.0, -6.5), (-15.0, -4.5), (-41.0, -4.5)])
        for i, gname in enumerate(['Upper_Throat_Guide', 'Lower_Throat_Guide']):
            ext_g = extrude_profile(rollers_comp, sk_throat.profiles.item(i), 270.0)
            ext_g.bodies.item(0).name = gname
            apply_color(ext_g.bodies.item(0), col_chute_guide, opacity=0.55)

        add_cyl_x(rollers_comp, -140.0, 352.0, -82.0, 4.0, 2.0, 'Diverter_Pivot_Shaft', col_steel)
        pl_div = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -130.0)
        sk_div = rollers_comp.sketches.add(pl_div)
        draw_polygon_yz(sk_div, -130.0, [(-82.0, 5.5), (-66.0, -1.5), (-68.0, -3.5), (-83.0, 2.5)])
        ext_div = extrude_profile(rollers_comp, sk_div.profiles.item(0), 260.0)
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

        # 4 Metallic Chrome Square Guide Blocks (matching close-up images 1-5)
        pl_top = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 10.0)
        sk_blocks = slide_comp.sketches.add(pl_top)
        for px in punch_x_coords:
            sk_blocks.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_blocks, px - 8.5, -8.5, 10.0),
                w2s(sk_blocks, px + 8.5, 8.5, 10.0)
            )
        for i in range(sk_blocks.profiles.count):
            ext_blk = extrude_profile(slide_comp, sk_blocks.profiles.item(i), 13.0, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
            blk_body = ext_blk.bodies.item(0)
            blk_body.name = f'Chrome_Punch_Guide_Block_{i + 1}'
            apply_color(blk_body, col_blue_rotor if i == 2 else col_chrome)

        # Top circular boss collar on each Square Guide Block (Z = 23.0 to 24.5 mm)
        pl_boss = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 23.0)
        sk_boss = slide_comp.sketches.add(pl_boss)
        for px in punch_x_coords:
            sk_boss.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_boss, px, 0.0, 23.0), mm(5.6))
        for i in range(sk_boss.profiles.count):
            extrude_profile(slide_comp, sk_boss.profiles.item(i), 1.5, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        # Cut 4 Vertical Punch & Die Bores (Dia 7.6 mm) through Guide Blocks and C-Channel Die at Y = 0
        pl_cut = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -15.0)
        sk_holes = slide_comp.sketches.add(pl_cut)
        for px in punch_x_coords:
            sk_holes.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_holes, px, 0.0, -15.0), mm(3.8))
        for i in range(sk_holes.profiles.count):
            extrude_profile(slide_comp, sk_holes.profiles.item(i), 45.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # Cut 3 Rear Windows through the back of the C-Channel for the Position-Check Levers
        pl_slot = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -4.0)
        sk_slot = slide_comp.sketches.add(pl_slot)
        for sx in sensor_x_coords:
            sk_slot.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_slot, sx - 5.0, 6.0, -4.0),
                w2s(sk_slot, sx + 5.0, 18.0, -4.0)
            )
        for i in range(sk_slot.profiles.count):
            extrude_profile(slide_comp, sk_slot.profiles.item(i), 12.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # =====================================================================
        # 4A. OFF-CENTER DRIVE SHAFT, 4 STEPPED ECCENTRIC CAM ROTORS & BULL GEAR
        # =====================================================================
        cam_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_comp = cam_occ.component
        cam_comp.name = '04A_OffCenter_Shaft_And_Eccentric_Rotors'

        # Main Rotating Drive Shaft along X at (Y = 0, Z = 49.0 mm), Dia 8.0 mm (Radius 4.0 mm)
        add_cyl_x(cam_comp, -174.0, 358.0, 0.0, Z_SHAFT, 4.0, 'Upper_OffCenter_Drive_Shaft', col_steel)

        # 4 Stepped Eccentric Cam Rotors keyed off-center onto the Drive Shaft
        # At Top Dead Center (theta = 0), rotor center is at (Y = 0, Z = 53.0 mm) -> +4.0 mm above the shaft!
        for idx, px in enumerate(punch_x_coords):
            rotor_color = col_blue_rotor if idx == 2 else col_dark_cam

            # 1) Inner Bearing Journal inside the Clevis Strap Ring: X = px-5.5 to px+4.5 mm (width 10 mm), R = 11.5 mm
            journal = add_cyl_x(cam_comp, px - 5.5, 10.0, 0.0, Z_CAM_TDC, 11.5, f'Eccentric_Cam_Journal_{idx + 1}', rotor_color)

            # 2) Stepped Front Flange on +X side: X = px+4.5 to px+10.0 mm (width 5.5 mm), R = 11.5 mm
            flange = add_cyl_x(cam_comp, px + 4.5, 5.5, 0.0, Z_CAM_TDC, 11.5, f'Eccentric_Stepped_Flange_{idx + 1}', rotor_color)

            # 3) Cut the horizontal U-slot on the Stepped Front Flange where the off-center shaft passes through (matching screenshots!)
            pl_uslot = offset_plane(cam_comp, cam_comp.yZConstructionPlane, px + 4.4)
            sk_uslot = cam_comp.sketches.add(pl_uslot)
            sk_uslot.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_uslot, px + 4.4, -14.0, Z_SHAFT - 4.1),
                w2s(sk_uslot, px + 4.4, 2.0, Z_SHAFT + 4.1)
            )
            extrude_profile(cam_comp, sk_uslot.profiles.item(0), 6.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

            # 4) Cut the molded front pocket recess on the +X face of the Stepped Flange (matching screenshots!)
            pl_pock = offset_plane(cam_comp, cam_comp.yZConstructionPlane, px + 8.2)
            sk_pock = cam_comp.sketches.add(pl_pock)
            sk_pock.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_pock, px + 8.2, 0.0, Z_CAM_TDC + 1.5), mm(7.2))
            extrude_profile(cam_comp, sk_pock.profiles.item(0), 2.5, adsk.fusion.FeatureOperations.CutFeatureOperation)

            # 5) Cross-Pin Locking Hole on the shaft at X = px + 6.5 mm (visible in all 5 close-up frames!)
            pl_pinhole = offset_plane(cam_comp, cam_comp.xZConstructionPlane, -10.0)
            sk_pinhole = cam_comp.sketches.add(pl_pinhole)
            sk_pinhole.sketchCurves.sketchCircles.addByCenterRadius(
                w2s(sk_pinhole, px + 6.5, -10.0, Z_SHAFT), mm(1.3)
            )
            extrude_profile(cam_comp, sk_pinhole.profiles.item(0), 20.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # 28-Tooth Driven Bull Gear keyed to the right end of the Off-Center Cam Shaft (X = +173..+180 mm)
        add_spur_gear_x(cam_comp, 173.0, 7.0, 0.0, Z_SHAFT, 20.0, 28, 'Cam_Shaft_Driven_Bull_Gear', col_brass_gear, col_steel)

        # =====================================================================
        # 4B. OUTER ECCENTRIC CLEVIS STRAPS (Collar Ring + 2 Bottom Fork Ears)
        # =====================================================================
        strap_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        strap_comp = strap_occ.component
        strap_comp.name = '04B_Eccentric_Clevis_Straps'

        for idx, px in enumerate(punch_x_coords):
            strap_color = col_blue_cam if idx == 2 else col_dark_cam

            # Upper Circular Strap Ring wrapping around the Eccentric Cam Journal (R_out = 15.0 mm, R_in = 11.55 mm)
            # Spans X = px - 5.5 to px + 4.5 mm (width 10.0 mm)
            add_tube_x(strap_comp, px - 5.5, 10.0, 0.0, Z_CAM_TDC, 15.0, 11.55, f'Eccentric_Strap_Ring_{idx + 1}', strap_color)

            # Two Bottom Clevis Fork Ears hanging down from the ring (Z = 40.5 down to 31.0 mm) straddling the Silver Punch Pin
            # Left Ear: X = px - 5.5 to px - 3.0 mm | Right Ear: X = px + 2.0 to px + 4.5 mm
            for ear_x, ear_side in [(px - 5.5, 'Left'), (px + 2.0, 'Right')]:
                pl_ear = offset_plane(strap_comp, strap_comp.yZConstructionPlane, ear_x)
                sk_ear = strap_comp.sketches.add(pl_ear)
                draw_polygon_yz(sk_ear, ear_x, [
                    (-5.8, 40.5),
                    (5.8, 40.5),
                    (3.8, 31.0),
                    (-3.8, 31.0)
                ])
                ext_ear = extrude_profile(strap_comp, sk_ear.profiles.item(0), 2.5)
                ear_body = ext_ear.bodies.item(0)
                ear_body.name = f'Clevis_Fork_Ear_{idx + 1}_{ear_side}'
                apply_color(ear_body, strap_color)

            # Cut the Clevis Wrist-Pin Bore (Dia 2.8 mm) through both Fork Ears at (Y = 0, Z = 34.0 mm)
            pl_wbore = offset_plane(strap_comp, strap_comp.yZConstructionPlane, px - 6.0)
            sk_wbore = strap_comp.sketches.add(pl_wbore)
            sk_wbore.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_wbore, px - 6.0, 0.0, Z_WRIST_TDC), mm(1.4))
            extrude_profile(strap_comp, sk_wbore.profiles.item(0), 11.5, adsk.fusion.FeatureOperations.CutFeatureOperation)

        # =====================================================================
        # 5. VERTICAL SILVER PUNCH PINS & CLEVIS WRIST PINS (4 Stations)
        # =====================================================================
        pins_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        pins_comp = pins_occ.component
        pins_comp.name = '05_Vertical_Punch_Pins'

        # Main cylindrical silver punch pins (Dia 7.4 mm, Z = +3.5 mm to +31.5 mm at TDC)
        pl_pin_base = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 3.5)
        sk_pins = pins_comp.sketches.add(pl_pin_base)
        for px in punch_x_coords:
            sk_pins.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_pins, px, 0.0, 3.5), mm(3.7))
        for i in range(sk_pins.profiles.count):
            ext_pin = extrude_profile(pins_comp, sk_pins.profiles.item(i), 28.0)
            ext_pin.bodies.item(0).name = f'Silver_Punch_Pin_{i + 1}'
            apply_color(ext_pin.bodies.item(0), col_chrome)

        # Upper Clevis Tang on each Punch Pin (fits between the 2 Clevis Fork Ears, Z = 31.5 to 37.0 mm)
        for idx, px in enumerate(punch_x_coords):
            add_box_x(pins_comp, px - 2.9, 4.8, -3.5, 31.5, 3.5, 37.0, f'Punch_Pin_Clevis_Tang_{idx + 1}', col_chrome)
            # Horizontal Silver Wrist Pin (Dia 2.8 mm) joining the Clevis Fork Ears to the Punch Pin at Z = 34.0 mm
            add_cyl_x(pins_comp, px - 5.6, 10.2, 0.0, Z_WRIST_TDC, 1.4, f'Clevis_Wrist_Pin_{idx + 1}', col_steel)

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
        sk_lat.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_lat, 105.0, 22.0, -4.5), mm(4.5))
        ext_lat = extrude_profile(check_comp, sk_lat.profiles.item(0), 3.0)
        ext_lat.bodies.item(0).name = 'Side_Edge_Optical_Sensor'
        apply_color(ext_lat.bodies.item(0), col_sensor_red)

        # =====================================================================
        # 7. UPPER INPUT PAPER TRAY & PICK-UP ROLLER
        # =====================================================================
        in_tray_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        in_tray_comp = in_tray_occ.component
        in_tray_comp.name = '07_Upper_Input_Tray_And_PickRoller'

        pl_ut = offset_plane(in_tray_comp, in_tray_comp.yZConstructionPlane, -115.0)
        sk_ut = in_tray_comp.sketches.add(pl_ut)
        draw_polygon_yz(sk_ut, -115.0, [
            (-280.0, 20.0), (-115.0, 20.0), (-68.0, 1.0),
            (-68.0, 3.5), (-115.0, 23.0), (-280.0, 23.0)
        ])
        ext_ut = extrude_profile(in_tray_comp, sk_ut.profiles.item(0), 230.0)
        ext_ut.bodies.item(0).name = 'Upper_Input_Tray_Bed'
        apply_color(ext_ut.bodies.item(0), col_tray_dark)

        for gx, gside in [(-115.0, 'Left'), (112.0, 'Right')]:
            add_box_x(in_tray_comp, gx, 3.0, -275.0, 23.0, -120.0, 36.0, f'Upper_Tray_Side_Guide_{gside}', col_dark_frame)

        add_cyl_x(in_tray_comp, -130.0, 358.0, -175.0, 37.0, 3.0, 'Pickup_Roller_Shaft', col_steel)
        for prx in [-55.0, 25.0]:
            add_cyl_x(in_tray_comp, prx, 30.0, -175.0, 37.0, 11.5, f'Sheet_Pickup_Roller_{int(prx)}', col_black)

        # =====================================================================
        # 8. LOWER OUTPUT TRAY & RETURN CHUTE
        # =====================================================================
        out_tray_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        out_tray_comp = out_tray_occ.component
        out_tray_comp.name = '08_Lower_Output_Tray_And_Chute'

        pl_lt = offset_plane(out_tray_comp, out_tray_comp.yZConstructionPlane, -120.0)
        sk_lt = out_tray_comp.sketches.add(pl_lt)
        draw_polygon_yz(sk_lt, -120.0, [
            (-68.0, -4.5), (-68.0, -7.5), (-125.0, -45.0), (-290.0, -45.0),
            (-290.0, -32.0), (-286.0, -32.0), (-286.0, -42.0), (-125.0, -42.0)
        ])
        ext_lt = extrude_profile(out_tray_comp, sk_lt.profiles.item(0), 240.0)
        ext_lt.bodies.item(0).name = 'Lower_Switchback_Output_Tray'
        apply_color(ext_lt.bodies.item(0), col_tray_dark)

        pl_rc = offset_plane(out_tray_comp, out_tray_comp.yZConstructionPlane, -115.0)
        sk_rc = out_tray_comp.sketches.add(pl_rc)
        draw_polygon_yz(sk_rc, -115.0, [(-80.0, -3.5), (-125.0, -33.0), (-125.0, -31.0), (-80.0, -1.5)])
        ext_rc = extrude_profile(out_tray_comp, sk_rc.profiles.item(0), 230.0)
        ext_rc.bodies.item(0).name = 'Lower_Return_Chute_Roof'
        apply_color(ext_rc.bodies.item(0), col_chute_guide, opacity=0.5)

        # =====================================================================
        # 9. PAPER SHEETS AT ALL 3 STAGES
        # =====================================================================
        paper_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        paper_comp = paper_occ.component
        paper_comp.name = '09_Paper_Flow_Stages'

        pl_p1 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, 23.0)
        sk_p1 = paper_comp.sketches.add(pl_p1)
        sk_p1.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p1, -105.0, -275.0, 23.0),
            w2s(sk_p1, 105.0, -120.0, 23.0)
        )
        ext_p1 = extrude_profile(paper_comp, sk_p1.profiles.item(0), 2.5)
        ext_p1.bodies.item(0).name = 'Stage1_Upper_Tray_Paper_Stack'
        apply_color(ext_p1.bodies.item(0), col_paper)

        pl_p2 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, -0.3)
        sk_p2 = paper_comp.sketches.add(pl_p2)
        sk_p2.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p2, -105.0, -135.0, -0.3),
            w2s(sk_p2, 105.0, 7.5, -0.3)
        )
        ext_p2 = extrude_profile(paper_comp, sk_p2.profiles.item(0), 0.6)
        ext_p2.bodies.item(0).name = 'Stage2_Sheet_At_Punch_Registration'
        apply_color(ext_p2.bodies.item(0), col_paper, opacity=0.85)

        pl_p3 = offset_plane(paper_comp, paper_comp.xYConstructionPlane, -42.0)
        sk_p3 = paper_comp.sketches.add(pl_p3)
        sk_p3.sketchCurves.sketchLines.addTwoPointRectangle(
            w2s(sk_p3, -105.0, -284.0, -42.0),
            w2s(sk_p3, 105.0, -134.0, -42.0)
        )
        ext_p3 = extrude_profile(paper_comp, sk_p3.profiles.item(0), 0.8)
        p3_body = ext_p3.bodies.item(0)
        p3_body.name = 'Stage3_Lower_Tray_Punched_Sheet'
        apply_color(p3_body, col_paper)

        sk_p3_holes = paper_comp.sketches.add(pl_p3)
        for px in punch_x_coords:
            sk_p3_holes.sketchCurves.sketchCircles.addByCenterRadius(
                w2s(sk_p3_holes, px, -142.0, -42.0), mm(3.2)
            )
        for i in range(sk_p3_holes.profiles.count):
            extrude_profile(paper_comp, sk_p3_holes.profiles.item(i), 2.0, adsk.fusion.FeatureOperations.CutFeatureOperation)

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
        # Distance from Motor (Y=18.0, Z=25.0) to Off-Center Shaft (Y=0.0, Z=49.0) is sqrt(18^2 + 24^2) = 30.0 mm exact!
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

        # =====================================================================
        # 14. AS-BUILT JOINTS & KINEMATIC LINKAGES
        # =====================================================================
        ab_joints = root.asBuiltJoints

        # Lock stationary sub-components onto the Sliding Carriage (03)
        rg_carriage = root.rigidGroups.createInput(
            adsk.core.ObjectCollection.createWithArray([slide_occ, check_occ, cam_stator_occ]),
            True
        )
        root.rigidGroups.add(rg_carriage).name = 'Carriage_Rigid_Group'

        # Joint 1: Lateral Slider Joint on Punch Carriage (along X-axis)
        cp_slide = add_point(slide_comp, 0.0, 0.0, 0.0, 'Carriage_Slider_Anchor')
        geo_slide = adsk.fusion.JointGeometry.createByPoint(cp_slide.createForAssemblyContext(slide_occ))
        ab_slide_in = ab_joints.createInput(slide_occ, base_occ, geo_slide)
        ab_slide_in.setAsSliderJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
        j_slide = ab_joints.add(ab_slide_in)
        j_slide.name = '01_Side_Misalignment_Slider'
        j_slide.jointMotion.slideLimits.isMinimumValueEnabled = True
        j_slide.jointMotion.slideLimits.minimumValue = mm(-25.0)
        j_slide.jointMotion.slideLimits.isMaximumValueEnabled = True
        j_slide.jointMotion.slideLimits.maximumValue = mm(25.0)

        # Joint 2: Revolute Joint on Stepper Motor Rotor & 14T Pinion Gear around (Y=18, Z=25)
        cp_motor = add_point(cam_rotor_comp, 173.0, Y_CAM_MOTOR, Z_CAM_MOTOR, 'Cam_Motor_Axis_Point')
        geo_motor = adsk.fusion.JointGeometry.createByPoint(cp_motor.createForAssemblyContext(cam_rotor_occ))
        ab_motor_in = ab_joints.createInput(cam_rotor_occ, slide_occ, geo_motor)
        ab_motor_in.setAsRevoluteJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
        j_motor_rev = ab_joints.add(ab_motor_in)
        j_motor_rev.name = '02_Cam_Stepper_Motor_Revolute'

        # Joint 3: Revolute Joint on Off-Center Drive Shaft & 4 Stepped Eccentric Rotors around (Y=0, Z=49)
        cp_cam = add_point(cam_comp, 40.0, 0.0, Z_SHAFT, 'OffCenter_Shaft_Axis_Point')
        geo_cam = adsk.fusion.JointGeometry.createByPoint(cp_cam.createForAssemblyContext(cam_occ))
        ab_cam_in = ab_joints.createInput(cam_occ, slide_occ, geo_cam)
        ab_cam_in.setAsRevoluteJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
        j_cam_rev = ab_joints.add(ab_cam_in)
        j_cam_rev.name = '03_OffCenter_Cam_Shaft_Revolute'

        # Joint 4: Vertical Slider Joint on the 4 Silver Punch Pins (along Z-axis)
        cp_pins = add_point(pins_comp, 40.0, 0.0, 20.0, 'Punch_Pin_Slider_Point')
        geo_pins = adsk.fusion.JointGeometry.createByPoint(cp_pins.createForAssemblyContext(pins_occ))
        ab_pins_in = ab_joints.createInput(pins_occ, slide_occ, geo_pins)
        ab_pins_in.setAsSliderJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)
        j_pins_slide = ab_joints.add(ab_pins_in)
        j_pins_slide.name = '04_Punch_Pins_Vertical_Slider'

        # Joint 5: Revolute Joint on the 4 Outer Clevis Straps around the Wrist Pin (Y=0, Z=34) on the Punch Pins
        cp_strap = add_point(strap_comp, 40.0, 0.0, Z_WRIST_TDC, 'Clevis_Wrist_Pin_Pivot')
        geo_strap = adsk.fusion.JointGeometry.createByPoint(cp_strap.createForAssemblyContext(strap_occ))
        ab_strap_in = ab_joints.createInput(strap_occ, pins_occ, geo_strap)
        ab_strap_in.setAsRevoluteJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
        j_strap_rev = ab_joints.add(ab_strap_in)
        j_strap_rev.name = '05_Clevis_Strap_WristPin_Revolute'

        # Focus Camera onto the Blue Highlighted Punch Bit (Station 3 at X = +40 mm) & Motor Gears
        vp = app.activeViewport
        cam = vp.camera
        cam.eye = adsk.core.Point3D.create(mm(145.0), mm(-115.0), mm(82.0))
        cam.target = adsk.core.Point3D.create(mm(55.0), mm(0.0), mm(34.0))
        cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
        cam.isFitView = False
        vp.camera = cam
        vp.refresh()

        ui.messageBox(
            'Off-Center Eccentric Cam & Clevis-Strap Punch Mechanism Built!\n\n'
            'Click OK to watch the live 3D animation (2 full punch cycles):\n'
            '• Stepper Motor & 14T Pinion spin the 28T Bull Gear & Off-Center Shaft.\n'
            '• Stepped Eccentric Rotor orbits inside the Blue Clevis Strap.\n'
            '• Clevis Strap rocks on the Wrist Pin while driving the Silver Punch Pin down through the Chrome Guide Block!'
        )

        # =====================================================================
        # 15. LIVE KINEMATIC ANIMATION (2 Full Punch Cycles = 720 Degrees)
        # =====================================================================
        rev_motor_motion = adsk.fusion.RevoluteJointMotion.cast(j_motor_rev.jointMotion)
        rev_cam_motion = adsk.fusion.RevoluteJointMotion.cast(j_cam_rev.jointMotion)
        slide_pins_motion = adsk.fusion.SliderJointMotion.cast(j_pins_slide.jointMotion)
        rev_strap_motion = adsk.fusion.RevoluteJointMotion.cast(j_strap_rev.jointMotion)

        total_steps = 90  # 2 revolutions at 8 degrees per step
        for step in range(total_steps + 1):
            theta = (step / total_steps) * (4.0 * math.pi)

            # Exact Slider-Crank Kinematics for the Off-Center Eccentric Cam & Clevis Strap:
            # 1) Vertical displacement of Punch Pin & Wrist Pin (in mm):
            dz_mm = ECCENTRICITY * (math.cos(theta) - 1.0) + (L_STRAP - math.sqrt(L_STRAP**2 - (ECCENTRICITY * math.sin(theta))**2))

            # 2) Rocking angle phi (in radians) of the Outer Clevis Strap on the Wrist Pin:
            phi_rad = math.asin((ECCENTRICITY / L_STRAP) * math.sin(theta))

            # Apply synchronized motion to all 4 joints:
            rev_motor_motion.rotationValue = -2.0 * theta   # 2:1 gear ratio
            rev_cam_motion.rotationValue = theta            # Off-center shaft & eccentric rotor rotation
            slide_pins_motion.slideValue = mm(dz_mm)        # Vertical punch stroke (0 to -8.0 mm)
            rev_strap_motion.rotationValue = phi_rad        # Clevis strap rocking on wrist pin

            adsk.doEvents()
            vp.refresh()
            time.sleep(0.02)

        # Add persistent Motion Link between Stepper Motor Pinion and Cam Shaft Bull Gear (2:1)
        try:
            mlinks = root.motionLinks
            ml_in = mlinks.createInput(j_cam_rev, j_motor_rev)
            ml_in.valueOne = adsk.core.ValueInput.createByReal(math.pi)
            ml_in.valueTwo = adsk.core.ValueInput.createByReal(-2.0 * math.pi)
            ml = mlinks.add(ml_in)
            ml.name = 'Motor_2to1_Gear_MotionLink'
        except:
            pass

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))