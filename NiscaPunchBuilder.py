import adsk.core
import adsk.fusion
import traceback

def mm(val: float) -> float:
    """Convert millimeters to Fusion internal units (centimeters)."""
    return val / 10.0

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

        # 1. Try copying an appearance already loaded in the active document
        if appearances.count > 0:
            try:
                base_appear = appearances.item(0)
            except:
                pass

        # 2. Otherwise search loaded appearance libraries with safe try/except guards
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

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root = design.rootComponent

        # Create Color Palette matching the Canon Finetech Nisca video
        col_steel = create_color(design, 'Nisca_Steel', 185, 190, 198)
        col_dark_frame = create_color(design, 'Nisca_Channel_Grey', 105, 110, 118)
        col_black = create_color(design, 'Nisca_Black_Roller', 35, 38, 42)
        col_blue_cam = create_color(design, 'Nisca_Highlight_Blue', 50, 140, 235)
        col_white = create_color(design, 'Nisca_White_Roller', 242, 242, 246)
        col_pcb_green = create_color(design, 'Nisca_Sensor_PCB', 20, 150, 55)
        col_sensor_red = create_color(design, 'Nisca_Sensor_LED', 215, 35, 40)
        col_stopper_amber = create_color(design, 'Nisca_Stopper_Guide', 220, 160, 45)
        col_paper = create_color(design, 'Nisca_Paper', 248, 250, 255)

        # 4-Hole standard punch positions along X-axis (in mm)
        punch_x_coords = [-120.0, -40.0, 40.0, 120.0]

        # =====================================================================
        # 1. STATIONARY BASE FRAME & LINEAR RAILS (Grounded)
        # =====================================================================
        base_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        base_comp = base_occ.component
        base_comp.name = '01_Stationary_Frame_And_LeadScrew'
        base_occ.isGrounded = True

        for side_x, name_suffix in [(-205.0, 'Left'), (195.0, 'Right')]:
            pl = offset_plane(base_comp, base_comp.yZConstructionPlane, side_x)
            sk = base_comp.sketches.add(pl)
            sk.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(mm(-120.0), mm(-32.0), 0),
                adsk.core.Point3D.create(mm(25.0), mm(65.0), 0)
            )
            ext = extrude_profile(base_comp, sk.profiles.item(0), 10.0)
            ext.bodies.item(0).name = f'Frame_Plate_{name_suffix}'
            apply_color(ext.bodies.item(0), col_dark_frame)

        # Lead screw (Y=-22, Z=-20) and Linear Guide Rod (Y=16, Z=-14)
        pl_left = offset_plane(base_comp, base_comp.yZConstructionPlane, -200.0)
        sk_rods = base_comp.sketches.add(pl_left)
        sk_rods.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(-22.0), mm(-20.0), 0), mm(4.0)
        )
        sk_rods.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(16.0), mm(-14.0), 0), mm(4.0)
        )
        for i, rod_name in enumerate(['Lateral_Lead_Screw', 'Linear_Guide_Rod']):
            ext_rod = extrude_profile(base_comp, sk_rods.profiles.item(i), 400.0)
            ext_rod.bodies.item(0).name = rod_name
            apply_color(ext_rod.bodies.item(0), col_steel)

        # =====================================================================
        # 2. SWITCHBACK REGISTRATION ROLLERS (White) & FEED ROLLERS (Black)
        # =====================================================================
        rollers_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        rollers_comp = rollers_occ.component
        rollers_comp.name = '02_Switchback_And_Feed_Rollers'

        pl_shaft = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, -200.0)
        sk_shafts = rollers_comp.sketches.add(pl_shaft)
        sk_shafts.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(-42.0), mm(0.0), 0), mm(3.0)
        )
        sk_shafts.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(-105.0), mm(0.0), 0), mm(3.0)
        )
        for i, sh_name in enumerate(['Switchback_Shaft', 'Feed_Shaft']):
            ext_sh = extrude_profile(rollers_comp, sk_shafts.profiles.item(i), 400.0)
            ext_sh.bodies.item(0).name = sh_name
            apply_color(ext_sh.bodies.item(0), col_steel)

        # White Switchback Rollers
        for rx in [-65.0, 30.0]:
            pl_r = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, rx)
            sk_r = rollers_comp.sketches.add(pl_r)
            sk_r.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(-42.0), mm(0.0), 0), mm(12.0)
            )
            ext_wr = extrude_profile(rollers_comp, sk_r.profiles.item(0), 35.0)
            ext_wr.bodies.item(0).name = f'White_Reg_Roller_{int(rx)}'
            apply_color(ext_wr.bodies.item(0), col_white)

        # Black Transport Rollers
        for rx in [-55.0, 31.0]:
            pl_r = offset_plane(rollers_comp, rollers_comp.yZConstructionPlane, rx)
            sk_r = rollers_comp.sketches.add(pl_r)
            sk_r.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(-105.0), mm(0.0), 0), mm(11.0)
            )
            ext_br = extrude_profile(rollers_comp, sk_r.profiles.item(0), 24.0)
            ext_br.bodies.item(0).name = f'Black_Feed_Roller_{int(rx)}'
            apply_color(ext_br.bodies.item(0), col_black)

        # =====================================================================
        # 3. PUNCH SLIDE UNIT (C-Channel Die + Optical Sensor + Stopper Guides)
        # =====================================================================
        slide_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        slide_comp = slide_occ.component
        slide_comp.name = '03_Punch_Slide_Unit_Carriage'

        # 3A. Lower C-Channel Die Frame spanning X = -170 to +170 mm
        pl_chan = offset_plane(slide_comp, slide_comp.yZConstructionPlane, -170.0)
        sk_chan = slide_comp.sketches.add(pl_chan)
        lines = sk_chan.sketchCurves.sketchLines
        pts = [
            adsk.core.Point3D.create(mm(-14.0), mm(-10.0), 0),
            adsk.core.Point3D.create(mm(14.0), mm(-10.0), 0),
            adsk.core.Point3D.create(mm(14.0), mm(10.0), 0),
            adsk.core.Point3D.create(mm(-14.0), mm(10.0), 0),
            adsk.core.Point3D.create(mm(-14.0), mm(6.0), 0),
            adsk.core.Point3D.create(mm(9.0), mm(6.0), 0),
            adsk.core.Point3D.create(mm(9.0), mm(-6.0), 0),
            adsk.core.Point3D.create(mm(-14.0), mm(-6.0), 0)
        ]
        for i in range(len(pts)):
            lines.addByTwoPoints(pts[i], pts[(i + 1) % len(pts)])

        ext_chan = extrude_profile(slide_comp, sk_chan.profiles.item(0), 340.0)
        chan_body = ext_chan.bodies.item(0)
        chan_body.name = 'C_Channel_Die_Beam'
        apply_color(chan_body, col_dark_frame)

        # 3B. Punch Guide Blocks on top of C-Channel (4 stations)
        pl_top = offset_plane(slide_comp, slide_comp.xYConstructionPlane, 10.0)
        sk_blocks = slide_comp.sketches.add(pl_top)
        for px in punch_x_coords:
            sk_blocks.sketchCurves.sketchLines.addTwoPointRectangle(
                adsk.core.Point3D.create(mm(px - 9.0), mm(-9.0), 0),
                adsk.core.Point3D.create(mm(px + 9.0), mm(9.0), 0)
            )
        for i in range(sk_blocks.profiles.count):
            extrude_profile(
                slide_comp,
                sk_blocks.profiles.item(i),
                16.0,
                adsk.fusion.FeatureOperations.JoinFeatureOperation
            )

        # 3C. Cut 4 Vertical Punch & Die Holes through Guide Blocks and C-Channel
        pl_cut = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -15.0)
        sk_holes = slide_comp.sketches.add(pl_cut)
        for px in punch_x_coords:
            sk_holes.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(px), mm(0.0), 0), mm(3.2)
            )
        for i in range(sk_holes.profiles.count):
            extrude_profile(
                slide_comp,
                sk_holes.profiles.item(i),
                45.0,
                adsk.fusion.FeatureOperations.CutFeatureOperation
            )

        # 3D. Optical Edge Sensor (Green PCB + Red Optical Sensor on Right Side)
        pl_pcb = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -5.0)
        sk_pcb = slide_comp.sketches.add(pl_pcb)
        sk_pcb.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(mm(132.0), mm(-30.0), 0),
            adsk.core.Point3D.create(mm(168.0), mm(8.0), 0)
        )
        ext_pcb = extrude_profile(slide_comp, sk_pcb.profiles.item(0), 2.0)
        ext_pcb.bodies.item(0).name = 'Optical_Registration_PCB'
        apply_color(ext_pcb.bodies.item(0), col_pcb_green)

        pl_led = offset_plane(slide_comp, slide_comp.xYConstructionPlane, -3.0)
        sk_led = slide_comp.sketches.add(pl_led)
        sk_led.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(148.0), mm(-16.0), 0), mm(4.0)
        )
        ext_led = extrude_profile(slide_comp, sk_led.profiles.item(0), 2.5)
        ext_led.bodies.item(0).name = 'Side_Edge_Optical_Sensor'
        apply_color(ext_led.bodies.item(0), col_sensor_red)

        # 3E. Paper Stopper Guides (Skew Registration Stoppers inside C-Channel)
        for sg_x in [-80.0, 0.0, 80.0]:
            pl_sg = offset_plane(slide_comp, slide_comp.yZConstructionPlane, sg_x - 3.0)
            sk_sg = slide_comp.sketches.add(pl_sg)
            sg_lines = sk_sg.sketchCurves.sketchLines
            sg_pts = [
                adsk.core.Point3D.create(mm(4.0), mm(-5.0), 0),
                adsk.core.Point3D.create(mm(8.0), mm(-5.0), 0),
                adsk.core.Point3D.create(mm(12.0), mm(14.0), 0),
                adsk.core.Point3D.create(mm(6.0), mm(14.0), 0)
            ]
            for j in range(len(sg_pts)):
                sg_lines.addByTwoPoints(sg_pts[j], sg_pts[(j + 1) % len(sg_pts)])
            ext_sg = extrude_profile(slide_comp, sk_sg.profiles.item(0), 6.0)
            ext_sg.bodies.item(0).name = f'Paper_Stopper_Guide_{int(sg_x)}'
            apply_color(ext_sg.bodies.item(0), col_stopper_amber)

        # =====================================================================
        # 4. ROTARY CAM DRIVE SHAFT & 4 ECCENTRIC CAM HOUSINGS
        # =====================================================================
        cam_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        cam_comp = cam_occ.component
        cam_comp.name = '04_Rotary_Cam_Shaft_Assembly'

        # Main Upper Drive Shaft centered at Y = 0, Z = 50 mm
        pl_cam_sh = offset_plane(cam_comp, cam_comp.yZConstructionPlane, -175.0)
        sk_cam_sh = cam_comp.sketches.add(pl_cam_sh)
        sk_cam_sh.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(mm(0.0), mm(50.0), 0), mm(5.0)
        )
        ext_cam_sh = extrude_profile(cam_comp, sk_cam_sh.profiles.item(0), 350.0)
        ext_cam_sh.bodies.item(0).name = 'Upper_Punch_Drive_Shaft'
        apply_color(ext_cam_sh.bodies.item(0), col_steel)

        # 4 Cylindrical Cam Housings + Internal Eccentric Cam Lobes
        for idx, px in enumerate(punch_x_coords):
            # Internal Eccentric Cam Lobe (offset downward in Z to drive the pin)
            pl_lobe = offset_plane(cam_comp, cam_comp.yZConstructionPlane, px - 5.0)
            sk_lobe = cam_comp.sketches.add(pl_lobe)
            sk_lobe.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(0.0), mm(44.5), 0), mm(9.5)
            )
            ext_lobe = extrude_profile(cam_comp, sk_lobe.profiles.item(0), 10.0)
            lobe_body = ext_lobe.bodies.item(0)
            lobe_body.name = f'Internal_Eccentric_Lobe_{idx + 1}'
            apply_color(lobe_body, col_steel)

            # Outer Cylindrical Housing
            pl_drum = offset_plane(cam_comp, cam_comp.yZConstructionPlane, px - 10.0)
            sk_drum = cam_comp.sketches.add(pl_drum)
            sk_drum.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(0.0), mm(47.0), 0), mm(15.0)
            )
            ext_drum = extrude_profile(cam_comp, sk_drum.profiles.item(0), 20.0)
            drum_body = ext_drum.bodies.item(0)
            drum_body.name = f'Cam_Housing_{idx + 1}'
            if idx == 2:
                # 3rd unit highlighted in translucent Blue just like the video
                apply_color(drum_body, col_blue_cam, opacity=0.45)
            else:
                apply_color(drum_body, col_black)

        # =====================================================================
        # 5. VERTICAL RECIPROCATING PUNCH PINS (4 Stations)
        # =====================================================================
        pins_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        pins_comp = pins_occ.component
        pins_comp.name = '05_Vertical_Punch_Pins'

        pl_pin_base = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 2.0)
        sk_pins = pins_comp.sketches.add(pl_pin_base)
        for px in punch_x_coords:
            sk_pins.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(px), mm(0.0), 0), mm(3.0)
            )
        for i in range(sk_pins.profiles.count):
            ext_pin = extrude_profile(pins_comp, sk_pins.profiles.item(i), 30.0)
            ext_pin.bodies.item(0).name = f'Punch_Blade_Pin_{i + 1}'
            apply_color(ext_pin.bodies.item(0), col_steel)

        # Upper Pin Follower Collars at Z = 32..35 mm
        pl_cap = offset_plane(pins_comp, pins_comp.xYConstructionPlane, 32.0)
        sk_caps = pins_comp.sketches.add(pl_cap)
        for px in punch_x_coords:
            sk_caps.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(mm(px), mm(0.0), 0), mm(6.5)
            )
        for i in range(sk_caps.profiles.count):
            ext_cap = extrude_profile(pins_comp, sk_caps.profiles.item(i), 3.0)
            ext_cap.bodies.item(0).name = f'Punch_Follower_Collar_{i + 1}'
            apply_color(ext_cap.bodies.item(0), col_blue_cam if i == 2 else col_steel)

        # =====================================================================
        # 6. A4 PAPER SHEET IN REGISTRATION POSITION
        # =====================================================================
        paper_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        paper_comp = paper_occ.component
        paper_comp.name = '06_Registered_Paper_Sheet'

        pl_paper = offset_plane(paper_comp, paper_comp.xYConstructionPlane, -0.25)
        sk_paper = paper_comp.sketches.add(pl_paper)
        sk_paper.sketchCurves.sketchLines.addTwoPointRectangle(
            adsk.core.Point3D.create(mm(-105.0), mm(-155.0), 0),
            adsk.core.Point3D.create(mm(105.0), mm(4.0), 0)
        )
        ext_paper = extrude_profile(paper_comp, sk_paper.profiles.item(0), 0.5)
        ext_paper.bodies.item(0).name = 'A4_Sheet'
        apply_color(ext_paper.bodies.item(0), col_paper, opacity=0.85)

        # =====================================================================
        # 7. ASSEMBLY JOINTS (Lateral Slider + Rigid Carriage Group)
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

            # Lock the Cam Shaft and Punch Pins to slide laterally with the Punch Carriage
            rg_in = root.rigidGroups.createInput(
                adsk.core.ObjectCollection.createWithArray([slide_occ, cam_occ, pins_occ]),
                True
            )
            rg = root.rigidGroups.add(rg_in)
            rg.name = 'Punch_Slide_Unit_Group'
        except:
            pass

        # Fit Isometric Camera View
        vp = app.activeViewport
        cam = vp.camera
        cam.eye = adsk.core.Point3D.create(mm(260.0), mm(-280.0), mm(210.0))
        cam.target = adsk.core.Point3D.create(mm(0.0), mm(-30.0), mm(10.0))
        cam.upVector = adsk.core.Vector3D.create(0, 0, 1)
        cam.isFitView = True
        vp.camera = cam
        vp.refresh()

        ui.messageBox(
            'Canon Finetech Nisca Registration & Punch Unit Built Successfully!\n\n'
            '• Click and drag "03_Punch_Slide_Unit_Carriage" left/right to test Side Misalignment Correction.\n'
            '• Zoom into the 3rd (translucent blue) Cam Housing to see the internal Eccentric Cam Lobe & Follower.\n'
            '• Inspect the C-Channel throat to view the amber Skew Stopper Guides.'
        )

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))