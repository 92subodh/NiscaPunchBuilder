import adsk.core
import adsk.fusion
import math
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

    # Central boss hub
    hub_r = max(4.5, pitch_radius * 0.42)
    add_cyl_x(comp, x_start - 1.5, thickness_x + 3.0, wy, wz, hub_r, f'{name}_Hub', color_hub)
    return gear_body

def add_nema17_motor_x(comp: adsk.fusion.Component, x_mount_face: float, body_extends_positive_x: bool, wy: float, wz: float, shaft_len: float, name_prefix: str, col_black, col_alu, col_steel):
    """Build a realistic NEMA 17 Stepper Motor (42x42mm frame) with pilot boss and 5mm output shaft."""
    half = 21.0
    if body_extends_positive_x:
        # Motor body is on +X side of x_mount_face; shaft protrudes toward -X
        add_box_x(comp, x_mount_face, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_FrontCap', col_alu)
        add_box_x(comp, x_mount_face + 7.0, 24.0, wy - half + 0.8, wz - half + 0.8, wy + half - 0.8, wz + half - 0.8, f'{name_prefix}_StatorStack', col_black)
        add_box_x(comp, x_mount_face + 31.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_RearCap', col_alu)
        add_cyl_x(comp, x_mount_face - 2.0, 2.0, wy, wz, 11.0, f'{name_prefix}_PilotBoss', col_alu)
        add_cyl_x(comp, x_mount_face - shaft_len, shaft_len, wy, wz, 2.5, f'{name_prefix}_MotorShaft', col_steel)
    else:
        # Motor body is on -X side of x_mount_face; shaft protrudes toward +X
        add_box_x(comp, x_mount_face - 7.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_FrontCap', col_alu)
        add_box_x(comp, x_mount_face - 31.0, 24.0, wy - half + 0.8, wz - half + 0.8, wy + half - 0.8, wz + half - 0.8, f'{name_prefix}_StatorStack', col_black)
        add_box_x(comp, x_mount_face - 38.0, 7.0, wy - half, wz - half, wy + half, wz + half, f'{name_prefix}_RearCap', col_alu)
        add_cyl_x(comp, x_mount_face, 2.0, wy, wz, 11.0, f'{name_prefix}_PilotBoss', col_alu)
        add_cyl_x(comp, x_mount_face, shaft_len, wy, wz, 2.5, f'{name_prefix}_MotorShaft', col_steel)

def add_belt_drive_x(comp: adsk.fusion.Component, x_start: float, width_x: float, y1: float, z1: float, y2: float, z2: float, r_pulley: float, name_prefix: str, col_pulley, col_belt):
    """Build 2 Timing Pulleys and a closed Timing Belt connecting (y1,z1) and (y2,z2)."""
    add_cyl_x(comp, x_start - 1.0, width_x + 2.0, y1, z1, r_pulley + 1.5, f'{name_prefix}_Pulley_1_Flange', col_pulley)
    add_cyl_x(comp, x_start - 1.0, width_x + 2.0, y2, z2, r_pulley + 1.5, f'{name_prefix}_Pulley_2_Flange', col_pulley)

    dy = y2 - y1
    dz = z2 - z1
    dist = math.hypot(dy, dz)
    ny = -dz / dist
    nz = dy / dist
    t = 1.8  # Belt thickness

    pl = offset_plane(comp, comp.yZConstructionPlane, x_start)
    sk = comp.sketches.add(pl)
    # Upper belt span
    draw_polygon_yz(sk, x_start, [
        (y1 + ny * r_pulley, z1 + nz * r_pulley),
        (y2 + ny * r_pulley, z2 + nz * r_pulley),
        (y2 + ny * (r_pulley + t), z2 + nz * (r_pulley + t)),
        (y1 + ny * (r_pulley + t), z1 + nz * (r_pulley + t))
    ])
    # Lower belt span
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

        # Color Palette
        col_steel = create_color(design, 'Nisca_Steel', 185, 190, 198)
        col_alu = create_color(design, 'Nisca_Aluminum', 210, 215, 222)
        col_brass_gear = create_color(design, 'Nisca_Brass_Gear', 215, 175, 65)
        col_dark_frame = create_color(design, 'Nisca_Channel_Grey', 95, 102, 112)
        col_tray_dark = create_color(design, 'Nisca_Tray_Charcoal', 48, 52, 58)
        col_chute_guide = create_color(design, 'Nisca_Chute_Silver', 160, 168, 175)
        col_black = create_color(design, 'Nisca_Black_Roller', 30, 33, 38)
        col_blue_cam = create_color(design, 'Nisca_Highlight_Blue', 45, 138, 235)
        col_coupler_blue = create_color(design, 'Nisca_Coupler_Anodized', 35, 115, 210)
        col_white = create_color(design, 'Nisca_White_Roller', 242, 242, 246)
        col_pcb_green = create_color(design, 'Nisca_Sensor_PCB', 22, 145, 58)
        col_led_green = create_color(design, 'Nisca_Ready_LED', 40, 235, 80)
        col_sensor_red = create_color(design, 'Nisca_Sensor_LED', 220, 35, 40)
        col_stopper_amber = create_color(design, 'Nisca_Stopper_Guide', 230, 160, 35)
        col_diverter_orange = create_color(design, 'Nisca_Diverter_Gate', 235, 110, 30)
        col_paper = create_color(design, 'Nisca_Paper', 248, 250, 255)

        # 4-Hole standard punch positions along X-axis (in mm)
        punch_x_coords = [-120.0, -40.0, 40.0, 120.0]
        # 3 Rear Position/Skew verification sensor stations along X-axis (in mm)
        sensor_x_coords = [-80.0, 0.0, 80.0]

        # =====================================================================
        # 1. STATIONARY BASE FRAME & LINEAR RAILS (Grounded, Semi-Transparent)
        # =====================================================================
        base_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        base_comp = base_occ.component
        base_comp.name = '01_Stationary_Frame_And_Rails'
        base_occ.isGrounded = True

        for side_x, suffix in [(-205.0, 'Left'), (195.0, 'Right')]:
            add_box_x(base_comp, side_x, 10.0, -110.0, -52.0, 42.0, 68.0, f'Side_Frame_{suffix}', col_dark_frame, opacity=0.3)

        # Stationary Lead Screw (Y=-8, Z=-20, extended to X=-222 for Coupler) and Linear Guide Rail (Y=+14, Z=-20)
        add_cyl_x(base_comp, -222.0, 422.0, -8.0, -20.0, 4.5, 'Lateral_Lead_Screw', col_steel)
        add_cyl_x(base_comp, -200.0, 400.0, 14.0, -20.0, 4.5, 'Linear_Guide_Rod', col_steel)

        # =====================================================================
        # 2. REVERSIBLE SWITCHBACK ROLLERS & DIVERTER GATE
        # =====================================================================
        rollers_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        rollers_comp = rollers_occ.component
        rollers_comp.name = '02_Switchback_Rollers_And_Diverter'

        # Upper White Switchback Roller Shaft (Y = -55 mm, Z = +11 mm, extended to X=+228 for Gear & Pulley)
        add_cyl_x(rollers_comp, -200.0, 428.0, -55.0, 11.0, 3.5, 'Upper_Switchback_Shaft', col_steel)
        # Lower Black Pinch Roller Shaft (Y = -55 mm, Z = -11 mm, extended to X=+218 for Gear)
        add_cyl_x(rollers_comp, -200.0, 418.0, -55.0, -11.0, 3.5, 'Lower_Pinch_Shaft', col_steel)

        for rx in [-68.0, 32.0]:
            add_cyl_x(rollers_comp, rx, 36.0, -55.0, 11.0, 11.0, f'White_Switchback_Roller_{int(rx)}', col_white)
            add_cyl_x(rollers_comp, rx, 36.0, -55.0, -11.0, 11.0, f'Black_Pinch_Roller_{int(rx)}', col_black)

        # Horizontal Paper Guide Throat Plates between Switchback Rollers (Y=-40) and Punch Die (Y=-15)
        pl_throat = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -135.0)
        sk_throat = rollers_comp.sketches.add(pl_throat)
        draw_polygon_yz(sk_throat, -135.0, [(-41.0, 4.5), (-15.0, 4.5), (-15.0, 6.5), (-41.0, 6.5)])
        draw_polygon_yz(sk_throat, -135.0, [(-41.0, -6.5), (-15.0, -6.5), (-15.0, -4.5), (-41.0, -4.5)])
        for i, gname in enumerate(['Upper_Throat_Guide', 'Lower_Throat_Guide']):
            ext_g = extrude_profile(rollers_comp, sk_throat.profiles.item(i), 270.0)
            ext_g.bodies.item(0).name = gname
            apply_color(ext_g.bodies.item(0), col_chute_guide, opacity=0.55)

        # One-Way Diverter Flapper Gate at Y-Junction (Y = -82 mm, Z = +4 mm)
        add_cyl_x(rollers_comp, -140.0, 352.0, -82.0, 4.0, 2.0, 'Diverter_Pivot_Shaft', col_steel)
        pl_div = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -130.0)
        sk_div = rollers_comp.sketches.add(pl_div)
        draw_polygon_yz(sk_div, -130.0, [
            (-82.0, 5.5),
            (-66.0, -1.5),
            (-68.0, -3.5),
            (-83.0, 2.5)
        ])
        ext_div = extrude_profile(rollers_comp, sk_div.profiles.item(0), 260.0)
        ext_div.bodies.item(0).name = 'OneWay_Switchback_Diverter_Gate'
        apply_color(ext_div.bodies.item(0), col_diverter_orange)

        # =====================================================================
        # 3. PUNCH SLIDE UNIT CARRIAGE (C-Channel Die + Gantry Plates)
        # =====================================================================
        slide_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        slide_comp = slide_occ.component
        slide_comp.name = '03_Punch_Slide_Unit_Carriage'

        pl_chan = offset_plane(slide_comp, slide_comp.yZConstructionPlane, -170.0)
        sk_chan = slide_comp.sketches.add(pl_chan)
        draw_polygon_yz(sk_chan, -170.0, [
            (-14.0, -10.0),
            (15.0, -10.0),
            (15.0, 10.0),
            (-14.0, 10.0),
            (-14.0, 4.5),
            (10.0, 4.5),
            (10.0, -4.5),
            (-14.0, -4.5)
        ])
        ext_chan = extrude_profile(slide_comp, sk_chan.profiles.item(0), 340.0)
        chan_body = ext_chan.bodies.item(0)
        chan_body.name = 'C_Channel_Die_Beam'
        apply_color(chan_body, col_dark_frame)

        # Left and Right Carriage Gantry End-Plates supporting the Upper Cam Shaft & Cam Stepper Motor
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

        # 4 Punch Guide Blocks on top of C-Channel
        pl_top = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 10.0)
        sk_blocks = slide_comp.sketches.add(pl_top)
        for px in punch_x_coords:
            sk_blocks.sketchCurves.sketchLines.addTwoPointRectangle(
                w2s(sk_blocks, px - 9.0, -9.0, 10.0),
                w2s(sk_blocks, px + 9.0, 9.0, 10.0)
            )
        for i in range(sk_blocks.profiles.count):
            extrude_profile(slide_comp, sk_blocks.profiles.item(i), 16.0, adsk.fusion.FeatureOperations.JoinFeatureOperation)

        # Cut 4 Vertical Punch & Die Holes (Dia 6.4 mm)
        pl_cut = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -15.0)
        sk_holes = slide_comp.sketches.add(pl_cut)
        for px in punch_x_coords:
            sk_holes.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_holes, px, 0.0, -15.0), mm(3.2))
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
        # 4. ROTARY CAM DRIVE SHAFT & 4 ECCENTRIC CAM HOUSINGS
        # =====================================================================
        cam_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_comp = cam_occ.component
        cam_comp.name = '04_Rotary_Cam_Shaft_Assembly'

        # Main Upper Drive Shaft centered at Y = 0 mm, Z = +50 mm (extended to X=+184 for Bull Gear)
        add_cyl_x(cam_comp, -174.0, 358.0, 0.0, 50.0, 5.0, 'Upper_Punch_Drive_Shaft', col_steel)

        for idx, px in enumerate(punch_x_coords):
            add_cyl_x(cam_comp, px - 5.0, 10.0, 0.0, 46.5, 9.0, f'Internal_Eccentric_Lobe_{idx + 1}', col_steel)
            if idx == 2:
                add_cyl_x(cam_comp, px - 10.0, 20.0, 0.0, 48.5, 14.5, f'Cam_Housing_{idx + 1}_Translucent', col_blue_cam, opacity=0.42)
            else:
                add_cyl_x(cam_comp, px - 10.0, 20.0, 0.0, 48.5, 14.5, f'Cam_Housing_{idx + 1}', col_black)

        # =====================================================================
        # 5. VERTICAL RECIPROCATING PUNCH PINS (4 Stations at Y = 0)
        # =====================================================================
        pins_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        pins_comp = pins_occ.component
        pins_comp.name = '05_Vertical_Punch_Pins'

        pl_pin_base = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 2.0)
        sk_pins = pins_comp.sketches.add(pl_pin_base)
        for px in punch_x_coords:
            sk_pins.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_pins, px, 0.0, 2.0), mm(3.0))
        for i in range(sk_pins.profiles.count):
            ext_pin = extrude_profile(pins_comp, sk_pins.profiles.item(i), 32.5)
            ext_pin.bodies.item(0).name = f'Punch_Blade_Pin_{i + 1}'
            apply_color(ext_pin.bodies.item(0), col_steel)

        pl_cap = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 34.5)
        sk_caps = pins_comp.sketches.add(pl_cap)
        for px in punch_x_coords:
            sk_caps.sketchCurves.sketchCircles.addByCenterRadius(w2s(sk_caps, px, 0.0, 34.5), mm(6.5))
        for i in range(sk_caps.profiles.count):
            ext_cap = extrude_profile(pins_comp, sk_caps.profiles.item(i), 3.0)
            ext_cap.bodies.item(0).name = f'Punch_Follower_Collar_{i + 1}'
            apply_color(ext_cap.bodies.item(0), col_blue_cam if i == 2 else col_steel)

        # =====================================================================
        # 6. REAR PAPER POSITION & SKEW CHECK MECHANISM (Opposite to Paper Entry)
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
                (7.5, -3.5),
                (10.5, -3.5),
                (12.5, 1.5),
                (29.0, 1.5),
                (29.0, 4.5),
                (15.5, 5.5),
                (15.5, 13.5),
                (11.5, 13.5),
                (7.5, 4.0)
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
            (-280.0, 20.0),
            (-115.0, 20.0),
            (-68.0, 1.0),
            (-68.0, 3.5),
            (-115.0, 23.0),
            (-280.0, 23.0)
        ])
        ext_ut = extrude_profile(in_tray_comp, sk_ut.profiles.item(0), 230.0)
        ext_ut.bodies.item(0).name = 'Upper_Input_Tray_Bed'
        apply_color(ext_ut.bodies.item(0), col_tray_dark)

        for gx, gside in [(-115.0, 'Left'), (112.0, 'Right')]:
            add_box_x(in_tray_comp, gx, 3.0, -275.0, 23.0, -120.0, 36.0, f'Upper_Tray_Side_Guide_{gside}', col_dark_frame)

        # Overhead Sheet Pick-Up Roller Shaft (extended to X=+228 mm for Timing Belt Pulley)
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
            (-68.0, -4.5),
            (-68.0, -7.5),
            (-125.0, -45.0),
            (-290.0, -45.0),
            (-290.0, -32.0),
            (-286.0, -32.0),
            (-286.0, -42.0),
            (-125.0, -42.0)
        ])
        ext_lt = extrude_profile(out_tray_comp, sk_lt.profiles.item(0), 240.0)
        ext_lt.bodies.item(0).name = 'Lower_Switchback_Output_Tray'
        apply_color(ext_lt.bodies.item(0), col_tray_dark)

        pl_rc = offset_plane(out_tray_comp, out_tray_comp.yZConstructionPlane, -115.0)
        sk_rc = out_tray_comp.sketches.add(pl_rc)
        draw_polygon_yz(sk_rc, -115.0, [
            (-80.0, -3.5),
            (-125.0, -33.0),
            (-125.0, -31.0),
            (-80.0, -1.5)
        ])
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

        # Motor Mounting Flange & Standoffs on Left Frame Plate (X = -240 to -205 mm)
        add_box_x(lat_drive_comp, -242.0, 4.0, -30.0, -42.0, 14.0, 2.0, 'LeadScrew_Motor_Mount_Plate', col_dark_frame)
        for sy, sz in [(-25.0, -37.0), (9.0, -37.0), (-25.0, -3.0), (9.0, -3.0)]:
            add_cyl_x(lat_drive_comp, -238.0, 33.0, sy, sz, 2.5, 'Motor_Standoff_Pillar', col_alu)

        # Aluminum Flexible Jaw Coupler (X = -232 to -212 mm at Y = -8, Z = -20)
        add_cyl_x(lat_drive_comp, -232.0, 20.0, -8.0, -20.0, 9.5, 'Flexible_Shaft_Coupler', col_coupler_blue)

        # NEMA 17 Stepper Motor driving the Lateral Lead Screw
        add_nema17_motor_x(lat_drive_comp, -242.0, False, -8.0, -20.0, 22.0, 'Lateral_Reg_Stepper', col_black, col_alu, col_steel)

        # =====================================================================
        # 11. CAM PUNCH STEPPER MOTOR & 2:1 SPUR GEAR REDUCTION (On Carriage)
        # =====================================================================
        cam_drive_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_drive_comp = cam_drive_occ.component
        cam_drive_comp.name = '11_Cam_Punch_Motor_And_Gears'

        # NEMA 17 Punch Motor mounted on Carriage_Right_Motor_Plate (X = +170 mm) at (Y = +18, Z = +26)
        # Distance from (18, 26) to Cam Shaft (0, 50) is sqrt(18^2 + 24^2) = 30.0 mm exact!
        add_nema17_motor_x(cam_drive_comp, 164.0, False, 18.0, 26.0, 20.0, 'Punch_Cam_Stepper', col_black, col_alu, col_steel)

        # 14-Tooth Motor Pinion Gear (Pitch Radius = 10.0 mm) at X = +173..+180 mm
        add_spur_gear_x(cam_drive_comp, 173.0, 7.0, 18.0, 26.0, 10.0, 14, 'Cam_Motor_Pinion_Gear', col_brass_gear, col_steel)

        # 28-Tooth Cam Shaft Bull Gear (Pitch Radius = 20.0 mm) at X = +173..+180 mm on (Y = 0, Z = +50)
        add_spur_gear_x(cam_drive_comp, 173.0, 7.0, 0.0, 50.0, 20.0, 28, 'Cam_Shaft_Bull_Gear', col_brass_gear, col_steel)

        # =====================================================================
        # 12. ROLLER STEPPER DRIVE, 3-GEAR TRAIN & PICKUP TIMING BELT (Right Side)
        # =====================================================================
        roller_drive_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        roller_drive_comp = roller_drive_occ.component
        roller_drive_comp.name = '12_Roller_And_Belt_Drive_System'

        # Reversible Feed/Switchback Stepper Motor mounted inside Right Frame Plate (X = +195 mm) at (Y = -80, Z = -11)
        # Distance to Lower Pinch Shaft (Y = -55, Z = -11) is 25.0 mm exact!
        add_nema17_motor_x(roller_drive_comp, 195.0, False, -80.0, -11.0, 24.0, 'Switchback_Roller_Stepper', col_black, col_alu, col_steel)

        # Drive Gear on Stepper Motor (Pitch Radius = 14.0 mm, 18 teeth) at X = +208..+215 mm
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -80.0, -11.0, 14.0, 18, 'Roller_Motor_Drive_Gear', col_brass_gear, col_steel)

        # Meshed 1:1 Spur Gears on Lower Pinch Shaft (Y=-55, Z=-11) & Upper Switchback Shaft (Y=-55, Z=+11)
        # Pitch Radius = 11.0 mm (15 teeth) -> Meshes with Motor Gear (14+11=25mm) and with each other (11+11=22mm)!
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -55.0, -11.0, 11.0, 15, 'Lower_Pinch_Transfer_Gear', col_brass_gear, col_steel)
        add_spur_gear_x(roller_drive_comp, 208.0, 7.0, -55.0, 11.0, 11.0, 15, 'Upper_Switchback_Driven_Gear', col_brass_gear, col_steel)

        # Timing Belt & Pulleys at X = +219..+225 mm connecting Upper Switchback Shaft (-55, +11) to Pickup Roller Shaft (-175, +37)
        add_belt_drive_x(roller_drive_comp, 219.0, 6.0, -55.0, 11.0, -175.0, 37.0, 7.5, 'Pickup_Roller_Drive', col_alu, col_black)

        # =====================================================================
        # 13. DIVERTER GATE ROTARY SOLENOID ACTUATOR (Right Frame Side)
        # =====================================================================
        sol_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        sol_comp = sol_occ.component
        sol_comp.name = '13_Diverter_Gate_Solenoid'

        # Cylindrical Rotary Solenoid mounted on outer face of Right Frame Plate (X = +205..+225 mm) at (Y = -82, Z = +4)
        add_cyl_x(sol_comp, 205.0, 18.0, -82.0, 4.0, 9.0, 'Diverter_Rotary_Solenoid_Body', col_coupler_blue)
        add_cyl_x(sol_comp, 223.0, 3.0, -82.0, 4.0, 5.0, 'Solenoid_Armature_Hub', col_steel)

        # =====================================================================
        # 14. ASSEMBLY JOINTS (Lateral Slider + Rigid Carriage Group)
        # =====================================================================
        try:
            joints = root.joints
            pt_slide_proxy = slide_comp.originConstructionPoint.createForAssemblyContext(slide_occ)
            pt_base_proxy = base_comp.originConstructionPoint.createForAssemblyContext(base_occ)

            geo_slide = adsk.fusion.JointGeometry.createByPoint(pt_slide_proxy)
            geo_base = adsk.fusion.JointGeometry.createByPoint(pt_base_proxy)

            j_input_slide = joints.createInput(geo_slide, geo_base)
            j_input_slide.setAsSliderJointMotion(adsk.fusion.JointDirections.XAxisJointDirection)
            slider_joint = joints.add(j_input_slide)
            slider_joint.name = 'Side_Misalignment_Slider'

            limits = slider_joint.jointMotion.slideLimits
            limits.isMinimumValueEnabled = True
            limits.minimumValue = mm(-25.0)
            limits.isMaximumValueEnabled = True
            limits.maximumValue = mm(25.0)

            # Lock the Cam Shaft, Punch Pins, Rear Position-Check, and Cam Motor/Gears to slide together with the Carriage
            rg_in = root.rigidGroups.createInput(
                adsk.core.ObjectCollection.createWithArray([slide_occ, cam_occ, pins_occ, check_occ, cam_drive_occ]),
                True
            )
            rg = root.rigidGroups.add(rg_in)
            rg.name = 'Punch_Slide_Unit_Group'
        except:
            pass

        # Fit Isometric Camera View
        vp = app.activeViewport
        cam = vp.camera
        cam.eye = adsk.core.Point3D.create(mm(360.0), mm(-340.0), mm(210.0))
        cam.target = adsk.core.Point3D.create(mm(0.0), mm(-95.0), mm(0.0))
        cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
        cam.isFitView = True
        vp.camera = cam
        vp.refresh()

        ui.messageBox(
            'Full Electromechanical Switchback Punch Machine Built!\n\n'
            '• 10_Lateral_LeadScrew_Stepper_Drive: NEMA 17 + Blue Jaw Coupler on Left Frame.\n'
            '• 11_Cam_Punch_Motor_And_Gears: NEMA 17 + 2:1 Brass Spur Gears mounted on the Sliding Punch Carriage.\n'
            '• 12_Roller_And_Belt_Drive_System: NEMA 17 + 3-Gear Train + Timing Belt to Upper Tray Pickup Roller.\n'
            '• 13_Diverter_Gate_Solenoid: Rotary Solenoid on Right Frame driving the Orange Diverter Gate.'
        )

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))