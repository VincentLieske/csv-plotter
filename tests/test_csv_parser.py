"""
Tests für den CSV-Parser — Datei-Einlesen und Spalten-Parsing.
"""
import os
from csv_parser import parse_csv_file, ProcessedCSVFile
from column_parser import ColumnType
from tests.helpers import create_temp_csv, create_temp_csv_binary


class TestParseCsvFile:
    """Tests für parse_csv_file"""

    def test_simple_numeric_csv(self):
        """Einfache CSV mit zwei numerischen Spalten"""
        content = "X;Y\n1,5;10,2\n2,3;20,5\n3,7;30,8\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert isinstance(result, ProcessedCSVFile)
            assert len(result.parsed_columns) == 2
            assert result.parsed_columns[0].column_type == ColumnType.NUMERIC
            assert result.parsed_columns[1].column_type == ColumnType.NUMERIC
            assert result.parsed_columns[0].series.iloc[0] == 1.5
            assert result.parsed_columns[1].series.iloc[2] == 30.8
        finally:
            os.unlink(path)

    def test_date_and_numeric_csv(self):
        """CSV mit Datums-Spalte und Zahlen-Spalte"""
        content = "Datum;Wert\n01.01.2024;100\n15.03.2024;200\n24.12.2024;300\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 2
            assert result.parsed_columns[0].column_type == ColumnType.DATE
            assert result.parsed_columns[1].column_type == ColumnType.NUMERIC
            assert result.parsed_columns[0].series.iloc[1].month == 3
            assert result.parsed_columns[1].series.iloc[2] == 300.0
        finally:
            os.unlink(path)

    def test_filename_without_extension(self):
        """Dateiname ohne .csv Extension"""
        content = "X;Y\n1;2\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            basename = os.path.splitext(os.path.basename(path))[0]
            assert result.filename == basename
        finally:
            os.unlink(path)

    def test_three_columns_mixed_types(self):
        """CSV mit drei Spalten: Datum, Zahl, Text"""
        content = "Datum;Temperatur;Notiz\n01.01.2024;22,5;sonnig\n15.03.2024;18,3;bewölkt\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 3
            assert result.parsed_columns[0].column_type == ColumnType.DATE
            assert result.parsed_columns[1].column_type == ColumnType.NUMERIC
            assert result.parsed_columns[2].column_type == ColumnType.TEXT
        finally:
            os.unlink(path)

    def test_thousands_separator_in_csv(self):
        """CSV mit Tausenderpunkt-Zahlen"""
        content = "X;Y\n1.234,56;7.890,12\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert result.parsed_columns[0].column_type == ColumnType.NUMERIC
            assert result.parsed_columns[0].series.iloc[0] == 1234.56
            assert result.parsed_columns[1].series.iloc[0] == 7890.12
        finally:
            os.unlink(path)

    def test_latin1_encoding(self):
        """CSV mit Latin-1 Encoding (z.B. Umlaute von älteren Excel-Exporten)"""
        content = "Name;Wert\nMüller;10,5\nSchmidt;20,3\n"
        path = create_temp_csv(content, encoding='latin-1')
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 2
            assert result.parsed_columns[0].column_type == ColumnType.TEXT
            assert result.parsed_columns[1].column_type == ColumnType.NUMERIC
        finally:
            os.unlink(path)

    def test_cp1252_encoding(self):
        """CSV mit Windows-1252 Encoding"""
        content = "Name;Wert\nStraße;10,5\n"
        path = create_temp_csv(content, encoding='cp1252')
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 2
        finally:
            os.unlink(path)

    def test_utf16_bom_encoding(self):
        """CSV mit UTF-16 LE BOM wird korrekt erkannt und gelesen"""
        content_utf16 = "X;Y\n1,5;10,2\n".encode('utf-16-le')
        bom = b'\xff\xfe'
        path = create_temp_csv_binary(bom + content_utf16)
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 2
            assert result.parsed_columns[0].series.iloc[0] == 1.5
        finally:
            os.unlink(path)

    def test_empty_csv_has_no_rows(self):
        """Nur Header, keine Datenzeilen → leere Series"""
        content = "X;Y\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 2
            assert len(result.parsed_columns[0].series) == 0
            assert len(result.parsed_columns[1].series) == 0
        finally:
            os.unlink(path)

    def test_single_column_csv(self):
        """CSV mit nur einer Spalte → nur ein ColumnResult"""
        content = "Wert\n10\n20\n30\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert len(result.parsed_columns) == 1
        finally:
            os.unlink(path)

    def test_column_names_are_preserved(self):
        """Spaltennamen aus dem Header werden übernommen"""
        content = "Temperatur (°C);Luftfeuchtigkeit (%)\n22,5;65\n"
        path = create_temp_csv(content)
        try:
            result = parse_csv_file(path)
            assert result.parsed_columns[0].column_name == "Temperatur (°C)"
            assert result.parsed_columns[1].column_name == "Luftfeuchtigkeit (%)"
        finally:
            os.unlink(path)