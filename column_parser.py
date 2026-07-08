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

    @staticmethod
    def detect_column_type(column_values: pd.Series) -> ColumnType:
        """
        Erkennt automatisch, welcher Datentyp in der Spalte dominiert.

        Logik:
        1. Wenn pandas bereits als numeric erkannt → NUMERIC
        2. Sonst: Scanne erste 100 Werte auf Datumsformat
        3. Wenn > 60% Datumsformat → DATE
        4. Wenn > 60% können als Zahl geparst werden → NUMERIC
        5. Fallback → TEXT
        """
        # pd.read_csv(decimal=',') konvertiert deutsche Kommazahlen automatisch
        # → wenn schon numeric dtype, dann sicher Zahl
        if pd.api.types.is_numeric_dtype(column_values):
            return ColumnType.NUMERIC

        sample = column_values.dropna().astype(str).str.strip().head(100)
        if sample.empty:
            return ColumnType.TEXT

        # Zähle, wie viele Werte dem Datumsformat entsprechen
        date_hits = sample.apply(lambda v: bool(ColumnParser._DATE_PATTERN.match(v))).sum()
        if date_hits / len(sample) > 0.6:
            return ColumnType.DATE

        # Fallback: Versuche als Zahl zu parsen (mit deutschem Komma)
        numeric_hits = pd.to_numeric(
            sample.str.replace(',', '.', regex=False), errors='coerce'
        ).notna().sum()
        if numeric_hits / len(sample) > 0.6:
            return ColumnType.NUMERIC

        return ColumnType.TEXT

    @staticmethod
    def _parse_date_column(column_values: pd.Series) -> pd.Series:
        """
        Konvertiert eine Spalte in datetime64[ns] Format.

        - Erkennt automatisch dayfirst (DD.MM.YYYY vs MM.DD.YYYY)
        - Ungültige Datumsangaben werden zu NaT (Not a Time)
        """
        dayfirst = detect_dayfirst(column_values)
        return pd.to_datetime(column_values, dayfirst=dayfirst, errors='coerce')

    @staticmethod
    def _parse_numeric_column(column_values: pd.Series) -> pd.Series:
        """
        Konvertiert eine Spalte in float64 Format.

        Behandelt deutsche Dezimalkommas: "1,5" → 1.5
        Ungültige Zahlen werden zu NaN
        """
        # Falls schon numeric: kein parsing nötig
        if pd.api.types.is_numeric_dtype(column_values):
            return column_values

        # Sonst: String cleaning + Komma ersetzen + zu float konvertieren
        cleaned = column_values.astype(str).str.strip().str.replace(',', '.', regex=False)
        return pd.to_numeric(cleaned, errors='coerce')
