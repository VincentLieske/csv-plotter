"""
Performance-Tests für column_parser.py — große Dateien, Skalierbarkeit.
"""
import pytest
import pandas as pd
import time
from column_parser import ColumnParser, ColumnType
from tests.helpers import generate_large_csv_content, generate_large_mixed_csv_content


class TestParseNumericLargeData:
    """Performance-Tests für große numerische Spalten"""

    @pytest.mark.parametrize("num_rows", [100, 1000, 10000])
    def test_parse_numeric_column_scaling(self, num_rows):
        """Parsing von großen numerischen Spalten skaliert linear."""
        values = [f"{i * 0.5:.1f}" if i % 3 != 0 else f"{i * 0.5:.1f}" for i in range(num_rows)]
        s = pd.Series(values)
        start = time.perf_counter()
        result = ColumnParser._parse_numeric_column(s)
        elapsed = time.perf_counter() - start

        assert len(result) == num_rows
        assert pd.api.types.is_float_dtype(result)
        # Max 1 Sekunde für 10k Zeilen (sollte < 0.1s sein)
        assert elapsed < 5.0, f"10k Zeilen brauchten {elapsed:.2f}s"

    @pytest.mark.parametrize("num_rows", [100, 1000, 10000])
    def test_detect_column_type_scaling(self, num_rows):
        """Typerkennung skaliert linear (nur 100er Sample)."""
        values = [f"{i * 0.5:.1f}" if i % 2 == 0 else f"{i * 0.5:.1f}" for i in range(num_rows)]
        s = pd.Series(values)
        start = time.perf_counter()
        result = ColumnParser.detect_column_type(s)
        elapsed = time.perf_counter() - start

        assert result == ColumnType.NUMERIC
        assert elapsed < 2.0, f"detect_column_type für 10k brauchte {elapsed:.2f}s"

    def test_large_series_all_numeric_rapid(self):
        """10.000 Zahlen werden schnell als NUMERIC erkannt."""
        s = pd.Series([1.5] * 10000)
        start = time.perf_counter()
        result = ColumnParser.detect_column_type(s)
        elapsed = time.perf_counter() - start

        assert result == ColumnType.NUMERIC
        assert elapsed < 1.0, f"Sollte < 1s sein, war {elapsed:.2f}s"

    def test_large_series_all_text_rapid(self):
        """10.000 Textwerte werden schnell als TEXT erkannt."""
        s = pd.Series(["Text_" + str(i) for i in range(10000)])
        start = time.perf_counter()
        result = ColumnParser.detect_column_type(s)
        elapsed = time.perf_counter() - start

        assert result == ColumnType.TEXT
        assert elapsed < 2.0, f"Sollte < 2s sein, war {elapsed:.2f}s"

    def test_large_series_mixed_types_rapid(self):
        """10.000 gemischte Werte → Typerkennung dauert nicht zu lange."""
        values = ["01.01.2024"] * 6000 + ["1,5"] * 3000 + ["Text"] * 1000
        s = pd.Series(values)
        start = time.perf_counter()
        result = ColumnParser.detect_column_type(s)
        elapsed = time.perf_counter() - start

        # 60% Datum → DATE
        assert result == ColumnType.DATE
        assert elapsed < 2.0, f"Sollte < 2s sein, war {elapsed:.2f}s"


class TestParseDateLargeData:
    """Performance-Tests für große Datums-Spalten"""

    @pytest.mark.parametrize("num_rows", [100, 1000])
    def test_parse_date_column_scaling(self, num_rows):
        """Parsing von großen Datums-Spalten skaliert angemessen."""
        dates = [f"{(i % 28) + 1:02d}.{(i % 12) + 1:02d}.2024" for i in range(num_rows)]
        s = pd.Series(dates)
        start = time.perf_counter()
        result = ColumnParser._parse_date_column(s)
        elapsed = time.perf_counter() - start

        assert len(result) == num_rows
        assert pd.api.types.is_datetime64_any_dtype(result)
        assert elapsed < 5.0, f"{num_rows} Zeilen brauchten {elapsed:.2f}s"


class TestParseColumnToSeriesLargeData:
    """Performance-Tests für parse_column_to_series mit großen Daten"""

    def test_parse_large_numeric(self):
        """parse_column_to_series mit 10.000 Zahlen."""
        s = pd.Series([f"{i * 0.5:.1f}" for i in range(10000)])
        start = time.perf_counter()
        result = ColumnParser.parse_column_to_series(s, "Groß")
        elapsed = time.perf_counter() - start

        assert result.column_type == ColumnType.NUMERIC
        assert len(result.series) == 10000
        assert elapsed < 5.0, f"Brauchte {elapsed:.2f}s"

    def test_parse_large_dates(self):
        """parse_column_to_series mit 1000 Datumswerten."""
        dates = [f"{(i % 28) + 1:02d}.{(i % 12) + 1:02d}.2024" for i in range(1000)]
        s = pd.Series(dates)
        start = time.perf_counter()
        result = ColumnParser.parse_column_to_series(s, "Datum")
        elapsed = time.perf_counter() - start

        assert result.column_type == ColumnType.DATE
        assert len(result.series) == 1000
        assert elapsed < 5.0, f"Brauchte {elapsed:.2f}s"