"""
Gemeinsame Test-Hilfsfunktionen und Fixtures für alle Tests.
"""
import os
import tempfile
import pandas as pd
from unittest.mock import Mock
from column_parser import ColumnType, ColumnResult
from csv_parser import ProcessedCSVFile


# ---------------------------------------------------------------------------
# CSV-Datei-Hilfsfunktionen
# ---------------------------------------------------------------------------

def create_temp_csv(content: str, encoding: str = 'utf-8') -> str:
    """Erstellt eine temporäre CSV-Datei und gibt den Pfad zurück.

    Die Datei muss nach dem Test vom Aufrufer gelöscht werden (os.unlink).
    """
    fd, path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'w', encoding=encoding) as f:
        f.write(content)
    return path


def create_temp_csv_binary(content: bytes) -> str:
    """Erstellt eine temporäre CSV-Datei mit binärem Inhalt (z.B. für Encoding-Tests).

    Die Datei muss nach dem Test vom Aufrufer gelöscht werden (os.unlink).
    """
    fd, path = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(fd, 'wb') as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Mock-Daten-Hilfsfunktionen
# ---------------------------------------------------------------------------

def make_mock_file(filename: str, x_type: ColumnType = ColumnType.NUMERIC,
                   y_type: ColumnType = ColumnType.NUMERIC,
                   x_values=None, y_values=None) -> ProcessedCSVFile:
    """Erstellt einen gemockten ProcessedCSVFile für plot_data-Tests.

    Erzeugt eine X- und Y-Spalte mit den angegebenen Typen und Werten.
    Falls keine Werte angegeben werden, werden Standardwerte (1.0, 2.0, 3.0
    bzw. 10.0, 20.0, 30.0) verwendet.
    """
    x_values = x_values if x_values is not None else [1.0, 2.0, 3.0]
    y_values = y_values if y_values is not None else [10.0, 20.0, 30.0]
    col_x = ColumnResult(series=pd.Series(x_values), column_type=x_type, column_name="X")
    col_y = ColumnResult(series=pd.Series(y_values), column_type=y_type, column_name="Y")
    return ProcessedCSVFile(filename=filename, parsed_columns=[col_x, col_y])


def make_default_mock_args(bw: bool = False, y0: bool = False,
                           date_x: bool = False,
                           table_decimal_dot: bool = False) -> Mock:
    """Erstellt einen gemockten args-Namespace mit Standardwerten."""
    return Mock(bw=bw, y0=y0, date_x=date_x,
                table_decimal_dot=table_decimal_dot)


# ---------------------------------------------------------------------------
# Testdaten-Konstanten
# ---------------------------------------------------------------------------

SIMPLE_NUMERIC_CSV = "X;Y\n1,5;10,2\n2,3;20,5\n3,7;30,8\n"
DATE_CSV = "Datum;Wert\n01.01.2024;100\n15.03.2024;200\n24.12.2024;300\n"
MIXED_TYPES_CSV = "Datum;Temperatur;Notiz\n01.01.2024;22,5;sonnig\n15.03.2024;18,3;bewölkt\n"
THOUSANDS_CSV = "X;Y\n1.234,56;7.890,12\n"
EMPTY_HEADER_CSV = "X;Y\n"
SINGLE_COLUMN_CSV = "Wert\n10\n20\n30\n"
GERMAN_NUMERIC_CSV = ("X;Y\n"
                      "1,5;10,2\n"
                      "2,3;20,5\n"
                      "3,7;30,8\n"
                      "4,1;40,1\n"
                      "5,9;50,9\n")


# ---------------------------------------------------------------------------
# Große Testdaten-Generatoren
# ---------------------------------------------------------------------------

def generate_large_csv_content(num_rows: int,
                               x_start: float = 1.0,
                               y_start: float = 10.0) -> str:
    """Generiert CSV-Inhalt mit 'num_rows' Datenzeilen.

    X-Werte sind simple aufsteigende Zahlen, Y-Werte sind X*2.
    """
    lines = ["X;Y"]
    for i in range(num_rows):
        x = x_start + i * 0.5
        y = y_start + i * 2.0
        lines.append(f"{x:.1f};{y:.1f}")
    return "\n".join(lines)


def generate_large_mixed_csv_content(num_rows: int) -> str:
    """Generiert CSV-Inhalt mit gemischten Datentypen für num_rows Zeilen."""
    lines = ["Datum;Temperatur;Notiz"]
    for i in range(num_rows):
        day = (i % 28) + 1
        month = ((i // 28) % 12) + 1
        year = 2024 + (i // 336)
        temp = 15.0 + (i % 30) * 0.5
        note = f"Messung_{i}" if i % 5 != 0 else "ungültig"
        lines.append(f"{day:02d}.{month:02d}.{year};{temp:.1f};{note}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV mit Anführungszeichen-Testdaten
# ---------------------------------------------------------------------------

QUOTED_NUMERIC_CSV = '"X";"Y"\n"1,5";"10,2"\n"2,3";"20,5"\n'
QUOTED_TEXT_CSV = '"Name";"Wert"\n"Müller";"10,5"\n"Schmidt";"20,3"\n'
QUOTED_MIXED_CSV = '"Datum";"Temperatur"\n"01.01.2024";"22,5"\n"15.03.2024";"18,3"\n'
QUOTED_COMMA_IN_TEXT = '"Name";"Beschreibung"\n"Test";"Hallo, Welt"\n"Beispiel";"Wert A, Wert B"\n'
QUOTED_MULTILINE = '"Name";"Wert"\n"Test";"Zeil\nbruch"\n'