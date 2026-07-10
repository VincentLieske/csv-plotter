"""
Spalten-Parser für CSV-Dateien — Typ-Erkennung und Parsing.

Erkennt automatisch, ob eine Spalte Datum, Zahl oder Text enthält
und konvertiert die Werte in das richtige Format.

Konvertierungs-Policy (gilt für Datums- und Zahlenspalten gleichermaßen):
- Das Format (dayfirst vs. monthfirst, deutsches Komma vs. englischer Punkt)
  wird per Heuristik über eine Stichprobe der Spalte ermittelt. Es wird davon
  ausgegangen, dass das Format innerhalb einer Datei konsistent ist — über
  mehrere Dateien hinweg wird das je Datei neu erkannt und kann abweichen.
- Einzelne Werte, die sich mit dem erkannten Format trotzdem nicht
  konvertieren lassen, werden NICHT verworfen, sondern als NaN/NaT behandelt
  und über `ColumnResult.warnings` gemeldet (eine Warnung pro Spalte mit
  Anzahl und Beispielwerten). Der Aufrufer gibt diese Warnungen aus.
- Wenn die Heuristik bei einer Datei danebenliegt, kann sie über die
  Parameter `dayfirst_override` / `decimal_override` (CLI: `--dayfirst`,
  `--decimal`) für den gesamten Lauf übersteuert werden, statt sie zu
  erraten. Viele Warnungen sind das Signal dafür, dass eine Übersteuerung
  oder eine Korrektur der Quelldaten nötig ist.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import re
import warnings

import pandas as pd

from date_format_detector import detect_dayfirst


# Größe der Stichprobe, anhand der Datums-/Zahlenformat-Heuristiken über eine
# Spalte entscheiden. Groß genug für stabile Mehrheitsentscheide, klein genug
# um bei großen Dateien nicht jede Zeile scannen zu müssen.
_HEURISTIC_SAMPLE_SIZE = 100
# Kleinere Stichprobe für die ISO-Datumserkennung (_has_iso_format): dort reicht
# ein kleinerer Ausschnitt, da das Muster (Jahr > 31 an erster Stelle) eindeutiger ist.
_ISO_SAMPLE_SIZE = 50
# Schwellwert für Mehrheitsentscheide (z.B. "Spalte ist DATE, wenn >60% der
# Stichprobe wie ein Datum aussehen"). >50% würde bei knappen Mehrheiten zu
# instabilen Entscheidungen führen; 60% verlangt eine klarere Mehrheit.
_MAJORITY_THRESHOLD = 0.6


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
    # Warnungen zu Werten, die nicht konvertiert werden konnten und als NaN/NaT
    # behandelt wurden. Siehe Modul-Docstring für die Konvertierungs-Policy.
    warnings: List[str] = field(default_factory=list)


class ColumnParser:
    """
    Parst CSV-Spalten und erkennt ihren Datentyp automatisch.

    Voraussetzung: CSV wurde mit pd.read_csv(sep=';', dtype=str) gelesen.
    Das Zahlenformat (deutsches Komma vs. englischer Punkt) wird von
    dieser Klasse selbst per Heuristik erkannt (siehe _detect_numeric_style).
    """

    # Regex für Datumsformate: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YY, etc.
    _DATE_PATTERN = re.compile(
        r'^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$'    # DD.MM.YYYY, DD-MM-YY, etc.
        r'|^\d{4}[./-]\d{1,2}[./-]\d{1,2}$'     # YYYY-MM-DD, YYYY/MM/DD, etc.
    )

    @staticmethod
    def parse_column_to_series(
        column_values: pd.Series,
        column_name: str = "",
        dayfirst_override: Optional[bool] = None,
        decimal_override: Optional[NumericStyle] = None,
    ) -> ColumnResult:
        """
        Parst eine Spalte und erkennt ihren Typ automatisch.

        Parameters:
            column_values: Die rohen Werte aus der CSV (pd.Series)
            column_name: Der Spaltenname (z.B. Spaltenkopf)
            dayfirst_override: Übersteuert die dayfirst-Heuristik für Datumsspalten
                (True=Tag zuerst, False=Monat zuerst, None=Heuristik verwenden)
            decimal_override: Übersteuert die Dezimaltrenner-Heuristik für Zahlenspalten
                (None=Heuristik verwenden)

        Returns:
            ColumnResult mit geparster Series, erkanntem Typ, Spaltenname und
            Warnungen zu nicht konvertierbaren Werten (siehe Modul-Docstring)
        """
        column_type = ColumnParser.detect_column_type(column_values)

        # Parse je nach erkanntem Typ
        warnings: List[str] = []
        if column_type == ColumnType.DATE:
            parsed = ColumnParser._parse_date_column(column_values, dayfirst_override)
            warnings = ColumnParser._collect_conversion_warnings(column_values, parsed, "Datum")
        elif column_type == ColumnType.NUMERIC:
            parsed = ColumnParser._parse_numeric_column(column_values, decimal_override)
            warnings = ColumnParser._collect_conversion_warnings(column_values, parsed, "Zahl")
        else:
            # TEXT: nur Whitespace trimmen, NaN-Werte als leere Strings
            parsed = column_values.fillna('').astype(str).str.strip()

        return ColumnResult(series=parsed, column_type=column_type, column_name=column_name, warnings=warnings)

    @staticmethod
    def _collect_conversion_warnings(original: pd.Series, parsed: pd.Series, kind: str) -> List[str]:
        """
        Vergleicht Roh- und Ergebnis-Serie und meldet Werte, die trotz erkanntem
        Format nicht konvertiert werden konnten (neu entstandene NaN/NaT).

        Parameters:
            original: Die Roh-Werte vor dem Parsen (als Strings)
            parsed: Die Werte nach dem Parsen (datetime64 oder float64)
            kind: Bezeichnung für die Warnmeldung, z.B. "Datum" oder "Zahl"

        Returns:
            Liste mit maximal einer Warnmeldung (Anzahl + Beispielwerte)
        """
        original_str = original.astype(str).str.strip()
        was_present = original.notna() & (original_str != '')
        newly_failed = was_present & parsed.isna()

        failed_values = original_str[newly_failed].unique()
        if len(failed_values) == 0:
            return []

        examples = ', '.join(repr(v) for v in failed_values[:5])
        return [
            f"{len(failed_values)} Wert(e) konnten nicht als {kind} interpretiert werden "
            f"und werden als NaN behandelt (z.B. {examples})"
        ]

    _THOUSANDS_COMMA = re.compile(r'^[+-]?\d{1,3}(\.\d{3})*,\d*$')

    @staticmethod
    def _is_german_number(s: str) -> bool:
        """Prüft, ob ein String eine deutsche Zahl ist (z.B. 1,5 oder 1.234,56)

        - Komma als Dezimaltrenner (z.B. '1,5', '-1,5', '+1,5')
        - Optional Tausenderpunkte (z.B. '1.234,56', '-1.234,56')
        - Komma ohne Dezimalstellen: '10,' → True
        - Doppelte Punkte: '1..234,56' → True
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
        sample = column_values.dropna().astype(str).str.strip().head(_HEURISTIC_SAMPLE_SIZE)
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
        4. Wenn > 60% als Zahl erkannt (deutsches Komma/Tausenderpunkte ODER
           einfache Punkt-/Integer-Notation, pro Wert kombiniert) → NUMERIC
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

        sample = column_values.dropna().astype(str).str.strip().head(_HEURISTIC_SAMPLE_SIZE)
        if sample.empty:
            return ColumnType.TEXT

        # Zähle, wie viele Werte dem Datumsformat entsprechen
        date_hits = sample.apply(lambda v: bool(ColumnParser._DATE_PATTERN.match(v))).sum()
        if date_hits / len(sample) > _MAJORITY_THRESHOLD:
            return ColumnType.DATE

        # Zahl, wenn deutsches Format (Komma, ggf. Tausenderpunkte) ODER einfache
        # Notation (englischer Punkt, Integer) zutrifft — beide Heuristiken werden
        # pro Wert kombiniert, damit gemischte Spalten (z.B. teils deutsch, teils
        # englisch notiert) nicht an einem einzelnen Check vorbeirutschen.
        numeric_hits = (
            sample.apply(ColumnParser._is_german_number)
            | pd.to_numeric(sample.str.replace(',', '.', regex=False), errors='coerce').notna()
        ).sum()
        if numeric_hits / len(sample) > _MAJORITY_THRESHOLD:
            return ColumnType.NUMERIC

        return ColumnType.TEXT

    @staticmethod
    def _has_iso_format(column_values: pd.Series) -> bool:
        """Prüft, ob die Werte überwiegend im ISO-Format (YYYY-MM-DD) vorliegen.

        Threshold: > 60% ISO-Format (konsistent mit detect_column_type).
        """
        sample = column_values.dropna().astype(str).str.strip().head(_ISO_SAMPLE_SIZE)
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
    def _parse_date_column(column_values: pd.Series, dayfirst_override: Optional[bool] = None) -> pd.Series:
        """
        Konvertiert eine Spalte in datetime64[ns] Format.

        - dayfirst_override erzwingt Tag- bzw. Monat-zuerst für die gesamte Spalte
          (übersteuert die Heuristik, siehe Modul-Docstring)
        - Sonst: Erkennt automatisch dayfirst (DD.MM.YYYY vs MM.DD.YYYY); ISO-Format
          (YYYY-MM-DD) wird ohne dayfirst erkannt
        - Ungültige Datumsangaben werden zu NaT (Not a Time); parse_column_to_series
          meldet daraus resultierende Warnungen
        """
        if dayfirst_override is not None:
            return ColumnParser._to_datetime_quiet(column_values, dayfirst=dayfirst_override)

        # Prüfe zuerst auf ISO-Format (YYYY-MM-DD), das kein dayfirst benötigt
        if ColumnParser._has_iso_format(column_values):
            return ColumnParser._to_datetime_quiet(column_values, dayfirst=False)

        dayfirst = detect_dayfirst(column_values)
        return ColumnParser._to_datetime_quiet(column_values, dayfirst=dayfirst)

    @staticmethod
    def _to_datetime_quiet(column_values: pd.Series, dayfirst: bool) -> pd.Series:
        """
        Wrapper um pd.to_datetime(errors='coerce'), der die pandas-Warnung
        "Could not infer format" unterdrückt: Nicht konvertierbare Werte werden
        von uns bereits gezielt über `_collect_conversion_warnings` gemeldet,
        die generische pandas-Warnung wäre hier nur Rauschen.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Could not infer format')
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
    def _parse_numeric_column(column_values: pd.Series, decimal_override: Optional[NumericStyle] = None) -> pd.Series:
        """
        Konvertiert eine Spalte in float64 Format.

        decimal_override erzwingt deutsches (Komma) oder englisches (Punkt) Format
        für die gesamte Spalte (übersteuert die Heuristik, siehe Modul-Docstring).
        Ohne Override wird automatisch erkannt, ob die Spalte deutsche (Komma) oder
        englische (Punkt) Zahlen verwendet (Heuristik über alle Werte, analog zu
        detect_dayfirst).

        Behandelt deutsche Dezimalkommas: "1,5" → 1.5
        Behandelt deutsche Tausendertrenner: "1.234,56" → 1234.56
        Englische Punkt-Notation: "1234.56" → 1234.56
        Negative Zahlen: "-1,5" → -1.5
        Ungültige Werte werden zu NaN; parse_column_to_series meldet daraus
        resultierende Warnungen.
        """
        # Falls schon numeric: kein parsing nötig
        if pd.api.types.is_numeric_dtype(column_values):
            return column_values

        # String-Werte trimmen
        cleaned = column_values.astype(str).str.strip()

        # Erkenne, ob die Spalte deutsches oder englisches Format verwendet
        style = decimal_override if decimal_override is not None else ColumnParser._detect_numeric_style(cleaned)

        if style == NumericStyle.GERMAN_COMMA:
            # Deutsches Format: Komma = Dezimaltrenner, Punkte entfernen
            transformed = cleaned.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        else:
            # Englisches Format: Punkt = Dezimaltrenner, Kommas entfernen
            transformed = cleaned.str.replace(',', '', regex=False)

        return pd.to_numeric(transformed, errors='coerce')