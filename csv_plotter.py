"""
CSV-Plotter — Erstellt Diagramme und Tabellen-PDFs aus CSV-Messdaten.

Features:
- Scatterplot und Liniendiagramm mit korrekter X-Achsen-Skalierung
- Tabellen-PDFs mit geparsten Messwerten
- Unterstützung für mehrere CSV-Dateien zum Vergleich
- Datumsachse und Schwarz-Weiß-Modus für Drucke
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import argparse
import locale
import warnings
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
import math
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
from column_parser import ColumnType, NumericStyle
from csv_parser import parse_csv_file, ProcessedCSVFile

# Pfad zu SumatraPDF (Portable Version, sperrt PDFs nicht)
# Der Default-Pfad ist Windows-spezifisch, da dieses Tool nur auf Windows
# läuft. Für andere Installationsorte per Umgebungsvariable überschreiben.
# Falls SumatraPDF nicht gefunden wird, wird das PDF-Öffnen übersprungen.
SUMATRA_PDF_PATH = os.environ.get(
    "SUMATRA_PDF_PATH",
    r"C:\PortableApps\SumatraPDFPortable\SumatraPDFPortable.exe"
)
# SumatraPDF-Flag: neues Fenster statt vorhandenes wiederzuverwenden
# (wichtig, damit mehrfach erzeugte PDFs nicht dasselbe Fenster überschreiben)
_SUMATRA_NEW_WINDOW_FLAG = "/n"

# Anzeigeformat für Datumsachsen/-zellen (deutsches Format, konsistent zwischen
# Plot-Achse und Tabellen-PDF)
_DATE_DISPLAY_FORMAT = "%d.%m.%Y"

# Teile große Tabellen in mehrere Subtabellen auf, damit jede Subtabelle auf
# eine A4-Seite passt (30 Zeilen ist ein konservativer Erfahrungswert für die
# Standard-Schriftgröße von ReportLab bei mehrspaltigen Tabellen)
_MAX_ROWS_PER_SUBTABLE = 30

# Plot-Titel je nach Anzahl der Dateien
_PLOT_TITLE_SINGLE = "Messdaten"
_PLOT_TITLE_MULTI = "Vergleich Messungen"


def parse_args() -> argparse.Namespace:
    """Parst Kommandozeilen-Argumente"""
    parser = argparse.ArgumentParser(
        description='CSV-Plotter und Tabellenexport mit PDF-Ausgabe',
        add_help=False,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('csv_files', nargs='+', help='CSV-Dateien mit Messdaten')
    parser.add_argument('--y0', action='store_true',
                        help='Y=0-Linie und Y-Achse ab 0 anzeigen')
    parser.add_argument('--bw', action='store_true',
                        help='Schwarz-Weiß-Darstellung (mit verschiedenen Symbolen statt Farben)')
    parser.add_argument('--no-pdf-view', action='store_true',
                        help='PDFs nach Erstellung nicht automatisch öffnen')
    parser.add_argument('--table-decimal-dot', action='store_true',
                        help='Erzwingt Dezimalpunkt (.) in Tabellen-PDFs (statt lokaler Komma-Formatierung)')
    parser.add_argument('--date-x', action='store_true',
                        help='Erzwingt Datumsformat für X-Achse (erste Spalte)')
    parser.add_argument('--dayfirst', choices=['auto', 'true', 'false'], default='auto',
                        help='Übersteuert die Tag/Monat-zuerst-Erkennung für Datumsspalten\n'
                             '(true=Tag zuerst, false=Monat zuerst, auto=Heuristik pro Datei, Default: auto).\n'
                             'Nützlich, wenn die Heuristik bei uneindeutigen Datumsangaben danebenliegt.')
    parser.add_argument('--decimal', choices=['auto', 'comma', 'dot'], default='auto',
                        help='Übersteuert die Dezimaltrenner-Erkennung für Zahlenspalten\n'
                             '(comma=deutsches Komma, dot=englischer Punkt, auto=Heuristik pro Datei, Default: auto).\n'
                             'Nützlich, wenn die Heuristik bei uneindeutigen Zahlenformaten danebenliegt.')
    parser.add_argument('-?', '--help', action='help', help='Diese Hilfe anzeigen und beenden')
    return parser.parse_args()


def _setup_locale(args: argparse.Namespace) -> Tuple[bool, Tuple[Optional[str], Optional[str]]]:
    """
    Richtet locale-aware Dezimalformatierung ein.

    Returns:
        (use_locale_numeric, original_locale):
            use_locale_numeric: True wenn locale-Formatierung aktiv ist
            original_locale: ursprüngliches Locale zum Zurücksetzen
    """
    use_locale_numeric = False
    original_locale = locale.getlocale(locale.LC_NUMERIC)
    if not args.table_decimal_dot:
        try:
            locale.setlocale(locale.LC_NUMERIC, '')
            use_locale_numeric = True
        except Exception as e:
            print(f"Warnung: Konnte System-Locale nicht setzen: {e}", file=sys.stderr)
    else:
        # Bei --table-decimal-dot: explizit C-Locale setzen für Punkt als Dezimaltrenner
        try:
            locale.setlocale(locale.LC_NUMERIC, 'C')
        except Exception as e:
            print(f"Warnung: Konnte C-Locale nicht setzen: {e}", file=sys.stderr)
    return use_locale_numeric, original_locale


def _restore_locale(original_locale: Tuple[Optional[str], Optional[str]]) -> None:
    """Stellt das ursprüngliche Locale wieder her."""
    try:
        locale.setlocale(locale.LC_NUMERIC, original_locale)
    except Exception:
        pass


def _unescape_newlines(text: str) -> str:
    """
    Wandelt escaped Newlines (\\n) in echte Newlines um.
    
    Dies wird für Spaltennamen verwendet, die in CSV-Dateien escaped stehen können.
    """
    if text is None:
        return ""
    return str(text).replace("\\n", "\n")


def plot_data(processed_files: List[ProcessedCSVFile], args: argparse.Namespace) -> str:
    """
    Erstellt ein Scatterplot mit Linien aus den geparsten CSV-Daten.

    - Bei mehreren CSV-Dateien: alle in einem Diagramm zum Vergleich
    - X-Achse: korrekt skaliert nach Zahlenwert (nicht äquidistant wie Excel)
    - Datumsachse: automatisch erkannt und formatiert (oder mit --date-x erzwungen)
    - Schwarz-Weiß-Modus: mit verschiedenen Symbolen für Drucke

    Returns:
        Pfad zur gespeicherten PDF-Datei

    Raises:
        ValueError: wenn processed_files leer ist oder Dateien weniger als 2 Spalten haben
    """
    if not processed_files:
        raise ValueError("Keine Daten zum Plotten vorhanden.")

    for f in processed_files:
        if len(f.parsed_columns) < 2:
            raise ValueError(
                f"Datei '{f.filename}' hat nur {len(f.parsed_columns)} Spalte(n). "
                f"Für ein Diagramm werden mindestens 2 Spalten benötigt (X und Y)."
            )

    single_file = len(processed_files) == 1
    first_file = processed_files[0]

    # Vorbereitung: Figure und Axes
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    markers = ['o', 's', '^', 'x', 'D', 'v', '*', 'P', 'H']

    # Sammle alle X-Spalten-Typen vor dem Plotten (für konsistente Datumsprüfung)
    all_x_types = [f.parsed_columns[0].column_type for f in processed_files]

    # Flag ob mindestens eine X-Spalte ein Datum ist
    # --date-x erzwingt Datumsformat für X-Achse
    x_has_date = args.date_x

    # Lokaler Speicher für konvertierte X-Serien (um Side Effects auf processed_files zu vermeiden)
    converted_x_series: Dict[int, pd.Series] = {}

    # Wenn X-Achse potentiell Datum ist: prüfe und konvertiere X-Spalten vor dem Plotten
    # Dies muss VOR dem Plot-Loop passieren, damit konvertierte Daten verwendet werden können
    if x_has_date or any(t == ColumnType.DATE for t in all_x_types):
        has_non_date_file = False
        for idx, processed_data in enumerate(processed_files):
            x_series = processed_data.parsed_columns[0].series
            x_col_type = all_x_types[idx]

            if pd.api.types.is_datetime64_any_dtype(x_series):
                # Bereits datetime → merken für Datumsformat
                if not x_has_date:
                    x_has_date = True
                continue

            # Prüfe, ob die X-Spalte NUMERIC ist
            if pd.api.types.is_numeric_dtype(x_series) or x_col_type == ColumnType.NUMERIC:
                if args.date_x:
                    print(f"Warnung: --date-x angegeben, aber X-Spalte '{processed_data.filename}' ist numerisch. Numerische Darstellung wird verwendet.", file=sys.stderr)
                    has_non_date_file = True
                    break
                # Bei automatischer Erkennung: NUMERIC + DATE gemischt → Datumsformat deaktivieren
                if x_has_date:
                    print(f"Warnung: X-Spalte '{processed_data.filename}' ist numerisch, aber andere Dateien haben Datums-X. Datumsformat wird deaktiviert.", file=sys.stderr)
                    has_non_date_file = True
                    break
                # Keine Datums-Spalte gefunden → kein Datumsformat
                continue

            # Versuche die X-Daten als Datum zu konvertieren (für TEXT-Spalten)
            try:
                # Warnung unterdrücken: nicht-konvertierbare Werte werden unten
                # explizit behandelt (--date-x-Warnung bzw. stille Ignoranz)
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', message='Could not infer format')
                    converted = pd.to_datetime(x_series, errors='coerce')
                if converted.notna().any():
                    # Erfolgreich konvertiert - speichere lokal (kein Side Effect auf processed_files)
                    converted_x_series[idx] = converted
                    x_has_date = True
                else:
                    if args.date_x:
                        print(f"Warnung: --date-x angegeben, aber X-Spalte '{processed_data.filename}' kann nicht als Datum formatiert werden. Numerische Darstellung wird verwendet.", file=sys.stderr)
                        has_non_date_file = True
                        break
                    # Bei automatischer Erkennung: ignoriere nicht-konvertierbare Werte
            except Exception as e:
                if args.date_x:
                    print(f"Warnung: --date-x Fehler bei Datumskonvertierung: {e}. Numerische Darstellung wird verwendet.", file=sys.stderr)
                    has_non_date_file = True
                    break
                # Bei automatischer Erkennung: ignoriere Fehler

        if has_non_date_file:
            x_has_date = False
            converted_x_series = {}  # Verwerfe alle Konvertierungen

    # Plotte jede CSV-Datei
    for i, processed_data in enumerate(processed_files):
        label = processed_data.filename

        # Extrahiere X und Y aus den geparsten Spalten
        x_data = processed_data.parsed_columns[0].series
        y_data = processed_data.parsed_columns[1].series

        # Wähle Farbe/Symbol basierend auf Modus (Farbe oder Schwarz-Weiß)
        if args.bw:
            color = 'black'
            marker = markers[i % len(markers)]  # Verschiedene Symbole
        else:
            color = plot_colors[i % len(plot_colors)]  # Verschiedene Farben
            marker = 'o'

        # Verwende konvertierte X-Daten falls vorhanden (für --date-x mit TEXT-X-Spalten)
        if i in converted_x_series:
            x_data = converted_x_series[i]

        # Zeichne Scatter und Linie
        ax.scatter(x_data, y_data, color=color, marker=marker, s=15, label=label)
        ax.plot(x_data, y_data, color=color, linestyle='--')

    # Wenn X-Achse Datum ist: formatiere schön mit Datumsformat
    if x_has_date:
        # Bei automatischer Erkennung (ohne --date-x): wenn nicht alle Dateien
        # DATE-Typ haben, aber mindestens eine, warnen
        if not args.date_x and any(t == ColumnType.DATE for t in all_x_types) and not all(t == ColumnType.DATE for t in all_x_types):
            non_date_files = [processed_files[i].filename for i, t in enumerate(all_x_types) if t != ColumnType.DATE]
            print(f"Warnung: Nicht alle X-Spalten sind Datumsspalten ({', '.join(non_date_files)}). Datumsformat wird dennoch verwendet.", file=sys.stderr)

        ax.xaxis.set_major_formatter(mdates.DateFormatter(_DATE_DISPLAY_FORMAT))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()  # Dreht Labels automatisch für Lesbarkeit

    # Hole Achsenbeschriftungen von der ersten Datei
    # (annahme: alle CSV-Dateien haben gleiche Spalten)
    try:
        x_label = _unescape_newlines(first_file.parsed_columns[0].column_name)
    except Exception:
        x_label = ""
    try:
        y_label = _unescape_newlines(first_file.parsed_columns[1].column_name)
    except Exception:
        y_label = ""

    # Konfiguriere Achsen und Titel
    ax.set_xlabel(x_label, fontsize=8)
    ax.set_ylabel(y_label, fontsize=8)
    ax.set_title(_PLOT_TITLE_SINGLE if single_file else _PLOT_TITLE_MULTI)
    ax.grid(True)
    ax.legend()

    # X-Achsen-Labels drehen für bessere Lesbarkeit
    plt.xticks(rotation=90)
    plt.subplots_adjust(bottom=0.22)

    # Optional: Y-Achse von 0 starten (für Größenverhältnisse wichtig)
    if args.y0:
        ax.set_ylim(bottom=0)
        ax.axhline(0, color='gray', linestyle=':', linewidth=1)

    # Speichere als PDF (300 dpi für gute Qualität)
    pdf_plot = (os.path.splitext(first_file.filename)[0] + "_plot.pdf"
                if single_file
                else "Vergleich_Messungen.pdf")
    plt.savefig(pdf_plot, dpi=300)
    plt.close(fig)
    print(f"Plot gespeichert als {pdf_plot}")
    return pdf_plot


def format_cell(value: Any, col_type: ColumnType, use_locale_numeric: bool = False) -> str:
    """
    Formatiert einen einzelnen Zellenwert für die Tabellen-PDFs.

    Args:
        value: Der Zellenwert (kann NaN, NaT, Zahl, Datum, String sein)
        col_type: Der Typ der Spalte (DATE, NUMERIC, TEXT)
        use_locale_numeric: Ob locale-aware Formatierung für Zahlen verwendet werden soll

    Returns:
        Formatierter String für ReportLab
    """
    # Leere Werte (NaN, NaT)
    if pd.isna(value):
        return ""
    # Datumsformat: DD.MM.YYYY
    if col_type == ColumnType.DATE:
        try:
            return pd.Timestamp(value).strftime(_DATE_DISPLAY_FORMAT)
        except Exception:
            return str(value)
    # Zahlenformat: locale-aware wenn möglich (z.B. "1.234,56" in Deutschland)
    if col_type == ColumnType.NUMERIC and use_locale_numeric:
        # Booleans sind keine echten Zahlen, direkt als String ausgeben
        if isinstance(value, bool):
            return str(value)
        try:
            return format(value, 'n')  # 'n' = locale-aware
        except Exception:
            pass
    # TEXT-Werte: Whitespace trimmen (konsistent mit column_parser.py)
    if col_type == ColumnType.TEXT:
        return str(value).strip()
    return str(value)


def export_tables(processed_files: List[ProcessedCSVFile], args: argparse.Namespace) -> List[str]:
    """
    Exportiert die geparsten Messwerte als Tabellen-PDFs.

    Eine PDF pro CSV-Datei mit:
    - Überschrift mit Dateinamen
    - Tabelle mit allen Spalten und Zeilen
    - Automatische Aufteilung auf mehrere Subtabellen bei zu vielen Zeilen

    Raises:
        ValueError: wenn processed_files leer ist
    """
    if not processed_files:
        raise ValueError("Keine Daten zum Exportieren vorhanden.")

    styles = getSampleStyleSheet()

    # Stil für zentrierte Spaltenköpfe
    centered_header_style = ParagraphStyle(
        name='CenteredHeader',
        parent=styles['Normal'],
        alignment=1  # 0=links, 1=mitte, 2=rechts
    )

    # Richte locale-aware Dezimalformatierung einmalig ein (nicht pro Zelle!)
    use_locale_numeric, original_locale = _setup_locale(args)

    try:
        pdf_tables = []

        # Erstelle eine Tabellen-PDF für jede CSV-Datei
        for processed_file in processed_files:
            cols = processed_file.parsed_columns
            if not cols:
                continue

            # Spaltenköpfe
            columns_reportlab = [
                Paragraph(col.column_name.replace("\\n", "<br/>"), centered_header_style)
                for col in cols
            ]

            pdf_filename = f"{processed_file.filename}_tabelle.pdf"
            doc = SimpleDocTemplate(pdf_filename, pagesize=A4)
            elements = []

            # Titel
            table_title = processed_file.filename
            elements.append(Paragraph(f"Messwerte Tabelle: {table_title}", styles['Heading1']))

            # Teile große Tabellen in mehrere Subtabellen auf, damit jede Subtabelle
            # auf eine A4-Seite passt (30 Zeilen ist ein konservativer Erfahrungswert
            # für die Standard-Schriftgröße von ReportLab bei mehrspaltigen Tabellen)
            max_rows_per_col = _MAX_ROWS_PER_SUBTABLE
            col_lengths = [len(col.series) for col in cols]
            num_rows = min(col_lengths)
            
            # Warnung bei unterschiedlich langen Spalten
            if len(set(col_lengths)) > 1:
                max_len = max(col_lengths)
                min_len = min(col_lengths)
                print(f"Warnung: Spalten haben unterschiedliche Längen ({min_len}-{max_len}). Überschüssige Werte werden ignoriert.", file=sys.stderr)
            
            num_subtables = math.ceil(num_rows / max_rows_per_col)
            subtable_rows = []

            for i in range(num_subtables):
                start = i * max_rows_per_col
                end = min((i + 1) * max_rows_per_col, num_rows)

                # Baue Zeilendaten mit Formatierung
                subrows = []
                for row_idx in range(start, end):
                    row = [
                        format_cell(col.series.iloc[row_idx], col.column_type, use_locale_numeric)
                        for col in cols
                    ]
                    subrows.append(row)

                # Erstelle Subtabelle mit Styling
                table_data = [columns_reportlab] + subrows
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Header zentriert
                    ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                    ('ALIGN', (0, 1), (-1, -1), 'CENTER'),  # Daten zentriert
                    ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                    ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold')  # Header fett
                ]))
                subtable_rows.append([table])

            # Packe alle Subtabellen vertikal untereinander
            layout_table = Table(subtable_rows, hAlign='CENTER')
            layout_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            elements.append(layout_table)

            # Schreibe PDF
            doc.build(elements)
            print(f"Tabelle gespeichert als {pdf_filename}")
            pdf_tables.append(pdf_filename)

        return pdf_tables

    finally:
        # Locale immer zurücksetzen
        _restore_locale(original_locale)


def open_pdfs(pdf_files: List[str]) -> None:
    """Öffnet alle PDFs in SumatraPDF (sperrt Dateien nicht)"""
    if not pdf_files:
        return
    for pdf in pdf_files:
        try:
            subprocess.Popen([SUMATRA_PDF_PATH, _SUMATRA_NEW_WINDOW_FLAG, pdf])
        except FileNotFoundError:
            print(f"Warnung: SumatraPDF nicht gefunden unter {SUMATRA_PDF_PATH}", file=sys.stderr)
        except Exception as e:
            print(f"Warnung: Konnte PDF '{pdf}' nicht öffnen: {e}", file=sys.stderr)


def main() -> None:
    """
    Hauptfunktion: Parst CSV-Dateien und exportiert Plot + Tabellen

    Fehlerbehandlungs-Strategie über die Module hinweg:
    - csv_plotter.py (dieses Modul) ist die einzige Stelle, die den Prozess
      beendet (sys.exit) — es fängt hier alle Exceptions aus den Parser-Modulen
      ab und wandelt sie in eine Fehlermeldung + Exit-Code um.
    - csv_parser.py wirft ValueError bei nicht lesbaren Dateien (z.B. alle
      Encodings fehlgeschlagen); das ist ein Abbruchgrund für den ganzen Lauf.
    - column_parser.py wirft bewusst keine Exceptions für nicht konvertierbare
      Einzelwerte, sondern gibt NaN/NaT + eine Warnung zurück (siehe dortiger
      Modul-Docstring) — ein einzelner unparsbarer Wert soll nicht den
      gesamten Lauf abbrechen.
    """
    try:
        args = parse_args()

        # Prüfe, ob alle CSV-Dateien existieren
        for file in args.csv_files:
            if not os.path.isfile(file):
                print(f"Fehler: Datei nicht gefunden: '{file}'", file=sys.stderr)
                sys.exit(1)

        # CLI-Overrides für die Format-Heuristik auflösen (siehe column_parser.py Policy)
        dayfirst_override = {'auto': None, 'true': True, 'false': False}[args.dayfirst]
        decimal_override = {
            'auto': None,
            'comma': NumericStyle.GERMAN_COMMA,
            'dot': NumericStyle.ENGLISH_DOT,
        }[args.decimal]

        # Parse alle CSV-Dateien
        processed_files = [
            parse_csv_file(file, dayfirst_override=dayfirst_override, decimal_override=decimal_override)
            for file in args.csv_files
        ]

        # Erstelle Diagramm
        pdf_plot = plot_data(processed_files, args)

        # Erstelle Tabellen-PDFs
        pdf_tables = export_tables(processed_files, args)

        # Öffne PDFs (falls nicht deaktiviert)
        if not args.no_pdf_view:
            open_pdfs([pdf_plot] + pdf_tables)

    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Fehler: Datei nicht gefunden: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()