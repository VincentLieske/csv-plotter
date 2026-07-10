"""
Tests für column_parser.py — spezielle CSV-Formate (Anführungszeichen, Sonderzeichen).
"""
import pandas as pd
from column_parser import ColumnParser, ColumnType
from tests.helpers import (
    QUOTED_NUMERIC_CSV, QUOTED_TEXT_CSV, QUOTED_MIXED_CSV,
    QUOTED_COMMA_IN_TEXT, QUOTED_MULTILINE
)


class TestDetectColumnTypeQuoted:
    """Typerkennung mit Werten, die Anführungszeichen enthalten"""

    def test_quoted_numeric_values(self):
        """'\"1,5\"' → NUMERIC (Anführungszeichen werden von pd.read_csv entfernt)"""
        # Simuliert, wie pd.read_csv mit Anführungszeichen umgeht
        s = pd.Series(["1,5", "10,2", "20,3"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.NUMERIC

    def test_quoted_text_values(self):
        """'\"Müller\"' → TEXT"""
        s = pd.Series(["Müller", "Schmidt", "Bauer"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.TEXT

    def test_quoted_mixed_types(self):
        """Anführungszeichen mit gemischten Typen → korrekte Erkennung"""
        s = pd.Series(["01.01.2024", "22,5", "18,3"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.NUMERIC  # 2/3 = 66% NUMERIC > 60%

    def test_quoted_dates(self):
        """'\"01.01.2024\"' → DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024", "24.12.2024"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.DATE


class TestParseNumericQuoted:
    """Zahlen-Parsing mit Werten, die Anführungszeichen enthalten"""

    def test_quoted_german_comma(self):
        """'\"1,5\"' → 1.5"""
        s = pd.Series(["1,5", "2,3", "4,7"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert result.iloc[1] == 2.3
        assert result.iloc[2] == 4.7

    def test_quoted_thousands_separator(self):
        """'\"1.234,56\"' → 1234.56"""
        s = pd.Series(["1.234,56", "7.890,12"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234.56
        assert result.iloc[1] == 7890.12

    def test_quoted_english_dot(self):
        """'\"1234.56\"' → 1234.56"""
        s = pd.Series(["1234.56", "7890.12"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1234.56
        assert result.iloc[1] == 7890.12


class TestParseDateQuoted:
    """Datums-Parsing mit Werten, die Anführungszeichen enthalten"""

    def test_quoted_german_date(self):
        """'\"01.01.2024\"' → datetime"""
        s = pd.Series(["01.01.2024", "15.03.2024"])
        result = ColumnParser._parse_date_column(s)
        assert result.iloc[0] == pd.Timestamp("2024-01-01")
        assert result.iloc[1] == pd.Timestamp("2024-03-15")

    def test_quoted_iso_date(self):
        """'\"2024-01-05\"' → datetime"""
        s = pd.Series(["2024-01-05", "2024-03-15"])
        result = ColumnParser._parse_date_column(s)
        assert result.iloc[0] == pd.Timestamp("2024-01-05")
        assert result.iloc[1] == pd.Timestamp("2024-03-15")


class TestParseColumnToSeriesQuoted:
    """parse_column_to_series mit Anführungszeichen-Werten"""

    def test_quoted_numeric_result(self):
        """Anführungszeichen-Zahlen → NUMERIC"""
        s = pd.Series(["1,5", "2,3", "4,7"])
        result = ColumnParser.parse_column_to_series(s, "Werte")
        assert result.column_type == ColumnType.NUMERIC
        assert result.series.iloc[0] == 1.5

    def test_quoted_date_result(self):
        """Anführungszeichen-Daten → DATE"""
        s = pd.Series(["01.01.2024", "15.03.2024"])
        result = ColumnParser.parse_column_to_series(s, "Datum")
        assert result.column_type == ColumnType.DATE
        assert result.series.iloc[0] == pd.Timestamp("2024-01-01")

    def test_quoted_text_result(self):
        """Anführungszeichen-Text → TEXT"""
        s = pd.Series(["Hallo", "Welt", "Test"])
        result = ColumnParser.parse_column_to_series(s, "Notiz")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "Hallo"


class TestSpecialCharacters:
    """Tests für Sonderzeichen in CSV-Werten"""

    def test_umlauts_in_text(self):
        """Umlaute in Text-Spalte → korrekt erhalten"""
        s = pd.Series(["Müller", "Schmidt", "Bäuerle"])
        result = ColumnParser.parse_column_to_series(s, "Name")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "Müller"
        assert result.series.iloc[2] == "Bäuerle"

    def test_special_chars_in_text(self):
        """Sonderzeichen wie &, %, $ in Text-Spalte"""
        s = pd.Series(["Test & Co.", "Wert (100%)", "Preis: 50$"])
        result = ColumnParser.parse_column_to_series(s, "Beschreibung")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "Test & Co."
        assert result.series.iloc[1] == "Wert (100%)"
        assert result.series.iloc[2] == "Preis: 50$"

    def test_leading_trailing_whitespace_in_text(self):
        """Whitespace in Text-Spalte wird getrimmt"""
        s = pd.Series(["  Hallo  ", "  Welt  ", "  Test  "])
        result = ColumnParser.parse_column_to_series(s, "Notiz")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "Hallo"
        assert result.series.iloc[1] == "Welt"

    def test_empty_strings_in_text(self):
        """Leere Strings in Text-Spalte → leerer String"""
        s = pd.Series(["Hallo", "", "Welt"])
        result = ColumnParser.parse_column_to_series(s, "Notiz")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "Hallo"
        assert result.series.iloc[1] == ""
        assert result.series.iloc[2] == "Welt"

    def test_mixed_whitespace_and_values(self):
        """Whitespace + Werte → korrekt getrimmt"""
        s = pd.Series(["  1,5  ", "  2,3  ", "  4,7  "])
        result = ColumnParser.parse_column_to_series(s, "Werte")
        assert result.column_type == ColumnType.NUMERIC
        assert result.series.iloc[0] == 1.5
        assert result.series.iloc[1] == 2.3

    def test_tab_characters_in_text(self):
        """Tabs in Text-Spalte → werden nicht entfernt (nur Whitespace-Trim)"""
        s = pd.Series(["Hallo\tWelt", "Test\tWert"])
        result = ColumnParser.parse_column_to_series(s, "Notiz")
        assert result.column_type == ColumnType.TEXT
        assert "\t" in result.series.iloc[0]

    def test_very_long_text(self):
        """Sehr langer Text → wird nicht abgeschnitten"""
        long_text = "A" * 10000
        s = pd.Series([long_text])
        result = ColumnParser.parse_column_to_series(s, "Lang")
        assert result.column_type == ColumnType.TEXT
        assert len(result.series.iloc[0]) == 10000

    def test_percentage_sign_in_numeric(self):
        """Prozentzeichen in Zahlen-Spalte → NaN (keine gültige Zahl)"""
        s = pd.Series(["50%", "75%", "100%"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.isna().all()

    def test_currency_symbols_in_numeric(self):
        """Währungssymbole in Zahlen-Spalte → NaN"""
        s = pd.Series(["€50", "$75", "100€"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.isna().all()

    def test_scientific_notation(self):
        """Wissenschaftliche Notation → NUMERIC"""
        s = pd.Series(["1e5", "2.5e-3", "1.0E+2"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.NUMERIC

    def test_scientific_notation_parsed(self):
        """Wissenschaftliche Notation → korrekt geparst"""
        s = pd.Series(["1e5", "2.5e-3", "1.0E+2"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 100000.0
        assert result.iloc[1] == 0.0025
        assert result.iloc[2] == 100.0


class TestEdgeCaseFormats:
    """Tests für extreme/ungültige CSV-Formate"""

    def test_only_whitespace_values(self):
        """Nur Whitespace → TEXT"""
        s = pd.Series(["   ", "\t", "\n"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.TEXT

    def test_only_special_chars(self):
        """Nur Sonderzeichen → TEXT"""
        s = pd.Series(["!!!", "@@@", "###"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.TEXT

    def test_unicode_characters(self):
        """Unicode-Zeichen (z.B. Emoji) → TEXT"""
        s = pd.Series(["Test 😊", "Wert 🎉", "Daten 📊"])
        result = ColumnParser.parse_column_to_series(s, "Unicode")
        assert result.column_type == ColumnType.TEXT
        assert "😊" in result.series.iloc[0]

    def test_mixed_encoding_latin1_chars(self):
        """Latin-1 Sonderzeichen (z.B. °, ±, µ) → TEXT"""
        s = pd.Series(["25°C", "±5%", "100µg"])
        result = ColumnParser.parse_column_to_series(s, "Einheiten")
        assert result.column_type == ColumnType.TEXT
        assert result.series.iloc[0] == "25°C"

    def test_negative_sign_variants(self):
        """Verschiedene Minus-Zeichen → NUMERIC"""
        # Normales Minus
        s1 = pd.Series(["-1,5", "-2,3"])
        assert ColumnParser.detect_column_type(s1) == ColumnType.NUMERIC

    def test_plus_sign_numbers(self):
        """Plus-Zeichen vor Zahlen → NUMERIC"""
        s = pd.Series(["+1,5", "+2,3"])
        result = ColumnParser.detect_column_type(s)
        assert result == ColumnType.NUMERIC

    def test_plus_sign_numbers_parsed(self):
        """Plus-Zeichen vor Zahlen → korrekt geparst"""
        s = pd.Series(["+1,5", "+2,3"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.iloc[0] == 1.5
        assert result.iloc[1] == 2.3

    def test_multiple_decimal_separators(self):
        """Mehrere Dezimaltrenner → NaN"""
        s = pd.Series(["1,5,6", "2,3,4"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.isna().all()

    def test_letters_in_numeric_string(self):
        """Buchstaben in Zahlen-String → NaN"""
        s = pd.Series(["1a5", "2b3"])
        result = ColumnParser._parse_numeric_column(s)
        assert result.isna().all()