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


class NumericStyle(Enum):
    """Stil der Zahlen-Notation in einer Spalte"""
    GERMAN_COMMA = 'german_comma'   # Komma als Dezimaltrenner, Punkt als Tausenderpunkt
    ENGLISH_DOT = 'english_dot'     # Punkt als Dezimaltrenner


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
        r'^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$'    # DD.MM.YYYY, DD-MM-YY, etc.
        r'|^\d{4}[./-]\d{1,2}[./-]\d{1,2}$'     # YYYY-MM-DD, YYYY/MM/DD, etc.
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

    _THOUSANDS_COMMA = re.compile(r'^[+-]?\d{1,3}(\.\d{3})*,\d*$')

    @staticmethod
    def _is_german_number(s: str) -> bool:
        """Prüft, ob ein String eine deutsche Zahl ist (z.B. 1,5 oder 1.234,56)

        - Komma als Dezimaltrenner (z.B. '1,5', '-1,5', '+1,5')
        - Optional Tausenderpunkte (z.B. '1.234,56', '-1.234,56')
        - Komma ohne Dezimalstellen: '10,' → True (wird von _parse_single_numeric unterstützt)
        - Doppelte Punkte: '1..234,56' → True (wird von _parse_single_numeric unterstützt)
        - Kein Komma: '1234' → False (wird von to_numeric bereits erfasst)
        - Punkt-Zahl: '1.5' → False (englische Notation)

        Hinweis: Die Heuristik ist absichtlich tolerant gegenüber Randfällen
        wie '10,' oder '1..234,56', da sie für Mehrheitsentscheide verwendet wird.
        """
        if ',' not in s:
            return False
        # "1,5", "-1,5", "+1,5" oder "10," → einfaches deutsches Format
        if '.' not in s:
            return bool(re.match(r'^[+-]?\d+,(\d+)?$', s))
        # "1.234,56", "-1.234,56" oder "+1.234,56" → deutsches Format mit Tausenderpunkten
        # Nutzt dieselbe Heuristik wie _is_thousands_dot: prüft ob alle Punkte
        # genau 3 Ziffern folgen haben (Tausenderpunkte)
        # Doppelte Punkte (z.B. "1..234,56") werden toleriert, indem wir
        # doppelte Punkte vor dem Matchen entfernen
        cleaned = re.sub(r'\.+', '.', s)
        return bool(ColumnParser._THOUSANDS_COMMA.match(cleaned))

    @staticmethod
    def _is_english_number(s: str) -> bool:
        """Prüft, ob ein String eine englische Zahl mit Dezimalpunkt ist (z.B. 1.5 oder 1234.567).

        - Punkt als Dezimaltrenner (z.B. '1.5', '-1.5', '1234.567')
        - Kein Komma im String (sonst wäre es deutsch)
        - Der letzte Punkt hat != 3 folgende Ziffern (sonst wäre es ambig als Tausenderpunkt)

        Returns:
            True wenn der String wie eine englische Zahl aussieht
        """
        if ',' in s:
            return False
        if '.' not in s:
            return False
        # '1.000', '1.234.567' → ambig (Tausenderpunkte möglich) → nicht als englisch zählen
        if ColumnParser._is_thousands_dot(s):
            return False
        # Mehrere Punkte → Tausenderpunkte (deutsch), nicht englisch
        if s.count('.') > 1:
            return False
        # Ein Punkt mit != 3 Nachkommastellen → englischer Dezimalpunkt
        try:
            float(s)
            return True
        except ValueError:
            return False

    @staticmethod
    def _detect_numeric_style(column_values: pd.Series) -> NumericStyle:
        """
        Erkennt anhand einer Stichprobe, ob die Spalte deutsche (Komma)
        oder englische (Punkt) Zahlen verwendet.

        Heuristik (analog zu detect_dayfirst):
        - Werte mit Komma → German-Evidenz (eindeutig deutsch)
        - Werte mit einzelnem Punkt und != 3 Nachkommastellen → English-Evidenz
        - Werte mit mehreren Punkten → German-Evidenz (Tausenderpunkte)
        - Werte mit Punkt und 3 Nachkommastellen → ambig → werden ignoriert
        - Werte ohne Punkt und Komma (Integers) → keine Evidenz
        - Fallback: GERMAN_COMMA (weil CSV mit decimal=',' gelesen wurde)

        Returns:
            NumericStyle.GERMAN_COMMA oder NumericStyle.ENGLISH_DOT
        """
        sample = column_values.dropna().astype(str).str.strip().head(100)
        if sample.empty:
            return NumericStyle.GERMAN_COMMA

        german_evidence = 0
        english_evidence = 0

        for val in sample:
            if ',' in val:
                # Komma vorhanden → deutsches Format (auch "1.234,56")
                if ColumnParser._is_german_number(val):
                    german_evidence += 1
            elif '.' in val:
                if val.count('.') > 1:
                    # Mehrere Punkte → Tausenderpunkte (deutsch)
                    german_evidence += 1
                elif not ColumnParser._is_thousands_dot(val):
                    # Ein Punkt mit != 3 folgenden Ziffern → englischer Dezimalpunkt
                    if ColumnParser._is_english_number(val):
                        english_evidence += 1
                # Ein Punkt mit 3 Ziffern → ambig (z.B. "1.000") → ignorieren
            # Weder Punkt noch Komma → Integer → keine Evidenz

        # Majority-Vote: German gewinnt bei Gleichstand (Fallback auf deutsches CSV-Format)
        return NumericStyle.GERMAN_COMMA if german_evidence >= english_evidence else NumericStyle.ENGLISH_DOT

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
        """Prüft, ob die Werte überwiegend im ISO-Format (YYYY-MM-DD) vorliegen.

        Threshold: > 60% ISO-Format (konsistent mit detect_column_type).
        """
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
        return iso_count / len(sample) > 0.6

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
    def _is_thousands_dot(s: str) -> bool:
        """
        Prüft, ob ein Punkt als Tausenderpunkt zu werten ist.
        
        Heuristik: Wenn dem letzten Punkt genau 3 Ziffern folgen, handelt es sich
        um einen Tausenderpunkt (z.B. "1.000", "1.234.567").
        Ein Punkt mit != 3 folgenden Ziffern ist ein Dezimalpunkt (z.B. "1.5", "1.2345").
        """
        return bool(re.search(r'\.\d{3}$', s))

    @staticmethod
    def _parse_single_numeric(value: str) -> float:
        """
        Parst einen einzelnen String-Wert in einen float.

        Unterstützte Formate:
        - Deutsch mit Komma: "1,5" → 1.5, "-1,5" → -1.5
        - Deutsch mit Tausenderpunkt + Komma: "1.234,56" → 1234.56
        - Deutsch mit Tausenderpunkt ohne Komma: "1.000" → 1000.0, "1.234.567" → 1234567.0
        - Englisch mit Punkt: "1.5" → 1.5, "1234.56" → 1234.56, "-1.5" → -1.5
        - Integer: "42" → 42.0

        Returns:
            float oder NaN bei ungültigen Werten
        """
        try:
            value_str = str(value)
            if not value_str or value_str == 'nan':
                return float('nan')
            if ',' in value_str:
                # Deutsches Format mit Komma (z.B. "1,5" oder "-1,5")
                return float(value_str.replace('.', '').replace(',', '.'))
            elif '.' in value_str and ColumnParser._is_thousands_dot(value_str):
                # Tausenderpunkt ohne Komma (z.B. "1.000", "-1.000")
                return float(value_str.replace('.', ''))
            else:
                # Normales Integer, englisches Float oder ungültig
                return float(value_str)
        except (ValueError, TypeError):
            return float('nan')

    @staticmethod
    def _parse_numeric_column(column_values: pd.Series) -> pd.Series:
        """
        Konvertiert eine Spalte in float64 Format.

        Erkennt automatisch, ob die Spalte deutsche (Komma) oder englische (Punkt)
        Zahlen verwendet (Heuristik über alle Werte, analog zu detect_dayfirst).

        Behandelt deutsche Dezimalkommas: "1,5" → 1.5
        Behandelt deutsche Tausendertrenner: "1.234,56" → 1234.56
        Englische Punkt-Notation: "1234.56" → 1234.56
        Negative Zahlen: "-1,5" → -1.5
        Ungültige Werte werden zu NaN
        """
        # Falls schon numeric: kein parsing nötig
        if pd.api.types.is_numeric_dtype(column_values):
            return column_values

        # String-Werte trimmen
        cleaned = column_values.astype(str).str.strip()

        # Erkenne, ob die Spalte deutsches oder englisches Format verwendet
        style = ColumnParser._detect_numeric_style(cleaned)

        if style == NumericStyle.GERMAN_COMMA:
            # Deutsches Format: Komma = Dezimaltrenner, Punkte entfernen
            transformed = cleaned.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        else:
            # Englisches Format: Punkt = Dezimaltrenner, Kommas entfernen
            transformed = cleaned.str.replace(',', '', regex=False)

        return pd.to_numeric(transformed, errors='coerce')