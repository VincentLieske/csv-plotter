"""
Spalten-Parser für CSV-Dateien — Typ-Erkennung und Parsing.

Erkennt automatisch, ob eine Spalte Datum, Zahl oder Text enthält
und konvertiert die Werte in das richtige Format.
"""
from dataclasses import dataclass
from enum import Enum
import re

import pandas as pd

from date_format_detector import detect_dayfirst


class ColumnType(Enum):
    """Mögliche Spaltentypen"""
    DATE = 'date'
    NUMERIC = 'numeric'
    TEXT = 'text'


@dataclass
class ColumnResult:
    """Ergebnis nach dem Parsen einer Spalte"""
    series: pd.Series          # Die geparste Serie (datetime64, float64, string, etc.)
    column_type: ColumnType    # Der erkannte Datentyp
    column_name: str           # Der Spaltenname (Header)


class ColumnParser:
    """
    Parst CSV-Spalten und erkennt ihren Datentyp automatisch.

    Voraussetzung: CSV wurde mit pd.read_csv(sep=';', decimal=',') gelesen.
    """

    # Regex für Datumsformate: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YY, etc.
    _DATE_PATTERN = re.compile(
        r'^\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$'    # DD.MM.YYYY, DD-MM-YY, etc.
        r'|^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$'     # YYYY-MM-DD, YYYY/MM/DD, etc.
    )

    @staticmethod
    def parse_column_to_series(column_values: pd.Series, column_name: str = "") -> ColumnResult:
        """
        Parst eine Spalte und erkennt ihren Typ automatisch.

        Parameters:
            column_values: Die rohen Werte aus der CSV (pd.Series)
            column_name: Der Spaltenname (z.B. Spaltenkopf)

        Returns:
            ColumnResult mit geparster Series, erkanntem Typ und Spaltenname
        """
        column_type = ColumnParser.detect_column_type(column_values)

        # Parse je nach erkanntem Typ
        if column_type == ColumnType.DATE:
            parsed = ColumnParser._parse_date_column(column_values)
        elif column_type == ColumnType.NUMERIC:
            parsed = ColumnParser._parse_numeric_column(column_values)
        else:
            # TEXT: nur Whitespace trimmen, NaN-Werte als leere Strings
            parsed = column_values.fillna('').astype(str).str.strip()

        return ColumnResult(series=parsed, column_type=column_type, column_name=column_name)

    _THOUSANDS_COMMA = re.compile(r'^\d{1,3}(\.\d{3})*,\d+$')

    @staticmethod
    def _is_german_number(s: str) -> bool:
        """Prüft, ob ein String eine deutsche Zahl ist (z.B. 1,5 oder 1.234,56)"""
        # Einfaches Komma: "1,5" → True
        # Tausenderpunkt + Komma: "1.234,56" → True
        # Kein Komma: "1234" → False (wird von to_numeric bereits erfasst)
        # Punkt-Zahl: "1.5" → False (englische Notation)
        if ',' not in s:
            return False
        # "1,5" → einfaches deutsches Format
        if '.' not in s:
            return bool(re.match(r'^\d+,\d+$', s))
        # "1.234,56" → deutsches Format mit Tausenderpunkten
        return bool(ColumnParser._THOUSANDS_COMMA.match(s))

    @staticmethod
    def _german_number_to_float(s: str) -> float:
        """Wandelt eine deutsche Zahl in einen float um (z.B. '1.234,56' → 1234.56)"""
        # Entferne Tausenderpunkte, ersetze Komma durch Punkt
        return float(s.replace('.', '').replace(',', '.'))

    @staticmethod
    def detect_column_type(column_values: pd.Series) -> ColumnType:
        """
        Erkennt automatisch, welcher Datentyp in der Spalte dominiert.

        Logik:
        1. Wenn pandas bereits als numeric erkannt UND nicht all-NaN → NUMERIC
        2. Sonst: Scanne erste 100 Werte auf Datumsformat
        3. Wenn > 60% Datumsformat → DATE
        4. Wenn > 60% können als Zahl geparst werden (inkl. deutscher Tausenderpunkt-Formate) → NUMERIC
        5. Fallback → TEXT
        """
        # pd.read_csv(decimal=',') konvertiert deutsche Kommazahlen automatisch
        # → wenn schon numeric dtype, dann sicher Zahl
        # Aber: Float-Spalte mit nur NaN-Werten ist kein NUMERIC
        if pd.api.types.is_numeric_dtype(column_values):
            if column_values.notna().any():
                return ColumnType.NUMERIC
            else:
                return ColumnType.TEXT

        sample = column_values.dropna().astype(str).str.strip().head(100)
        if sample.empty:
            return ColumnType.TEXT

        # Zähle, wie viele Werte dem Datumsformat entsprechen
        date_hits = sample.apply(lambda v: bool(ColumnParser._DATE_PATTERN.match(v))).sum()
        if date_hits / len(sample) > 0.6:
            return ColumnType.DATE

        # Fallback: Versuche als Zahl zu parsen (mit deutschem Komma + Tausenderpunkten)
        numeric_hits = (
            sample
            .apply(lambda v: ColumnParser._is_german_number(v))
            .sum()
        )
        if numeric_hits / len(sample) > 0.6:
            return ColumnType.NUMERIC

        # Zusätzlich: Einfache to_numeric (für englische Punkt-Notation und Integers)
        numeric_hits_simple = pd.to_numeric(
            sample.str.replace(',', '.', regex=False), errors='coerce'
        ).notna().sum()
        if numeric_hits_simple / len(sample) > 0.6:
            return ColumnType.NUMERIC

        return ColumnType.TEXT

    @staticmethod
    def _has_iso_format(column_values: pd.Series) -> bool:
        """Prüft, ob die Werte überwiegend im ISO-Format (YYYY-MM-DD) vorliegen."""
        sample = column_values.dropna().astype(str).str.strip().head(50)
        if sample.empty:
            return False
        iso_count = 0
        for val in sample:
            parts = re.split(r"[-/.]", val)
            if len(parts) == 3:
                try:
                    first = int(parts[0])
                    if first > 31:  # 4-stellige Jahreszahl
                        iso_count += 1
                except ValueError:
                    pass
        return iso_count / len(sample) > 0.5

    @staticmethod
    def _parse_date_column(column_values: pd.Series) -> pd.Series:
        """
        Konvertiert eine Spalte in datetime64[ns] Format.

        - Erkennt automatisch dayfirst (DD.MM.YYYY vs MM.DD.YYYY)
        - ISO-Format (YYYY-MM-DD) wird automatisch ohne dayfirst erkannt
        - Ungültige Datumsangaben werden zu NaT (Not a Time)
        """
        # Prüfe zuerst auf ISO-Format (YYYY-MM-DD), das kein dayfirst benötigt
        if ColumnParser._has_iso_format(column_values):
            return pd.to_datetime(column_values, dayfirst=False, errors='coerce')

        dayfirst = detect_dayfirst(column_values)
        return pd.to_datetime(column_values, dayfirst=dayfirst, errors='coerce')

    @staticmethod
    def _parse_numeric_column(column_values: pd.Series) -> pd.Series:
        """
        Konvertiert eine Spalte in float64 Format.

        Behandelt deutsche Dezimalkommas: "1,5" → 1.5
        Behandelt Tausendertrenner: "1.234,56" → 1234.56
        Ungültige Zahlen werden zu NaN
        """
        # Falls schon numeric: kein parsing nötig
        if pd.api.types.is_numeric_dtype(column_values):
            return column_values

        # Sonst: String cleaning
        cleaned = column_values.astype(str).str.strip()

        # Entferne Tausendertrenner (Punkt), aber nur wenn ein Komma als Dezimaltrenner existiert
        # "1.234,56" → "1234,56" → "1234.56"
        # "1234.56"  → bleibt "1234.56" (kein Komma, Punkt ist Dezimaltrenner)
        has_comma = cleaned.str.contains(',', regex=False)
        cleaned = cleaned.where(~has_comma, cleaned.str.replace('.', '', regex=False))

        # Ersetze deutsches Dezimalkomma durch Punkt
        cleaned = cleaned.str.replace(',', '.', regex=False)

        return pd.to_numeric(cleaned, errors='coerce')
