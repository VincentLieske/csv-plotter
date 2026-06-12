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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
import math
import subprocess
from column_parser import ColumnType
from csv_parser import parse_csv_file

# Pfad zu SumatraPDF (Portable Version, sperrt PDFs nicht)
SUMATRA_PDF_PATH = r"C:\PortableApps\SumatraPDFPortable\SumatraPDFPortable.exe"

def parse_args():
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
    parser.add_argument('--force-dot', action='store_true',
                        help='Erzwingt Dezimalpunkt (.) statt lokaler Einstellung')
    parser.add_argument('-?', '--help', action='help', help='Diese Hilfe anzeigen und beenden')
    return parser.parse_args()

def plot_data(processed_files, args):
    """
    Erstellt ein Scatterplot mit Linien aus den geparsten CSV-Daten.

    - Bei mehreren CSV-Dateien: alle in einem Diagramm zum Vergleich
    - X-Achse: korrekt skaliert nach Zahlenwert (nicht äquidistant wie Excel)
    - Datumsachse: automatisch erkannt und formatiert
    - Schwarz-Weiß-Modus: mit verschiedenen Symbolen für Drucke

    Returns:
        Pfad zur gespeicherten PDF-Datei
    """
    single_file = len(processed_files) == 1
    first_file = processed_files[0]

    # Vorbereitung: Figure und Axes
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    markers = ['o', 's', '^', 'x', 'D', 'v', '*', 'P', 'H']

    # Flag ob mindestens eine X-Spalte ein Datum ist
    x_has_date = False

    # Plotte jede CSV-Datei
    for i, processed_data in enumerate(processed_files):
        label = processed_data.filename

        # Extrahiere X und Y aus den geparsten Spalten
        x_data = processed_data.parsed_columns[0].series
        y_data = processed_data.parsed_columns[1].series

        # Merke: ist die X-Spalte eine Datumsspalte?
        if not x_has_date and processed_data.parsed_columns[0].column_type == ColumnType.DATE:
            x_has_date = True

        # Wähle Farbe/Symbol basierend auf Modus (Farbe oder Schwarz-Weiß)
        if args.bw:
            color = 'black'
            marker = markers[i % len(markers)]  # Verschiedene Symbole
        else:
            color = plot_colors[i % len(plot_colors)]  # Verschiedene Farben
            marker = 'o'

        # Zeichne Scatter und Linie
        ax.scatter(x_data, y_data, color=color, marker=marker, s=15, label=f"{label}")
        ax.plot(x_data, y_data, color=color, linestyle='--')

    # Wenn X-Achse Datum ist: formatiere schön mit Datumsformat
    if x_has_date:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()  # Dreht Labels automatisch für Lesbarkeit

    # Hole Achsenbeschriftungen von der ersten Datei
    # (annahme: alle CSV-Dateien haben gleiche Spalten)
    try:
        x_label = first_file.parsed_columns[0].column_name.replace("\\n", "\n")
    except Exception:
        x_label = ""
    try:
        y_label = first_file.parsed_columns[1].column_name.replace("\\n", "\n")
    except Exception:
        y_label = ""

    # Konfiguriere Achsen und Titel
    ax.set_xlabel(x_label, fontsize=8)
    ax.set_ylabel(y_label)
    ax.set_title("Messdaten" if single_file else "Vergleich Messungen")
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

def export_tables(processed_files, args):
    """
    Exportiert die geparsten Messwerte als Tabellen-PDFs.

    Eine PDF pro CSV-Datei mit:
    - Überschrift mit Dateinamen
    - Tabelle mit allen Spalten und Zeilen
    - Automatische Aufteilung auf mehrere Subtabellen bei zu vielen Zeilen
    """
    styles = getSampleStyleSheet()

    # Stil für zentrierte Spaltenköpfe
    centered_header_style = ParagraphStyle(
        name='CenteredHeader',
        parent=styles['Normal'],
        alignment=1  # 0=links, 1=mitte, 2=rechts
    )

    # Richte locale-aware Dezimalformatierung einmalig ein (nicht pro Zelle!)
    use_locale_numeric = False
    if not args.force_dot:
        try:
            locale.setlocale(locale.LC_NUMERIC, '')
            use_locale_numeric = True
        except Exception:
            pass

    pdf_tables = []

    def _format_cell(value, col_type: ColumnType) -> str:
        """Formatiert einen einzelnen Zellenwert für die Tabelle"""
        # Leere Werte (NaN, NaT)
        if pd.isna(value):
            return ""
        # Datumsformat: DD.MM.YYYY
        if col_type == ColumnType.DATE:
            try:
                return pd.Timestamp(value).strftime('%d.%m.%Y')
            except Exception:
                return str(value)
        # Zahlenformat: locale-aware wenn möglich (z.B. "1.234,56" in Deutschland)
        if col_type == ColumnType.NUMERIC and use_locale_numeric:
            try:
                return format(value, 'n')  # 'n' = locale-aware
            except Exception:
                pass
        return str(value)

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

        # Teile große Tabellen in mehrere Subtabellen (max 30 Zeilen pro Subtabelle)
        max_rows_per_col = 30
        num_rows = min(len(col.series) for col in cols)
        num_subtables = math.ceil(num_rows / max_rows_per_col)
        subtables = []

        for i in range(num_subtables):
            start = i * max_rows_per_col
            end = min((i + 1) * max_rows_per_col, num_rows)

            # Baue Zeilendaten mit Formatierung
            subrows = []
            for row_idx in range(start, end):
                row = [
                    _format_cell(col.series.iloc[row_idx], col.column_type)
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
            subtables.append(table)

        # Packe alle Subtabellen in eine Layout-Tabelle
        layout_data = [[t for t in subtables]]
        layout_table = Table(layout_data, hAlign='CENTER')
        layout_table.setStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ])
        elements.append(layout_table)

        # Schreibe PDF
        doc.build(elements)
        print(f"Tabelle gespeichert als {pdf_filename}")
        pdf_tables.append(pdf_filename)

    return pdf_tables

def open_pdfs(pdf_files):
    """Öffnet alle PDFs in SumatraPDF (sperrt Dateien nicht)"""
    for pdf in pdf_files:
        subprocess.Popen([SUMATRA_PDF_PATH, "/n", pdf])


def main():
    """Hauptfunktion: Parst CSV-Dateien und exportiert Plot + Tabellen"""
    args = parse_args()

    # Parse alle CSV-Dateien
    processed_files = [parse_csv_file(file) for file in args.csv_files]

    # Erstelle Diagramm
    pdf_plot = plot_data(processed_files, args)

    # Erstelle Tabellen-PDFs
    pdf_tables = export_tables(processed_files, args)

    # Öffne PDFs (falls nicht deaktiviert)
    if not args.no_pdf_view:
        open_pdfs([pdf_plot] + pdf_tables)


if __name__ == "__main__":
    main()