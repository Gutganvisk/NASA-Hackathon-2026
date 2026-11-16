import unittest

from server import water_alerts


class WaterAlertTests(unittest.TestCase):
    def test_persistent_low_wetness_only_alerts_for_selected_sensitive_crop(self):
        samples = {day: {"GWETROOT": value} for day, value in (
            ("20261114", 0.49), ("20261113", 0.47), ("20261112", 0.48),
        )}
        alerts = water_alerts(samples, "20261115", ["milho", "mandioca"])
        self.assertEqual(alerts, [{
            "cultura": "Milho", "saturacao_recente_pct": 49.0,
            "ultima_leitura": "2026-11-14", "dias_consecutivos": 3,
        }])
        self.assertEqual(water_alerts(samples, "20261115", []), [])

    def test_gap_or_stale_data_cannot_trigger_alert(self):
        records = {day: {"GWETROOT": 0.30} for day in ("20261115", "20261113", "20261112", "20261111")}
        self.assertEqual(water_alerts(records, "20261115", ["milho"]), [])
        self.assertEqual(water_alerts(records, "20261120", ["milho"]), [])

    def test_reading_at_the_threshold_breaks_the_sequence(self):
        records = {day: {"GWETROOT": value} for day, value in (
            ("20261115", 0.46), ("20261114", 0.50), ("20261113", 0.46),
        )}
        self.assertEqual(water_alerts(records, "20261115", ["milho"]), [])
