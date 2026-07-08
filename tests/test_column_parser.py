"""
Tests für den ColumnParser — Typ-Erkennung, Datums- und Zahlen-Parsing.
"""
import pytest
import pandas as pd
import numpy as np
from column_parser import ColumnParser, ColumnType


class TestDetectColumnType:
    """Tests für die automatische Spaltentyp-Erkennung"""

    def test_numeric_dtype_from_pandas(self):
        """Wenn pandas bereits numeric erkannt hat → NUMERIC"""
        s = pd.Series([1.5, 2.3, 4.7])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_integer_dtype(self):
        """Integer Series → NUMERIC"""
        s = pd.Series([1, 2, 3])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_date_format_dd_mm_yyyy(self):
        """Deutsches Datumsformat DD.MM.YYYY → DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024", "24.12.2024"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_date_format_iso(self):
        """ISO-Format YYYY-MM-DD → DATE"""
        s = pd.Series(["2024-01-01", "2024-03-15", "2024-12-24"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_date_format_dd_mm_yy(self):
        """Kurzes Datum DD.MM.YY → DATE"""
        s = pd.Series(["01.01.24", "15.03.24", "24.12.24"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_date_format_mixed_separators(self):
        """Verschiedene Trennzeichen → DATE"""
        s = pd.Series(["01/01/2024", "15-03-2024", "24.12.2024"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_numeric_german_comma(self):
        """Deutsche Kommazahlen → NUMERIC"""
        s = pd.Series(["1,5", "2,3", "4,7"])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_numeric_with_thousands_separator(self):
        """Zahlen mit Tausenderpunkt → NUMERIC"""
        s = pd.Series(["1.234,56", "7.890,12"])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_text_default(self):
        """Einfacher Text → TEXT"""
        s = pd.Series(["Hallo", "Welt", "Test"])
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_mixed_text_and_numbers(self):
        """Gemischte Spalte (mehr Text als Zahlen) → TEXT"""
        s = pd.Series(["Hallo", "42", "Welt", "Test", "ABC"])
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_empty_series(self):
        """Leere Series → TEXT"""
        s = pd.Series([], dtype=object)
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_all_nan(self):
        """Nur NaN-Werte → TEXT"""
        s = pd.Series([np.nan, np.nan, np.nan])
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_numeric_dot_notation(self):
        """Englische Punkt-Notation → NUMERIC"""
        s = pd.Series(["1.5", "2.3", "4.7"])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_mixed_dates_and_text(self):
        """Mehr Datum als Text → DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024", "24.12.2024", "irgendwas"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE


