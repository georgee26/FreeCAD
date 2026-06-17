# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD
import Part
import Sketcher

from SketcherTests.GuiTestCase import SketcherGuiTestCase, GUI_MODULE_AVAILABLE

if GUI_MODULE_AVAILABLE:
    import FreeCADGui

TOL = 1e-3


class TestGroupConstraintGui(SketcherGuiTestCase):
    """Tests for the Group constraint command, in particular that the generated
    frame line runs along the longest side of the group through its center: its
    length matches the group's dominant dimension and its midpoint is the group
    center, so the group can be centered without being resized."""

    def setUp(self):
        super().setUp()
        self.doc = FreeCAD.newDocument("TestGroupConstraint")

    def make_sketch(self, name, layout):
        sketch = self.doc.addObject("Sketcher::SketchObject", name)
        if layout == "wide":
            # bounding box x in [8, 44] (width 36), y in [6, 14] (height 8)
            sketch.addGeometry(Part.Circle(FreeCAD.Vector(10, 10, 0), FreeCAD.Vector(0, 0, 1), 2), False)
            sketch.addGeometry(Part.Circle(FreeCAD.Vector(40, 10, 0), FreeCAD.Vector(0, 0, 1), 4), False)
        else:  # tall
            # bounding box x in [6, 14] (width 8), y in [8, 44] (height 36)
            sketch.addGeometry(Part.Circle(FreeCAD.Vector(10, 10, 0), FreeCAD.Vector(0, 0, 1), 2), False)
            sketch.addGeometry(Part.Circle(FreeCAD.Vector(10, 40, 0), FreeCAD.Vector(0, 0, 1), 4), False)
        self.doc.recompute()
        return sketch

    def group_circles(self, sketch):
        FreeCADGui.getDocument(self.doc.Name).setEdit(sketch.Name)
        self.flush_gui(80)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, sketch.Name, "Edge1")
        FreeCADGui.Selection.addSelection(self.doc.Name, sketch.Name, "Edge2")
        FreeCADGui.runCommand("Sketcher_ConstrainGroup")
        self.flush_gui(80)
        self.doc.recompute()

    def frame_line(self, sketch):
        self.assertEqual([c.Type for c in sketch.Constraints], ["Group"])
        self.assertEqual(len(sketch.Geometry), 3)
        frame = sketch.Geometry[2]
        self.assertEqual(frame.TypeId, "Part::GeomLineSegment")
        self.assertTrue(sketch.GeometryFacadeList[2].Construction)
        return frame

    def frame_length(self, frame):
        return (frame.StartPoint - frame.EndPoint).Length

    def bbox_center(self, sketch):
        c1, c2 = sketch.Geometry[0], sketch.Geometry[1]
        xs = [
            c1.Center.x - c1.Radius,
            c1.Center.x + c1.Radius,
            c2.Center.x - c2.Radius,
            c2.Center.x + c2.Radius,
        ]
        ys = [
            c1.Center.y - c1.Radius,
            c1.Center.y + c1.Radius,
            c2.Center.y - c2.Radius,
            c2.Center.y + c2.Radius,
        ]
        return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

    def assert_group_rigid(self, sketch, dx, dy):
        """The group must keep its size and orientation: centering is a pure
        translation, never a scaling or rotation of the grouped geometries."""
        c1, c2 = sketch.Geometry[0], sketch.Geometry[1]
        self.assertAlmostEqual(c1.Radius, 2, delta=TOL)
        self.assertAlmostEqual(c2.Radius, 4, delta=TOL)
        self.assertAlmostEqual(c2.Center.x - c1.Center.x, dx, delta=TOL)
        self.assertAlmostEqual(c2.Center.y - c1.Center.y, dy, delta=TOL)

    def fix_group_size(self, sketch, length):
        """Dimension the frame length: the frame is the group's scale handle, so
        pinning its length keeps the group size fixed during further solves."""
        sketch.addConstraint(Sketcher.Constraint("Distance", 2, length))
        self.doc.recompute()

    def test_wide_group_frame_is_horizontal_through_center(self):
        sketch = self.make_sketch("SketchWide", "wide")
        self.group_circles(sketch)

        frame = self.frame_line(sketch)
        # horizontal line at the vertical center, spanning the full width (longest side)
        self.assertAlmostEqual(frame.StartPoint.y, 10.0, delta=TOL)
        self.assertAlmostEqual(frame.EndPoint.y, 10.0, delta=TOL)
        self.assertAlmostEqual(min(frame.StartPoint.x, frame.EndPoint.x), 8.0, delta=TOL)
        self.assertAlmostEqual(max(frame.StartPoint.x, frame.EndPoint.x), 44.0, delta=TOL)
        self.assertAlmostEqual(self.frame_length(frame), 36.0, delta=TOL)

    def test_tall_group_frame_is_vertical_through_center(self):
        sketch = self.make_sketch("SketchTall", "tall")
        self.group_circles(sketch)

        frame = self.frame_line(sketch)
        # vertical line at the horizontal center, spanning the full height (longest side)
        self.assertAlmostEqual(frame.StartPoint.x, 10.0, delta=TOL)
        self.assertAlmostEqual(frame.EndPoint.x, 10.0, delta=TOL)
        self.assertAlmostEqual(min(frame.StartPoint.y, frame.EndPoint.y), 8.0, delta=TOL)
        self.assertAlmostEqual(max(frame.StartPoint.y, frame.EndPoint.y), 44.0, delta=TOL)
        self.assertAlmostEqual(self.frame_length(frame), 36.0, delta=TOL)

    def test_center_wide_group_both_directions(self):
        sketch = self.make_sketch("SketchWideCenter", "wide")
        self.group_circles(sketch)
        # frame length already equals the width, so the group is not resized
        self.fix_group_size(sketch, 36.0)

        # horizontal frame with endpoints symmetric about the origin -> group
        # centered both ways, since the line's midpoint is the center of the group
        sketch.addConstraint(Sketcher.Constraint("Horizontal", 2))
        sketch.addConstraint(Sketcher.Constraint("Symmetric", 2, 1, 2, 2, -1, 1))
        self.doc.recompute()

        cx, cy = self.bbox_center(sketch)
        self.assertAlmostEqual(cx, 0, delta=TOL)
        self.assertAlmostEqual(cy, 0, delta=TOL)
        self.assert_group_rigid(sketch, dx=30, dy=0)

    def test_center_tall_group_horizontally(self):
        sketch = self.make_sketch("SketchTallCenter", "tall")
        self.group_circles(sketch)
        self.fix_group_size(sketch, 36.0)

        # vertical frame collinear with the vertical axis -> group centered
        # horizontally; the vertical position remains a free degree of freedom
        sketch.addConstraint(Sketcher.Constraint("Tangent", 2, -2))
        self.doc.recompute()

        cx, _ = self.bbox_center(sketch)
        self.assertAlmostEqual(cx, 0, delta=TOL)
        self.assert_group_rigid(sketch, dx=0, dy=30)
