"""
Tests für csv-plotter.py — Integrationstests für Plot, Tabellen-Export, PDF-Öffnen und main().
"""
import pytest
import pandas as pd
import numpy as np
import sys
import importlib
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from column_parser import ColumnType, ColumnResult
from csv_parser import ProcessedCSVFile

# csv-plotter.py enthält einen Bindestrich → kein normaler Modul-Import möglich
_csv_plotter = importlib.import_module('csv-plotter')
format_cell = _csv_plotter.format_cell
_setup_locale = _csv_plotter._setup_locale
plot_data = _csv_plotter.plot_data
export_tables = _csv_plotter.export_tables
open_pdfs = _csv_plotter.open_pdfs
main = _csv_plotter.main


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

    def test_text_value(self):
        """Text → str(value)"""
        result = format_cell("  Hallo Welt  ", ColumnType.TEXT)
        assert result == "  Hallo Welt  "

    def test_integer_numeric(self):
        """Integer → str(integer)"""
        result = format_cell(42, ColumnType.NUMERIC)
        assert result == "42"


# ---------------------------------------------------------------------------
# _setup_locale Tests
# ---------------------------------------------------------------------------

class TestSetupLocale:
    """Tests für _setup_locale"""

    def test_force_dot_uses_c_locale(self):
        """--force-dot → use_locale_numeric=False"""
        args = Mock()
        args.force_dot = True
        use_locale, original = _setup_locale(args)
        assert use_locale is False
        assert isinstance(original, tuple)

    def test_no_force_dot_tries_user_locale(self):
        """Ohne --force-dot → use_locale_numeric kann True sein"""
        args = Mock()
        args.force_dot = False
        use_locale, original = _setup_locale(args)
        assert isinstance(use_locale, bool)
        assert isinstance(original, tuple)


# ---------------------------------------------------------------------------
# plot_data Tests — Integration: prüft korrekte Aufrufe an matplotlib
# ---------------------------------------------------------------------------

