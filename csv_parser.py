"""
CSV-Parser — Liest CSV-Dateien und parst alle Spalten automatisch.

Umgang mit deutschen Formaten:
- Trennzeichen: Semikolon (;)
- Dezimalzeichen: Komma (,)
- Datumsformate: DD.MM.YYYY, YYYY-MM-DD, etc.

Hinweis: Alle Werte werden als Strings eingelesen (dtype=str), damit
ColumnParser die Typ-Erkennung und Zahlen-Parsing-Heuristik sauber
in einem Pfad durchführen kann — analog zur Datumsstil-Erkennung.
"""
import os
import sys
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from column_parser import ColumnParser, ColumnResult, NumericStyle


@dataclass
class ProcessedCSVFile:
    """Eine verarbeitete CSV-Datei mit allen geparsten Spalten"""
    filename: str              # Dateiname ohne Extension
    parsed_columns: List[ColumnResult]  # Die geparsten Spalten (enthält `series`, `column_type`, `column_name`)


def parse_csv_file(
    file_path: str,
    dayfirst_override: Optional[bool] = None,
    decimal_override: Optional[NumericStyle] = None,
) -> ProcessedCSVFile:
    """
    Liest eine CSV-Datei und parst alle Spalten.

    Parameters:
        file_path: Pfad zur CSV-Datei
        dayfirst_override: Übersteuert die dayfirst-Heuristik für alle Datumsspalten
            dieser Datei (None = Heuristik pro Datei verwenden, siehe ColumnParser)
        decimal_override: Übersteuert die Dezimaltrenner-Heuristik für alle
            Zahlenspalten dieser Datei (None = Heuristik pro Datei verwenden)

    Returns:
        ProcessedCSVFile mit Dateiname und geparsten Spalten (enthält `series`, `column_type`, `column_name`)

    Encoding: Versucht UTF-8, UTF-16 (mit BOM), Latin-1 und Windows-1252
    (häufig bei älteren Windows-Dateien mit Umlauten)

    Alle Werte werden als Strings eingelesen (dtype=str). Die Typ-Erkennung
    und das Parsing erfolgt komplett in ColumnParser, inkl. der Heuristik
    für deutsches (Komma) vs. englisches (Punkt) Zahlenformat pro Spalte.

    Konvertierungs-Policy (siehe column_parser.py Modul-Docstring für Details):
    Format wird pro Datei erkannt und als innerhalb der Datei konsistent
    angenommen. Werte, die sich nicht konvertieren lassen, werden als NaN/NaT
    behandelt und als Warnung auf stderr ausgegeben, statt sie stillschweigend
    zu verwerfen.
    """
    # Erkenne Encoding via BOM (Byte Order Mark)
    detected_encoding = None
    with open(file_path, 'rb') as f:
        raw = f.read(4)

    if raw[:2] == b'\xff\xfe':
        detected_encoding = 'utf-16'
    elif raw[:2] == b'\xfe\xff':
        detected_encoding = 'utf-16'
    elif raw[:3] == b'\xef\xbb\xbf':
        detected_encoding = 'utf-8-sig'
    # Kein BOM: Versuche mehrere Encodings
    encodings = ['utf-8', 'latin-1', 'cp1252']
    if detected_encoding:
        encodings = [detected_encoding] + encodings

    df = None
    for enc in encodings:
        try:
            # Lese CSV: ; als Trennzeichen, alle Werte als Strings
            # (kein decimal=',' mehr — ColumnParser entscheidet selbst
            #  per Heuristik ob deutsches oder englisches Format)
            df = pd.read_csv(file_path, sep=';', dtype=str, encoding=enc)
            print(f"[INFO] CSV mit Encoding '{enc}' gelesen: {file_path}")
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if df is None:
        raise ValueError(f"Konnte CSV '{file_path}' nicht mit unterstützten Encodings lesen")

    # Extrahiere Dateinamen ohne .csv Extension
    filename = os.path.splitext(os.path.basename(file_path))[0]

    # Parse alle Spalten automatisch
    parsed_columns = [
        ColumnParser.parse_column_to_series(
            df.iloc[:, i], df.columns[i],
            dayfirst_override=dayfirst_override,
            decimal_override=decimal_override,
        )
        for i in range(len(df.columns))
    ]

    # Nicht konvertierbare Werte stillschweigend zu NaN zu machen wäre Datenverlust
    # ohne Hinweis — daher werden sie hier als Warnung ausgegeben (siehe Policy oben).
    for column in parsed_columns:
        for warning in column.warnings:
            print(f"Warnung: Datei '{filename}', Spalte '{column.column_name}': {warning}", file=sys.stderr)

    return ProcessedCSVFile(filename=filename, parsed_columns=parsed_columns)