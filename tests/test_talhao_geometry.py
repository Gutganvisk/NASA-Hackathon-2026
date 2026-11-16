import unittest

from talhao_geometry import validate_plot


def rectangle(west, south, east, north):
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


class PlotGeometryTests(unittest.TestCase):
    def test_hectares_for_small_rectangle_at_equator(self):
        result = validate_plot(rectangle(0, 0, .001, .001), None, {})
        self.assertAlmostEqual(result["area_ha"], 1.2364, places=4)

    def test_rejects_open_and_self_crossing_rings(self):
        with self.assertRaisesRegex(ValueError, "Feche o contorno"):
            validate_plot([[0, 0], [1, 0], [1, 1], [0, 1]], None, {})
        with self.assertRaisesRegex(ValueError, "cruza a si mesmo"):
            validate_plot([[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]], None, {})

    def test_checks_edges_across_concave_limits(self):
        # All four vertices lie inside, but the plot crosses the opening.
        outer = [[0, 0], [4, 0], [4, 4], [3, 4], [3, 1], [1, 1], [1, 4], [0, 4], [0, 0]]
        property_geometry = {"type": "Polygon", "coordinates": [outer]}
        with self.assertRaisesRegex(ValueError, "perímetro do CAR"):
            validate_plot(rectangle(.5, 2, 3.5, 3), property_geometry, {})

    def test_rejects_excluded_hole_inside_plot(self):
        outer, hole = rectangle(0, 0, 4, 4), rectangle(1, 1, 2, 2)
        property_geometry = {"type": "Polygon", "coordinates": [outer, hole]}
        with self.assertRaisesRegex(ValueError, "perímetro do CAR"):
            validate_plot(rectangle(.5, .5, 3, 3), property_geometry, {})

    def test_accepts_plot_on_boundary_of_multipolygon_component(self):
        first, second = rectangle(0, 0, 2, 2), rectangle(3, 0, 5, 2)
        property_geometry = {"type": "MultiPolygon", "coordinates": [[first], [second]]}
        self.assertGreater(validate_plot(second, property_geometry, {})["area_ha"], 0)

    def test_distinguishes_overlap_from_shared_edge(self):
        subject = rectangle(0, 0, 2, 2)
        others = {"T2": rectangle(1, -1, 3, 1), "T3": rectangle(2, 0, 3, 1)}
        self.assertEqual(validate_plot(subject, None, others)["sobreposicoes"], ["T2"])
        self.assertEqual(validate_plot(subject, None, {"T2": subject[::-1]})["sobreposicoes"], ["T2"])


if __name__ == "__main__":
    unittest.main()
