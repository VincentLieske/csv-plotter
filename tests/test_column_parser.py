"""
Tests für den ColumnParser — Typ-Erkennung, Datums- und Zahlen-Parsing.
"""
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

    def test_threshold_date_above_60_percent(self):
        """70% Datum (7 von 10) → DATE"""
        s = pd.Series(["01.01.2024"] * 7 + ["irgendwas"] * 3)
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_threshold_date_below_60_percent(self):
        """50% Datum, 50% Zahlen → DATE (weil Date zuerst geprüft wird und 0.5 den DATE-Threshold nicht erreicht, aber Zahlen-Threshold 0.6 auch nicht → TEXT)"""
        s = pd.Series(["01.01.2024"] * 5 + ["1,5"] * 5)
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_threshold_numeric_above_60_percent(self):
        """70% deutsche Zahlen (7 von 10 ohne Datumsmatch) → NUMERIC"""
        s = pd.Series(["irgendwas"] * 3 + ["1,5"] * 7)
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_threshold_numeric_below_60_percent(self):
        """50% Zahlen (5 von 10) → TEXT"""
        s = pd.Series(["irgendwas"] * 5 + ["1,5"] * 5)
        assert ColumnParser.detect_column_type(s) == ColumnType.TEXT

    def test_threshold_english_dot_above_60_percent(self):
        """70% englische Punkt-Notation (7 von 10 ohne Datumsmatch) → NUMERIC"""
        s = pd.Series(["irgendwas"] * 3 + ["1.5"] * 7)
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_large_integers_without_separator(self):
        """Große ganze Zahlen ohne Tausendertrenner → NUMERIC"""
        s = pd.Series(["1000", "2000", "3000"])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC

    def test_mixed_date_and_numeric_more_date(self):
        """Gemischte Spalte mit mehr Datum als Zahlen (4 von 6 = 67%) → DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024", "24.12.2024", "01.05.2024", "1,5", "2,3"])
        assert ColumnParser.detect_column_type(s) == ColumnType.DATE

    def test_mixed_date_and_numeric_more_numeric(self):
        """Gemischte Spalte mit mehr Zahlen als Datum (5 von 6 = 83%) → NUMERIC"""
        s = pd.Series(["01.01.2024", "1,5", "2,3", "3,7", "4,1", "5,9"])
        assert ColumnParser.detect_column_type(s) == ColumnType.NUMERIC


class TestIsGermanNumber:
    """Direkte Tests für _is_german_number"""

    def test_simple_comma_number(self):
        """1,5 → True"""
        assert ColumnParser._is_german_number("1,5") is True

    def test_thousands_comma_number(self):
        """1.234,56 → True"""
        assert ColumnParser._is_german_number("1.234,56") is True

    def test_multi_thousands_comma_number(self):
        """1.000.000,00 → True"""
        assert ColumnParser._is_german_number("1.000.000,00") is True

    def test_english_dot_is_false(self):
        """1.5 → False"""
        assert ColumnParser._is_german_number("1.5") is False

    def test_integer_without_comma_is_false(self):
        """1234 → False"""
        assert ColumnParser._is_german_number("1234") is False

    def test_german_without_comma_is_false(self):
        """1.234 → False (Punkt-Tausender, aber kein Komma)"""
        assert ColumnParser._is_german_number("1.234") is False

    def test_text_is_false(self):
        """abc → False"""
        assert ColumnParser._is_german_number("abc") is False

    def test_empty_string_is_false(self):
        """"" → False"""
        assert ColumnParser._is_german_number("") is False

    def test_only_decimal_separator(self):
        """,5 → False (ungültiges Format)"""
        assert ColumnParser._is_german_number(",5") is False

    def test_only_thousands_dot(self):
        """1. → False"""
        assert ColumnParser._is_german_number("1.") is False


class TestGermanNumberToFloat:
    """Direkte Tests für _german_number_to_float"""

    def test_simple_comma(self):
        """1,5 → 1.5"""
        assert ColumnParser._german_number_to_float("1,5") == 1.5

    def test_thousands_and_comma(self):
        """1.234,56 → 1234.56"""
        assert ColumnParser._german_number_to_float("1.234,56") == 1234.56

    def test_multi_thousands(self):
        """1.000.000,00 → 1000000.0"""
        assert ColumnParser._german_number_to_float("1.000.000,00") == 1000000.0

    def test_large_number(self):
        """12.345.678,90 → 12345678.9"""
        assert ColumnParser._german_number_to_float("12.345.678,90") == 12345678.9


class TestHasIsoFormat:
    """Direkte Tests für _has_iso_format"""

    def test_pure_iso(self):
        """Reines ISO-Format → True"""
        s = pd.Series(["2024-01-05", "2024-03-15", "2024-12-24"])
        assert ColumnParser._has_iso_format(s) is True

    def test_german_date_is_false(self):
        """Deutsches DD.MM.YYYY → False"""
        s = pd.Series(["01.01.2024", "15.03.2024"])
        assert ColumnParser._has_iso_format(s) is False

    def test_mixed_iso_and_german(self):
        """ISO und deutsch gemischt → True (weil ISO > 50%)"""
        s = pd.Series(["2024-01-05", "2024-03-15", "01.01.2024"])
        assert ColumnParser._has_iso_format(s) is True

    def test_mixed_iso_below_threshold(self):
        """Weniger als 50% ISO → False"""
        s = pd.Series(["2024-01-05", "01.01.2024", "15.03.2024"])
        assert ColumnParser._has_iso_format(s) is False

    def test_empty_series(self):
        """Leere Series → False"""
        s = pd.Series([], dtype=object)
        assert ColumnParser._has_iso_format(s) is False

    def test_all_nan(self):
        """Nur NaN → False"""
        s = pd.Series([None, None])
        assert ColumnParser._has_iso_format(s) is False

    def test_short_year_iso(self):
        """ISO mit zweistelligem Jahr (24-01-05) → False (24 < 31, zählt nicht als ISO)"""
        s = pd.Series(["24-01-05", "24-03-15"])
        assert ColumnParser._has_iso_format(s) is False


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

    def test_thousands_dot_without_comma(self):
        """Tausenderpunkt ohne Dezimalkomma: '1.000' → 1000.0"""
        s = pd.Series(["1.000", "2.000"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1000.0
        assert result.iloc[1] == 2000.0

    def test_thousands_dot_multiple_groups(self):
        """Mehrere Tausenderpunkte ohne Komma: '1.234.567' → 1234567.0"""
        s = pd.Series(["1.234.567"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234567.0

    def test_english_dot_with_2_decimal_places(self):
        """Englische Dezimalzahl '1.23' → 1.23 (2 Ziffern nach Punkt → kein Tausenderpunkt)"""
        s = pd.Series(["1.23"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.23

    def test_mixed_german_thousands_and_english_dot(self):
        """Gemischte Formate in einer Spalte"""
        s = pd.Series(["1.234,56", "1234.56", "1,5"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234.56
        assert result.iloc[1] == 1234.56
        assert result.iloc[2] == 1.5

    def test_nan_and_valid_mixed(self):
        """NaN + gültige Werte"""
        s = pd.Series([np.nan, "1,5", np.nan, "2,3"])
        result = ColumnParser._parse_numeric_column(s)
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == 1.5
        assert pd.isna(result.iloc[2])
        assert result.iloc[3] == 2.3

    def test_boolean_strings_to_nan(self):
        """Boolesche Strings → NaN"""
        s = pd.Series(["true", "false", "1,5"])
        result = ColumnParser._parse_numeric_column(s)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 1.5

    def test_english_decimal_with_4_digits(self):
        """Englische Dezimalzahl '1.2345' (4 Nachkommastellen) → 1.2345 (alter Bug: wurde als deutscher Tausenderpunkt gewertet)"""
        s = pd.Series(["1.2345"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.2345

    def test_english_decimal_with_3_digits(self):
        """Englische Dezimalzahl '1.000' (3 Nachkommastellen, keine Komma in der Spalte) → 1000.0
        Hinweis: '1.000' allein ist ambig (1000 oder 1.000). Die Heuristik '3 Ziffern = Tausenderpunkt'
        behandelt es als Tausenderpunkt, was in der Praxis für deutsche CSV-Exporte die richtige Wahl ist."""
        s = pd.Series(["1.000"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1000.0

    def test_german_thousands_dot_without_comma_in_german_column(self):
        """'1.000' als deutscher Tausenderpunkt (weil andere Werte Komma haben) → 1000.0"""
        s = pd.Series(["1.000", "2,5"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1000.0
        assert result.iloc[1] == 2.5

    def test_multi_dot_german_thousands(self):
        """Mehrere Punkte wie '1.234.567' → deutsches Format erkannt → 1234567.0"""
        s = pd.Series(["1.234.567"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234567.0

    def test_english_decimal_multiple_values(self):
        """Rein englische Spalte mit mehreren Werten → korrekte floats"""
        s = pd.Series(["1.2345", "2.6789", "3.14159"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.2345
        assert result.iloc[1] == 2.6789
        assert result.iloc[2] == 3.14159

    def test_mixed_german_column_with_english_like_value(self):
        """Gemischte Spalte mit deutschem '1,5' und englischem '1.2345' → per-value: '1.2345' hat 4 Nachkommastellen → 1.2345, '1,5' → 1.5"""
        s = pd.Series(["1.2345", "1,5"])
        result = ColumnParser._parse_numeric_column(s)
        # '1.2345' hat kein Komma und 4 Ziffern nach Punkt → kein Tausenderpunkt (\.\d{3}$ matched nicht)
        assert result.iloc[0] == 1.2345
        # '1,5' hat Komma → deutsches Format
        assert result.iloc[1] == 1.5


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