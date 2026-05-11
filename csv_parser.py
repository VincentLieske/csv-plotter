"""
CSV Parser - Verarbeitet CSV-Dateien und liefert strukturierte Informationen zurück
"""
import os

import pandas as pd
from dataclasses import dataclass
from typing import List
from column_parser import ColumnParser, ColumnResult


# `ColumnResult` (from `column_parser`) already contains `series`, `column_type` and `column_name`.
# Reuse it directly instead of declaring a duplicate `ParsedColumn` dataclass.

@dataclass
class ProcessedCSVFile:
    """Enthält alle Informationen zu einer verarbeiteten CSV-Datei"""
    filename: str
    parsed_columns: List[ColumnResult]


def parse_csv_file(file_path) -> ProcessedCSVFile:
    """
    Verarbeitet eine CSV-Datei und liefert strukturierte Informationen zurück.
    
    Parameters
    ----------
    file_path : str
        Pfad zur CSV-Datei
        
    Returns
    -------
    ProcessedCSVFile
        Objekt mit:
        - filename: Dateiname ohne Extension
        - parsed_columns: Liste der `ColumnResult`-Objekte (enthält `series`, `column_type`, `column_name`)
    """
    # CSV-Datei lesen
    data = pd.read_csv(file_path, sep=';', decimal=',')
    
    # Dateiname ohne Extension
    filename = os.path.basename(file_path).replace('.csv', '')
    
    # Spalten verarbeiten
    parsed_columns = []
    
    for col_idx in range(len(data.columns)):
        column_data = data.iloc[:, col_idx]
        column_name = data.columns[col_idx]
        
        # Spalte parsen
        result = ColumnParser.parse_column_to_series(column_data, column_name)
        
        # ColumnResult direkt weiterreichen (enthält `series`, `column_type`, `column_name`)
        parsed_columns.append(result)
    
    return ProcessedCSVFile(
        filename=filename,
        parsed_columns=parsed_columns
    )
