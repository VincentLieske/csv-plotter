"""
Tests für csv_plotter.py — Integrationstests für Plot, Tabellen-Export, PDF-Öffnen und main().
"""
import pytest
import pandas as pd
import numpy as np
import sys
import locale
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from column_parser import ColumnType, ColumnResult
from csv_parser import ProcessedCSVFile
from csv_plotter import format_cell, _setup_locale, plot_data, export_tables, open_pdfs, main, _unescape_newlines
from tests.helpers import make_mock_file, make_default_mock_args


# ---------------------------------------------------------------------------
# format_cell Tests
# ---------------------------------------------------------------------------

class TestFormatCell:
    """Tests für format_cell"""

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
        result = format_cell(1234.56, ColumnType.NUMERIC, use_locale_numeric=True)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_text_value_stripped(self):
        """Text → str(value) mit getrimmtem Whitespace"""
        result = format_cell("  Hallo Welt  ", ColumnType.TEXT)
        assert result == "Hallo Welt"

    def test_integer_numeric(self):
        """Integer → str(integer)"""
        result = format_cell(42, ColumnType.NUMERIC)
        assert result == "42"

    def test_zero_value_returns_zero(self):
        """0 → '0'"""
        result = format_cell(0, ColumnType.NUMERIC)
        assert result == "0"

    def test_boolean_text_returns_str(self):
        """True als TEXT → 'True'"""
        result = format_cell(True, ColumnType.TEXT)
        assert result == "True"

    def test_empty_string_text_returns_empty(self):
        """'' als TEXT → ''"""
        result = format_cell("", ColumnType.TEXT)
        assert result == ""

    def test_nan_value_as_date_returns_empty(self):
        """NaN als DATE → ''"""
        assert format_cell(np.nan, ColumnType.DATE) == ""

    def test_false_boolean_numeric_returns_str(self):
        """False → 'False'"""
        result = format_cell(False, ColumnType.NUMERIC)
        assert result == "False"

    def test_float_without_decimal_numeric(self):
        """1.0 → '1.0'"""
        result = format_cell(1.0, ColumnType.NUMERIC)
        assert result == "1.0"

    def test_inf_value_returns_inf(self):
        """float('inf') → 'inf'"""
        result = format_cell(float('inf'), ColumnType.NUMERIC)
        assert result == "inf"

    def test_neg_inf_value_returns_neg_inf(self):
        """float('-inf') → '-inf'"""
        result = format_cell(float('-inf'), ColumnType.NUMERIC)
        assert result == "-inf"

    def test_pd_na_value_returns_empty(self):
        """pd.NA → ''"""
        result = format_cell(pd.NA, ColumnType.NUMERIC)
        assert result == ""

    def test_large_number_with_many_decimals(self):
        """Sehr lange Dezimalzahl → korrekt formatiert"""
        result = format_cell(1234567890.123456789, ColumnType.NUMERIC)
        assert "1234567890" in result


# ---------------------------------------------------------------------------
# _unescape_newlines Tests
# ---------------------------------------------------------------------------

class TestUnescapeNewlines:
    """Tests für _unescape_newlines"""

    def test_escaped_newline_converted(self):
        """\\n → \\n"""
        result = _unescape_newlines("Zeit\\nin s")
        assert result == "Zeit\nin s"

    def test_no_escaped_newline_unchanged(self):
        """Text ohne \\n bleibt unverändert"""
        result = _unescape_newlines("Zeit in s")
        assert result == "Zeit in s"

    def test_none_returns_empty(self):
        """None → ''"""
        result = _unescape_newlines(None)
        assert result == ""

    def test_multiple_escaped_newlines(self):
        """Mehrere \\n werden alle konvertiert"""
        result = _unescape_newlines("Zeile1\\nZeile2\\nZeile3")
        assert result == "Zeile1\nZeile2\nZeile3"

    def test_real_newline_unchanged(self):
        """Echter Newline bleibt erhalten"""
        result = _unescape_newlines("Zeit\nin s")
        assert result == "Zeit\nin s"


