"""
CSV-Parser — Liest CSV-Dateien und parst alle Spalten automatisch.

Umgang mit deutschen Formaten:
- Trennzeichen: Semikolon (;)
- Dezimalzeichen: Komma (,)
- Datumsformate: DD.MM.YYYY, YYYY-MM-DD, etc.
"""
import os
import pandas as pd
from dataclasses import dataclass
from typing import List
from column_parser import ColumnParser, ColumnResult


@dataclass
class ProcessedCSVFile:
    """Eine verarbeitete CSV-Datei mit allen geparsten Spalten"""
    filename: str              # Dateiname ohne Extension
    parsed_columns: List[ColumnResult]  # Die geparsten Spalten (enthält `series`, `column_type`, `column_name`)


def parse_csv_file(file_path: str) -> ProcessedCSVFile:
    """
    Liest eine CSV-Datei und parst alle Spalten.

    Parameters:
        file_path: Pfad zur CSV-Datei

    Returns:
        ProcessedCSVFile mit Dateiname und geparsten Spalten (enthält `series`, `column_type`, `column_name`)
    """
    # Lese CSV mit deutschen Einstellungen: ; als Trennzeichen, , als Dezimal
    df = pd.read_csv(file_path, sep=';', decimal=',')

    # Extrahiere Dateinamen ohne .csv Extension
    filename = os.path.splitext(os.path.basename(file_path))[0]

    # Parse alle Spalten automatisch
    parsed_columns = [
        ColumnParser.parse_column_to_series(df.iloc[:, i], df.columns[i])
        for i in range(len(df.columns))
    ]

    return ProcessedCSVFile(filename=filename, parsed_columns=parsed_columns)