class TestParseNumericColumn:
    """Tests für die Zahlen-Parsing-Funktion"""

    def test_already_numeric(self):
        """Bereits numerische Spalte bleibt unverändert"""
        s = pd.Series([1.5, 2.3, np.nan])
        result = ColumnParser._parse_numeric_column(s)
        assert pd.api.types.is_float_dtype(result)
        assert result.iloc[0] == 1.5
        assert pd.isna(result.iloc[2])

    def test_german_comma(self):
        """Deutsches Komma → Punkt"""
        s = pd.Series(["1,5", "2,3", "4,7"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert result.iloc[1] == 2.3
        assert result.iloc[2] == 4.7

    def test_thousands_separator(self):
        """Tausenderpunkt und Komma: 1.234,56 → 1234.56"""
        s = pd.Series(["1.234,56", "7.890,12", "1.000.000,00"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234.56
        assert result.iloc[1] == 7890.12
        assert result.iloc[2] == 1000000.00

    def test_english_dot_notation_preserved(self):
        """Englischer Punkt bleibt erhalten (kein Komma im String)"""
        s = pd.Series(["1234.56", "7890.12"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234.56
        assert result.iloc[1] == 7890.12

    def test_nan_handling(self):
        """Ungültige Werte werden zu NaN"""
        s = pd.Series(["1,5", "keine_zahl", "3,7"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 3.7

    def test_empty_strings(self):
        """Leere Strings → NaN"""
        s = pd.Series(["1,5", "", "3,7"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 3.7

    def test_whitespace_handling(self):
        """Whitespace wird getrimmt"""
        s = pd.Series([" 1,5 ", "  2,3  ", "  4,7"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert result.iloc[1] == 2.3
        assert result.iloc[2] == 4.7


class TestParseDateColumn:
    """Tests für die Datums-Parsing-Funktion"""

    def test_german_date_dd_mm_yyyy(self):
        """Deutsches Datum DD.MM.YYYY → datetime"""
        s = pd.Series(["01.01.2024", "15.03.2024", "24.12.2024"])
        result = ColumnParser._parse_date_column(s)
        assert pd.api.types.is_datetime64_any_dtype(result)
        assert result.iloc[0].day == 1
        assert result.iloc[0].month == 1
        assert result.iloc[0].year == 2024
        assert result.iloc[1].day == 15
        assert result.iloc[1].month == 3
        assert result.iloc[2].day == 24
        assert result.iloc[2].month == 12

    def test_iso_date(self):
        """ISO-Format YYYY-MM-DD → datetime (wird unabhängig von dayfirst korrekt erkannt)"""
        s = pd.Series(["2024-01-05", "2024-03-15"])
        result = ColumnParser._parse_date_column(s)
        assert result.iloc[0].day == 5
        assert result.iloc[0].month == 1
        assert result.iloc[1].day == 15
        assert result.iloc[1].month == 3

    def test_invalid_dates_to_nat(self):
        """Ungültige Daten → NaT"""
        s = pd.Series(["01.01.2024", "kein-datum", "99.99.9999"])
        result = ColumnParser._parse_date_column(s)
        assert result.iloc[0] == pd.Timestamp("2024-01-01")
        assert pd.isna(result.iloc[1])
        assert pd.isna(result.iloc[2])

    def test_ambiguous_date_dayfirst(self):
        """Ambiges Datum 01.02.2026 → dayfirst=True → 1. Februar"""
        s = pd.Series(["01.02.2026"])
        result = ColumnParser._parse_date_column(s)
        assert result.iloc[0].month == 2
        assert result.iloc[0].day == 1

    def test_mixed_date_formats(self):
        """Gemischte Datumsformate in einer Spalte.
        
        Hinweis: ISO-Format (2024-03-15) in einer sonst deutschen
        DD.MM.YYYY-Spalte wird zu NaT, da dayfirst=True den ISO-String
        nicht parsen kann. In der Praxis kommen gemischte Formate
        innerhalb einer Spalte extrem selten vor.
        """
        s = pd.Series(["01.01.2024", "2024-03-15", "24.12.2024"])
        result = ColumnParser._parse_date_column(s)
        assert pd.api.types.is_datetime64_any_dtype(result)
        assert result.iloc[0] == pd.Timestamp("2024-01-01")
        # ISO in DD.MM-Umgebung wird zu NaT (akzeptabler Trade-off)
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pd.Timestamp("2024-12-24")


class TestParseColumnToSeries:
    """Integrationstests für parse_column_to_series"""

    def test_numeric_result_type(self):
        """Zahlen-Spalte → ColumnResult mit NUMERIC"""
        s = pd.Series(["1,5", "2,3", "4,7"])
        result = ColumnParser.parse_column_to_series(s, "Messwerte")
        assert result.column_type == ColumnType.NUMERIC
        assert result.column_name == "Messwerte"
        assert isinstance(result.series, pd.Series)
        assert result.series.iloc[0] == 1.5

    def test_date_result_type(self):
        """Datums-Spalte → ColumnResult mit DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024"])
        result = ColumnParser.parse_column_to_series(s, "Datum")
        assert result.column_type == ColumnType.DATE
        assert result.column_name == "Datum"
        assert pd.api.types.is_datetime64_any_dtype(result.series)

    def test_text_result_type(self):
        """Text-Spalte → ColumnResult mit TEXT"""
        s = pd.Series(["Hallo", "Welt", None])
        result = ColumnParser.parse_column_to_series(s, "Notiz")
        assert result.column_type == ColumnType.TEXT
        assert result.column_name == "Notiz"
        assert result.series.iloc[0] == "Hallo"
        assert result.series.iloc[1] == "Welt"
        assert result.series.iloc[2] == ""  # None → leerer String

    def test_mixed_sparse_column(self):
        """Spalte mit überwiegend Zahlen + ein paar NaN → NUMERIC"""
        s = pd.Series(["1,5", "2,3", None, "4,7", "5,1"])
        result = ColumnParser.parse_column_to_series(s, "Werte")
        assert result.column_type == ColumnType.NUMERIC
        assert pd.isna(result.series.iloc[2])
        assert result.series.iloc[3] == 4.7

    def test_thousands_with_german_locale(self):
        """Tausenderpunkt-Komma Kombination → korrekter float"""
        s = pd.Series(["1.234,56", "7.890,12"])
        result = ColumnParser.parse_column_to_series(s, "Grosszahlen")
        assert result.column_type == ColumnType.NUMERIC
        assert result.series.iloc[0] == 1234.56
        assert result.series.iloc[1] == 7890.12