# ---------------------------------------------------------------------------
# _setup_locale Tests
# ---------------------------------------------------------------------------

class TestSetupLocale:
    """Tests für _setup_locale"""

    def test_table_decimal_dot_uses_c_locale(self):
        """--table-decimal-dot → use_locale_numeric=False"""
        args = Mock()
        args.table_decimal_dot = True
        use_locale, original = _setup_locale(args)
        assert use_locale is False
        assert isinstance(original, tuple)

    def test_no_table_decimal_dot_tries_user_locale(self):
        """Ohne --table-decimal-dot → use_locale_numeric kann True sein"""
        args = Mock()
        args.table_decimal_dot = False
        use_locale, original = _setup_locale(args)
        assert isinstance(use_locale, bool)
        assert isinstance(original, tuple)


# ---------------------------------------------------------------------------
# plot_data Tests — Integration: prüft korrekte Aufrufe an matplotlib
# ---------------------------------------------------------------------------

class TestPlotDataValidation:
    """Tests für plot_data-Validierung (leere Eingaben, Fehlerfälle)"""

    def test_empty_processed_files_raises(self):
        """Leere Liste → ValueError"""
        with pytest.raises(ValueError, match="Keine Daten zum Plotten"):
            plot_data([], Mock())

    def test_single_column_file_raises(self):
        """Datei mit nur einer Spalte → ValueError"""
        mock_file = Mock()
        mock_file.filename = "test"
        mock_file.parsed_columns = [Mock()]
        with pytest.raises(ValueError, match="mindestens 2 Spalten"):
            plot_data([mock_file], Mock())

    def test_two_columns_zero_rows_does_not_raise(self):
        """2 Spalten aber 0 Datenzeilen → kein ValueError (nur leere Plot)"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                col_x = ColumnResult(series=pd.Series([], dtype=float), column_type=ColumnType.NUMERIC, column_name="X")
                col_y = ColumnResult(series=pd.Series([], dtype=float), column_type=ColumnType.NUMERIC, column_name="Y")
                pf = ProcessedCSVFile(filename="leer", parsed_columns=[col_x, col_y])
                result = plot_data([pf], make_default_mock_args())
                assert result == "leer_plot.pdf"


class TestPlotDataPdfNaming:
    """Tests für korrekte PDF-Dateinamen"""

    def test_single_file_creates_correct_pdf_name(self):
        """Einzeldatei → PDF-Name = Dateiname_plot.pdf"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig') as mock_savefig:
                with patch('matplotlib.pyplot.close'):
                    mock_fig, mock_ax = MagicMock(), MagicMock()
                    mock_subplots.return_value = (mock_fig, mock_ax)

                    result = plot_data([make_mock_file("messung1")], make_default_mock_args())

                    assert result == "messung1_plot.pdf"
                    mock_savefig.assert_called_once()
                    assert mock_savefig.call_args[0][0] == "messung1_plot.pdf"

    def test_multiple_files_creates_comparison_pdf(self):
        """Mehrere Dateien → Vergleichs-PDF"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig') as mock_savefig:
                with patch('matplotlib.pyplot.close'):
                    mock_fig, mock_ax = MagicMock(), MagicMock()
                    mock_subplots.return_value = (mock_fig, mock_ax)

                    args = make_default_mock_args()
                    result = plot_data([
                        make_mock_file("a"),
                        make_mock_file("b")
                    ], args)

                    assert result == "Vergleich_Messungen.pdf"
                    assert mock_ax.scatter.call_count == 2
                    assert mock_ax.plot.call_count == 2


class TestPlotDataStyling:
    """Tests für Styling-Einstellungen (bw, y0, grid, legend)"""

    def test_bw_mode_uses_black(self):
        """--bw → scatter mit color='black'"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m")], make_default_mock_args(bw=True))
                assert mock_ax.scatter.call_args.kwargs['color'] == 'black'

    def test_y0_mode_adds_hline(self):
        """--y0 → set_ylim(bottom=0) + axhline"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m")], make_default_mock_args(y0=True))
                mock_ax.set_ylim.assert_called_once_with(bottom=0)
                mock_ax.axhline.assert_called_once()

    def test_negative_y_values_with_y0(self):
        """--y0 mit negativen Y-Werten → set_ylim(bottom=0) wird aufgerufen"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m", y_values=[-5.0, -2.0, -10.0])], make_default_mock_args(y0=True))
                mock_ax.set_ylim.assert_called_once_with(bottom=0)
                mock_ax.axhline.assert_called_once()

    def test_legend_is_created(self):
        """Legend wird erstellt"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m")], make_default_mock_args())
                mock_ax.legend.assert_called_once()

    def test_grid_is_enabled(self):
        """Grid wird aktiviert"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m")], make_default_mock_args())
                mock_ax.grid.assert_called_once_with(True)

    def test_labels_are_set_from_column_names(self):
        """Achsenlabels werden aus Spaltennamen übernommen"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                col_x = ColumnResult(series=pd.Series([1.0, 2.0]), column_type=ColumnType.NUMERIC, column_name="Zeit (s)")
                col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Temperatur")
                pf = ProcessedCSVFile(filename="test", parsed_columns=[col_x, col_y])

                plot_data([pf], make_default_mock_args())
                mock_ax.set_xlabel.assert_called_once_with("Zeit (s)", fontsize=8)
                mock_ax.set_ylabel.assert_called_once_with("Temperatur", fontsize=8)

    def test_column_name_with_newline_escapes_replaced(self):
        """\\n im Spaltennamen wird in echten Zeilenumbruch umgewandelt"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                col_x = ColumnResult(series=pd.Series([1.0, 2.0]), column_type=ColumnType.NUMERIC, column_name="Zeit\\nin s")
                col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Temperatur")
                pf = ProcessedCSVFile(filename="test", parsed_columns=[col_x, col_y])

                plot_data([pf], make_default_mock_args())
                mock_ax.set_xlabel.assert_called_once_with("Zeit\nin s", fontsize=8)


