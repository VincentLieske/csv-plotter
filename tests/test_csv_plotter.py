"""
Tests für csv-plotter.py — Formatzellen-Funktion, Locale-Setup und Plot-Validierung.
"""
import pytest
import pandas as pd
import numpy as np
import sys
import importlib
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from column_parser import ColumnType
from csv_parser import ProcessedCSVFile

# csv-plotter.py enthält einen Bindestrich → kein normaler Modul-Import möglich
_csv_plotter = importlib.import_module('csv-plotter')
format_cell = _csv_plotter.format_cell
_setup_locale = _csv_plotter._setup_locale


class TestFormatCell:
    """Tests für format_cell (ehemals Closure _format_cell, jetzt testbar)"""

    def test_nan_value_returns_empty_string(self):
        """NaN → ''"""
        assert format_cell(np.nan, ColumnType.NUMERIC) == ""

    def test_nat_value_returns_empty_string(self):
        """NaT → ''"""
        assert format_cell(pd.NaT, ColumnType.DATE) == ""

    def test_none_value_returns_empty_string(self):
        """None → ''"""
        assert format_cell(None, ColumnType.TEXT) == ""

    def test_date_format_dd_mm_yyyy(self):
        """Timestamp → DD.MM.YYYY"""
        result = format_cell(pd.Timestamp("2024-01-05"), ColumnType.DATE)
        assert result == "05.01.2024"

    def test_date_from_datetime(self):
        """datetime-Objekt → DD.MM.YYYY"""
        result = format_cell(datetime(2024, 12, 24), ColumnType.DATE)
        assert result == "24.12.2024"

    def test_invalid_date_returns_str(self):
        """Ungültiges Datum → str(value)"""
        result = format_cell("kein-datum", ColumnType.DATE)
        assert result == "kein-datum"

    def test_numeric_without_locale_returns_str(self):
        """Zahl ohne locale → str(value)"""
        result = format_cell(1234.56, ColumnType.NUMERIC)
        assert result == "1234.56"

    def test_numeric_with_locale_formatting(self):
        """Zahl mit locale → format(value, 'n') (abhängig vom System-Locale)"""
        # Mit use_locale_numeric=True sollte format(value, 'n') aufgerufen werden.
        # Da das Test-Locale systemabhängig ist, prüfen wir nur, dass ein String
        # zurückkommt und keine Exception fliegt.
        result = format_cell(1234.56, ColumnType.NUMERIC, use_locale_numeric=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_text_value(self):
        """Text → str(value)"""
        result = format_cell("  Hallo Welt  ", ColumnType.TEXT)
        # TEXT-Spalten-Werte kommen bereits getrimmt aus dem Parser
        assert result == "  Hallo Welt  "

    def test_integer_numeric(self):
        """Integer → str(integer)"""
        result = format_cell(42, ColumnType.NUMERIC)
        assert result == "42"


class TestSetupLocale:
    """Tests für _setup_locale"""

    def test_force_dot_uses_c_locale(self):
        """--force-dot: Force C-Locale → use_locale_numeric=False"""
        args = Mock()
        args.force_dot = True
        use_locale, original = _setup_locale(args)
        assert use_locale is False
        # original_locale sollte ein Tupel sein
        assert isinstance(original, tuple)

    def test_no_force_dot_tries_user_locale(self):
        """Ohne --force-dot: Versuche User-Locale → use_locale_numeric kann True sein"""
        args = Mock()
        args.force_dot = False
        use_locale, original = _setup_locale(args)
        # Sollte bei den meisten Systemen True ergeben
        # Auf CI-Systemen ohne deutsches Locale könnte es False sein
        assert isinstance(use_locale, bool)
        assert isinstance(original, tuple)