class TestPlotData:
    """Tests für plot_data (Integration mit matplotlib)"""

    def _make_mock_file(self, filename: str, x_type: ColumnType = ColumnType.NUMERIC,
                        y_type: ColumnType = ColumnType.NUMERIC,
                        x_values=None, y_values=None):
        x_values = x_values if x_values is not None else [1.0, 2.0, 3.0]
        y_values = y_values if y_values is not None else [10.0, 20.0, 30.0]
        col_x = ColumnResult(series=pd.Series(x_values), column_type=x_type, column_name="X")
        col_y = ColumnResult(series=pd.Series(y_values), column_type=y_type, column_name="Y")
        return ProcessedCSVFile(filename=filename, parsed_columns=[col_x, col_y])

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

    def test_single_file_creates_correct_pdf_name(self):
        """Einzeldatei → PDF-Name = Dateiname_plot.pdf"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig') as mock_savefig:
                with patch('matplotlib.pyplot.close'):
                    mock_fig, mock_ax = MagicMock(), MagicMock()
                    mock_subplots.return_value = (mock_fig, mock_ax)

                    args = Mock(bw=False, y0=False)
                    result = plot_data([self._make_mock_file("messung1")], args)

                    assert result == "messung1_plot.pdf"
                    mock_savefig.assert_called_once()
                    # Prüfe dass der korrekte Dateiname übergeben wurde
                    assert mock_savefig.call_args[0][0] == "messung1_plot.pdf"

    def test_multiple_files_creates_comparison_pdf(self):
        """Mehrere Dateien → Vergleichs-PDF"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig') as mock_savefig:
                with patch('matplotlib.pyplot.close'):
                    mock_fig, mock_ax = MagicMock(), MagicMock()
                    mock_subplots.return_value = (mock_fig, mock_ax)

                    args = Mock(bw=False, y0=False)
                    result = plot_data([
                        self._make_mock_file("a"),
                        self._make_mock_file("b")
                    ], args)

                    assert result == "Vergleich_Messungen.pdf"
                    assert mock_ax.scatter.call_count == 2
                    assert mock_ax.plot.call_count == 2

    def test_bw_mode_uses_black(self):
        """--bw → scatter mit color='black'"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([self._make_mock_file("m")], Mock(bw=True, y0=False))
                assert mock_ax.scatter.call_args.kwargs['color'] == 'black'

    def test_y0_mode_adds_hline(self):
        """--y0 → set_ylim(bottom=0) + axhline"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([self._make_mock_file("m")], Mock(bw=False, y0=True))
                mock_ax.set_ylim.assert_called_once_with(bottom=0)
                mock_ax.axhline.assert_called_once()

    def test_date_x_axis_sets_date_formatter(self):
        """X-Achse ist Datum → set_major_formatter + set_major_locator werden aufgerufen"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
                plot_data([self._make_mock_file("m", x_type=ColumnType.DATE, x_values=dates)],
                          Mock(bw=False, y0=False))

                mock_ax.xaxis.set_major_formatter.assert_called_once()
                mock_ax.xaxis.set_major_locator.assert_called_once()
                mock_fig.autofmt_xdate.assert_called_once()

    def test_labels_are_set_from_column_names(self):
        """Achsenlabels werden aus Spaltennamen übernommen"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                col_x = ColumnResult(series=pd.Series([1.0, 2.0]), column_type=ColumnType.NUMERIC, column_name="Zeit (s)")
                col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Temperatur")
                pf = ProcessedCSVFile(filename="test", parsed_columns=[col_x, col_y])

                plot_data([pf], Mock(bw=False, y0=False))
                mock_ax.set_xlabel.assert_called_once_with("Zeit (s)", fontsize=8)
                mock_ax.set_ylabel.assert_called_once_with("Temperatur", fontsize=8)

    def test_legend_is_created(self):
        """Legend wird erstellt"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([self._make_mock_file("m")], Mock(bw=False, y0=False))
                mock_ax.legend.assert_called_once()

    def test_grid_is_enabled(self):
        """Grid wird aktiviert"""
        with patch('matplotlib.pyplot.subplots') as mock_subplots:
            with patch('matplotlib.pyplot.savefig'), patch('matplotlib.pyplot.close'):
                mock_fig, mock_ax = MagicMock(), MagicMock()
                mock_subplots.return_value = (mock_fig, mock_ax)

                plot_data([self._make_mock_file("m")], Mock(bw=False, y0=False))
                mock_ax.grid.assert_called_once_with(True)


# ---------------------------------------------------------------------------
# export_tables Tests — Integration: prüft korrekte Aufrufe an reportlab
# ---------------------------------------------------------------------------

class TestExportTables:
    """Tests für export_tables (Integration mit reportlab)"""

    def test_empty_processed_files_raises(self):
        """Leere Liste → ValueError"""
        with pytest.raises(ValueError, match="Keine Daten zum Exportieren"):
            export_tables([], Mock())

    def test_empty_columns_skipped(self):
        """Datei ohne Spalten → übersprungen (kein PDF)"""
        mock_file = Mock(filename="leer", parsed_columns=[])
        with patch.object(_csv_plotter, 'SimpleDocTemplate') as mock_doc:
            result = export_tables([mock_file], Mock(force_dot=False))
            assert result == []
            mock_doc.assert_not_called()

    def test_single_file_creates_pdf(self):
        """Einzeldatei → SimpleDocTemplate + build werden aufgerufen"""
        col_x = ColumnResult(series=pd.Series([1.0, 2.0]), column_type=ColumnType.NUMERIC, column_name="X")
        col_y = ColumnResult(series=pd.Series([10.0, 20.0]), column_type=ColumnType.NUMERIC, column_name="Y")
        pf = ProcessedCSVFile(filename="test", parsed_columns=[col_x, col_y])

        with patch.object(_csv_plotter, 'SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale'), patch('locale.getlocale', return_value=('german', 'cp1252')):
                result = export_tables([pf], Mock(force_dot=False))

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

        with patch.object(_csv_plotter, 'SimpleDocTemplate') as mock_doc_template:
            mock_doc_instance = MagicMock()
            mock_doc_template.return_value = mock_doc_instance
            with patch('locale.setlocale'), patch('locale.getlocale', return_value=('german', 'cp1252')):
                result = export_tables(files, Mock(force_dot=False))

        assert result == ["a_tabelle.pdf", "b_tabelle.pdf"]
        assert mock_doc_template.call_count == 2
        assert mock_doc_instance.build.call_count == 2


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
            assert "SumatraPDF nicht gefunden" in capsys.readouterr().out

    def test_other_error_shows_warning(self, capsys):
        """Anderer Fehler → Warnung"""
        with patch('subprocess.Popen', side_effect=Exception("fehler")):
            open_pdfs(["test.pdf"])
            captured = capsys.readouterr().out
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

        with patch.object(sys, 'argv', ['csv-plotter.py', str(csv_file)]):
            with patch.object(_csv_plotter, 'parse_csv_file', return_value=mock_file) as mock_parse:
                with patch.object(_csv_plotter, 'plot_data', return_value="plot.pdf"):
                    with patch.object(_csv_plotter, 'export_tables', return_value=["tab.pdf"]):
                        with patch.object(_csv_plotter, 'open_pdfs') as mock_open:
                            main()

        mock_parse.assert_called_once_with(str(csv_file))

    def test_main_file_not_found_exits(self, capsys):
        """Nicht-existierende Datei → Fehlermeldung + exit(1)"""
        with patch.object(sys, 'argv', ['csv-plotter.py', 'nicht_da.csv']):
            with pytest.raises(SystemExit) as exc:
                main()
        assert "Datei nicht gefunden" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_parse_error_handled(self, tmp_path, capsys):
        """Parse-Fehler → Fehlermeldung + exit(1)"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv-plotter.py', str(csv_file)]):
            with patch.object(_csv_plotter, 'parse_csv_file', side_effect=ValueError("Fehler")):
                with pytest.raises(SystemExit) as exc:
                    main()
        assert "Fehler" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_plot_error_handled(self, tmp_path, capsys):
        """Plot-Fehler → Fehlermeldung + exit(1)"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv-plotter.py', str(csv_file)]):
            with patch.object(_csv_plotter, 'parse_csv_file', return_value=MagicMock()):
                with patch.object(_csv_plotter, 'plot_data', side_effect=ValueError("Plot kaputt")):
                    with pytest.raises(SystemExit) as exc:
                        main()
        assert "Plot kaputt" in capsys.readouterr().err
        assert exc.value.code == 1

    def test_main_no_pdf_view_skips_open(self, tmp_path):
        """--no-pdf-view → open_pdfs wird nicht aufgerufen"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("X;Y\n1,5;10,2\n")

        with patch.object(sys, 'argv', ['csv-plotter.py', '--no-pdf-view', str(csv_file)]):
            with patch.object(_csv_plotter, 'parse_csv_file'):
                with patch.object(_csv_plotter, 'plot_data', return_value="plot.pdf"):
                    with patch.object(_csv_plotter, 'export_tables', return_value=[]):
                        with patch.object(_csv_plotter, 'open_pdfs') as mock_open:
                            main()
        mock_open.assert_not_called()