class TestPlotDataDateHandling:
    """Tests für Datumsbehandlung in plot_data"""

    def test_date_x_axis_sets_date_formatter(self):
        """X-Achse ist Datum → set_major_formatter + set_major_locator werden aufgerufen"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
                plot_data([make_mock_file("m", x_type=ColumnType.DATE, x_values=dates)],
                          make_default_mock_args())

                mock_ax.xaxis.set_major_formatter.assert_called_once()
                mock_ax.xaxis.set_major_locator.assert_called_once()
                mock_fig.autofmt_xdate.assert_called_once()

    def test_date_x_flag_falls_back_to_numeric_for_pure_numbers(self, capsys):
        """--date-x mit rein numerischen Werten → Warnung + numerische Darstellung"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m", x_type=ColumnType.NUMERIC, x_values=[1.0, 2.0, 3.0])],
                          make_default_mock_args(date_x=True))

                mock_ax.xaxis.set_major_formatter.assert_not_called()
                mock_ax.xaxis.set_major_locator.assert_not_called()

        captured = capsys.readouterr()
        assert "Warnung" in captured.err or "nicht als Datum formatiert werden" in captured.err

    def test_date_x_flag_converts_convertible_strings(self):
        """--date-x konvertiert X-Spalte mit Datums-ähnlichen Strings"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([make_mock_file("m", x_type=ColumnType.TEXT, x_values=["2024-01-01", "2024-01-02"])],
                          make_default_mock_args(date_x=True))

                mock_ax.xaxis.set_major_formatter.assert_called_once()
                mock_ax.xaxis.set_major_locator.assert_called_once()

    def test_mixed_x_types_first_numeric_second_date_with_date_x(self, capsys):
        """--date-x mit Datei-1 NUMERIC-X und Datei-2 DATE-X → Warnung + keine Datumsformatierung"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                f1 = make_mock_file("a", x_type=ColumnType.NUMERIC, x_values=[1.0, 2.0, 3.0])
                f2 = make_mock_file("b", x_type=ColumnType.DATE,
                                   x_values=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
                plot_data([f1, f2], make_default_mock_args(date_x=True))

                mock_ax.xaxis.set_major_formatter.assert_not_called()
                captured = capsys.readouterr()
                assert "numerisch" in captured.err

    def test_mixed_x_types_first_date_second_numeric_auto(self, capsys):
        """Automatische Erkennung: Datei-1 DATE, Datei-2 NUMERIC → Warnung, aber Datumsformat gesetzt"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                f1 = make_mock_file("a", x_type=ColumnType.DATE,
                                   x_values=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
                f2 = make_mock_file("b", x_type=ColumnType.NUMERIC, x_values=[1.0, 2.0, 3.0])
                plot_data([f1, f2], make_default_mock_args())

                mock_ax.xaxis.set_major_formatter.assert_called_once()
                captured = capsys.readouterr()
                assert "Nicht alle X-Spalten sind Datumsspalten" in captured.err

    def test_date_x_flag_converts_text_x_in_all_files(self):
        """--date-x konvertiert TEXT-X-Spalten in allen Dateien zu datetime"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                f1 = make_mock_file("a", x_type=ColumnType.TEXT, x_values=["2024-01-01", "2024-01-02"])
                f2 = make_mock_file("b", x_type=ColumnType.TEXT, x_values=["2024-02-01", "2024-02-02"])
                plot_data([f1, f2], make_default_mock_args(date_x=True))

                assert pd.api.types.is_datetime64_any_dtype(f1.parsed_columns[0].series)
                assert pd.api.types.is_datetime64_any_dtype(f2.parsed_columns[0].series)
                mock_ax.xaxis.set_major_formatter.assert_called_once()

    def test_date_x_flag_one_file_not_convertible_disables_all(self, capsys):
        """--date-x: wenn eine Datei nicht konvertierbar ist → Datumsformat für alle deaktiviert"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                f1 = make_mock_file("a", x_type=ColumnType.TEXT, x_values=["2024-01-01", "2024-01-02"])
                f2 = make_mock_file("b", x_type=ColumnType.TEXT, x_values=["kein-datum", "auch-keins"])
                plot_data([f1, f2], make_default_mock_args(date_x=True))

                mock_ax.xaxis.set_major_formatter.assert_not_called()
                captured = capsys.readouterr()
                assert "kann nicht als Datum" in captured.err


# ---------------------------------------------------------------------------
# export_tables Tests — Integration: prüft korrekte Aufrufe an reportlab
# ---------------------------------------------------------------------------

class TestExportTables:
    """Tests für export_tables (Integration mit reportlab)"""

    def _make_default_pf(self, filename="test") -> ProcessedCSVFile:
        """Erstellt einen einfachen ProcessedCSVFile für Tabellen-Tests."""
        col_x = ColumnResult(series=pd.Series([1.0, 2.0]), column_type=ColumnType.NUMERIC, column_name="X")
        col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Y")
        return ProcessedCSVFile(filename=filename, parsed_columns=[col_x, col_y])

    def test_empty_processed_files_raises(self):
        """Leere Liste → ValueError"""
        with pytest.raises(ValueError, match="Keine Daten zum Exportieren"):
            export_tables([], Mock())

    def test_empty_columns_skipped(self):
        """Datei ohne Spalten → übersprungen (kein PDF)"""
        mock_file = Mock(filename="leer", parsed_columns=[])
        with patch('csv_plotter.SimpleDocTemplate') as mock_doc:
            result = export_tables([mock_file], make_default_mock_args(table_decimal_dot=False))
            assert result == []
            mock_doc.assert_not_called()

    def test_single_file_creates_pdf(self):
        """Einzeldatei → SimpleDocTemplate + build werden aufgerufen"""
        pf = self._make_default_pf()

        with patch('csv_plotter.SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale'), patch('locale.getlocale', return_value=('german', 'cp1252')):
                result = export_tables([pf], make_default_mock_args(table_decimal_dot=False))

        assert result == ["test_tabelle.pdf"]
        mock_doc_template.assert_called_once()
        mock_doc_instance.build.assert_called_once()

    def test_multiple_files_create_multiple_pdfs(self):
        """Mehrere Dateien → mehrere PDFs"""
        files = [
            ProcessedCSVFile(filename="a", parsed_columns=[
                ColumnResult(series=pd.Series([1.0]), column_type=ColumnType.NUMERIC, column_name="X"),
                ColumnResult(series=pd.Series([10.0]), column_type=ColumnType.NUMERIC, column_name="Y")
            ]),
            ProcessedCSVFile(filename="b", parsed_columns=[
                ColumnResult(series=pd.Series([2.0]), column_type=ColumnType.NUMERIC, column_name="X"),
                ColumnResult(series=pd.Series([20.0]), column_type=ColumnType.NUMERIC, column_name="Y")
            ])
        ]

        with patch('csv_plotter.SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale'), patch('locale.getlocale', return_value=('german', 'cp1252')):
                result = export_tables(files, make_default_mock_args(table_decimal_dot=False))

        assert result == ["a_tabelle.pdf", "b_tabelle.pdf"]
        assert mock_doc_template.call_count == 2
        assert mock_doc_instance.build.call_count == 2

    def test_uneven_column_lengths_shows_warning(self, capsys):
        """Unterschiedlich lange Spalten → Warnung ausgeben"""
        col_x = ColumnResult(series=pd.Series([1.0, 2.0, 3.0]), column_type=ColumnType.NUMERIC, column_name="X")
        col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Y")
        pf = ProcessedCSVFile(filename="test", parsed_columns=[col_x, col_y])

        with patch('csv_plotter.SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale'), patch('locale.getlocale', return_value=('german', 'cp1252')):
                result = export_tables([pf], make_default_mock_args(table_decimal_dot=False))

        assert "unterschiedliche Längen" in capsys.readouterr().err
        assert result == ["test_tabelle.pdf"]

    def test_table_decimal_dot_flag_uses_c_locale(self):
        """--table-decimal-dot → locale wird auf 'C' gesetzt (Punkt als Dezimaltrenner)"""
        pf = self._make_default_pf()

        with patch('csv_plotter.SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale') as mock_setlocale, patch('locale.getlocale', return_value=('german', 'cp1252')):
                export_tables([pf], make_default_mock_args(table_decimal_dot=True))

        mock_setlocale.assert_any_call(locale.LC_NUMERIC, 'C')

    def test_table_decimal_dot_false_uses_user_locale(self):
        """Ohne --table-decimal-dot → User-Locale ('') wird versucht"""
        pf = self._make_default_pf()

        with patch('csv_plotter.SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale') as mock_setlocale, patch('locale.getlocale', return_value=('german', 'cp1252')):
                export_tables([pf], make_default_mock_args(table_decimal_dot=False))

        mock_setlocale.assert_any_call(locale.LC_NUMERIC, '')


# ---------------------------------------------------------------------------
# open_pdfs Tests — Integration: prüft korrekte subprocess-Aufrufe
# ---------------------------------------------------------------------------

class TestOpenPdfs:
    """Tests für open_pdfs (Integration mit subprocess)"""

    def test_opens_pdf_with_sumatra(self):
        """PDF wird mit SumatraPDF geöffnet"""
        with patch('subprocess.Popen') as mock_popen:
            open_pdfs(["test.pdf"])
            mock_popen.assert_called_once()

    def test_opens_multiple_pdfs(self):
        """Mehrere PDFs → mehrere Popen-Aufrufe"""
        with patch('subprocess.Popen') as mock_popen:
            open_pdfs(["a.pdf", "b.pdf", "c.pdf"])
            assert mock_popen.call_count == 3

    def test_empty_list_does_nothing(self):
        """Leere Liste → kein Popen-Aufruf"""
        with patch('subprocess.Popen') as mock_popen:
            open_pdfs([])
            mock_popen.assert_not_called()

    def test_file_not_found_shows_warning(self, capsys):
        """SumatraPDF nicht gefunden → Warnung"""
        with patch('subprocess.Popen', side_effect=FileNotFoundError):
            open_pdfs(["test.pdf"])
            assert "SumatraPDF nicht gefunden" in capsys.readouterr().err

    def test_other_error_shows_warning(self, capsys):
        """Anderer Fehler → Warnung"""
        with patch('subprocess.Popen', side_effect=Exception("fehler")):
            open_pdfs(["test.pdf"])
            captured = capsys.readouterr().err
            assert "Konnte PDF" in captured
            assert "fehler" in captured


# ---------------------------------------------------------------------------
# main() Integration Tests
# ---------------------------------------------------------------------------

class TestMain:
    """Tests für main()"""

    def test_main_parse_plot_export_open(self, tmp_path):
        """main() durchläuft: parse → plot → export → open_pdfs"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        mock_file = ProcessedCSVFile(filename="test", parsed_columns=[
            ColumnResult(series=pd.Series([1.5]), column_type=ColumnType.NUMERIC, column_name="X")
        ])

        with patch.object(sys, 'argv', ['csv_plotter.py', str(csv_file)]):
            with patch('csv_plotter.parse_csv_file', return_value=mock_file) as mock_parse:
                with patch('csv_plotter.plot_data', return_value="plot.pdf"):
                    with patch('csv_plotter.export_tables', return_value=["tab.pdf"]):
                        with patch('csv_plotter.open_pdfs') as mock_open:
                            main()

        mock_parse.assert_called_once_with(str(csv_file))

    def test_main_file_not_found_exits(self, capsys):
        """Nicht-existierende Datei → Fehlermeldung + exit(1)"""
        with patch.object(sys, 'argv', ['csv_plotter.py', 'nicht_da.csv']):
            with pytest.raises(SystemExit) as exc:
                main()
        assert "Datei nicht gefunden" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_parse_error_handled(self, tmp_path, capsys):
        """Parse-Fehler → Fehlermeldung + exit(1)"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv_plotter.py', str(csv_file)]):
            with patch('csv_plotter.parse_csv_file', side_effect=ValueError("Fehler")):
                with pytest.raises(SystemExit) as exc:
                    main()
        assert "Fehler" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_plot_error_handled(self, tmp_path, capsys):
        """Plot-Fehler → Fehlermeldung + exit(1)"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv_plotter.py', str(csv_file)]):
            with patch('csv_plotter.parse_csv_file', return_value=MagicMock()):
                with patch('csv_plotter.plot_data', side_effect=ValueError("Plot kaputt")):
                    with pytest.raises(SystemExit) as exc:
                        main()
        assert "Plot kaputt" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_no_pdf_view_skips_open(self, tmp_path):
        """--no-pdf-view → open_pdfs wird nicht aufgerufen"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv_plotter.py', '--no-pdf-view', str(csv_file)]):
            with patch('csv_plotter.parse_csv_file'):
                with patch('csv_plotter.plot_data', return_value="plot.pdf"):
                    with patch('csv_plotter.export_tables', return_value=[]):
                        with patch('csv_plotter.open_pdfs') as mock_open:
                            main()
        mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# format_cell: Spezialfälle (extrahiert aus TestPlotData)
# ---------------------------------------------------------------------------

class TestFormatCellSpecial:
    """Spezialfälle für format_cell (ehemals Teil von TestPlotData)"""

    def test_format_cell_bool_with_date_type(self):
        """format_cell(True, DATE) → 'True' (fällt durch auf str(value))"""
        assert format_cell(True, ColumnType.DATE) == "True"
        assert format_cell(False, ColumnType.DATE) == "False"

    def test_format_cell_large_negative_with_locale(self):
        """format_cell mit großer negativer Zahl + locale → korrekter String"""
        result = format_cell(-1234567.89, ColumnType.NUMERIC, use_locale_numeric=True)
        assert isinstance(result, str)
        assert result.startswith("-")
        assert "1234567" in result or "1.23457" in result or "e+" in result

    def test_format_cell_bool_numeric_with_locale(self):
        """format_cell(False, NUMERIC, use_locale_numeric=True) → 'False' (nicht '0')"""
        assert format_cell(False, ColumnType.NUMERIC, use_locale_numeric=True) == "False"
        assert format_cell(True, ColumnType.NUMERIC, use_locale_numeric=True) == "True"