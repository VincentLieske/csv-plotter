"""
Tests für die Datumsformat-Erkennung (detect_dayfirst).
"""
import pandas as pd
from date_format_detector import detect_dayfirst


class TestDetectDayfirst:
    """Tests für detect_dayfirst"""

    def test_german_date_dd_mm_yyyy(self):
        """DD.MM.YYYY → dayfirst=True (Tag 24 > 12)"""
        s = pd.Series(["24.12.2024", "15.03.2024", "01.01.2024"])
        assert detect_dayfirst(s) is True

    def test_us_date_mm_dd_yyyy(self):
        """MM.DD.YYYY mit Monat > 12 im zweiten Teil → dayfirst=False"""
        s = pd.Series(["01.15.2024", "03.22.2024"])
        assert detect_dayfirst(s) is False

    def test_ambiguous_date_default_german(self):
        """Ambiges Datum 01.02.2026 → Fallback auf Deutsch (dayfirst=True)"""
        s = pd.Series(["01.02.2026", "03.04.2026"])
        assert detect_dayfirst(s) is True

    def test_iso_date_ignored(self):
        """ISO-Format YYYY-MM-DD → wird ignoriert (erste Komponente > 31) → Fallback True"""
        s = pd.Series(["2024-01-05", "2026-03-15"])
        assert detect_dayfirst(s) is True

    def test_mixed_iso_and_german(self):
        """ISO + deutsches Datum → nur deutsches Datum zählt → dayfirst=True"""
        s = pd.Series(["2024-01-05", "24.12.2024"])
        assert detect_dayfirst(s) is True

    def test_mixed_iso_and_us(self):
        """ISO + US-Datum → nur US-Datum zählt → dayfirst=False"""
        s = pd.Series(["2024-01-05", "01.22.2024"])
        assert detect_dayfirst(s) is False

    def test_all_ambiguous(self):
        """Alle Werte ambig (1-2-2026, 3-4-2026) → Fallback True"""
        s = pd.Series(["01-02-2026", "03-04-2026"])
        assert detect_dayfirst(s) is True

    def test_empty_series(self):
        """Leere Series → Fallback True"""
        s = pd.Series([], dtype=object)
        assert detect_dayfirst(s) is True

    def test_all_nan(self):
        """Nur NaN → Fallback True"""
        s = pd.Series([None, None, None])
        assert detect_dayfirst(s) is True

    def test_mixed_separators(self):
        """Verschiedene Trennzeichen (-, /, .) → korrekte Erkennung"""
        s = pd.Series(["24-12-2024", "15/03/2024", "01.01.2024"])
        assert detect_dayfirst(s) is True

    def test_short_year(self):
        """Kurzes Jahr (YY) → korrekte Erkennung"""
        s = pd.Series(["24.12.24", "15.03.24"])
        assert detect_dayfirst(s) is True

    def test_majority_vote_day(self):
        """Mehrheit Tag-zuerst → dayfirst=True"""
        s = pd.Series(["24.12.2024", "15.03.2024", "01.15.2024"])
        assert detect_dayfirst(s) is True

    def test_majority_vote_month(self):
        """Mehrheit Monat-zuerst → dayfirst=False"""
        s = pd.Series(["01.15.2024", "03.22.2024", "24.12.2024"])
        assert detect_dayfirst(s) is False

    def test_invalid_parts_skipped(self):
        """Ungültige Teile (Buchstaben) werden übersprungen"""
        s = pd.Series(["24.12.2024", "abc.def.ghi", "15.03.2024"])
        assert detect_dayfirst(s) is True

    def test_both_components_12_fallback_german(self):
        """Beide Komponenten 12 (12.12.2024) → keine Evidenz → Fallback True"""
        s = pd.Series(["12.12.2024", "12.12.2025"])
        assert detect_dayfirst(s) is True

    def test_iso_and_ambiguous_mixed(self):
        """ISO + ambige Daten → nur ambige zählen → Fallback True"""
        s = pd.Series(["2024-01-05", "01-02-2026"])
        assert detect_dayfirst(s) is True

    def test_iso_and_us_mixed(self):
        """ISO + US-Datum → US-Datum zählt → dayfirst=False"""
        s = pd.Series(["2024-01-05", "01.22.2024"])
        assert detect_dayfirst(s) is False
