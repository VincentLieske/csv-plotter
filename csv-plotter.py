import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import argparse
import locale
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table as LayoutTable
import os
import math
import subprocess
from column_parser import ColumnType
from csv_parser import parse_csv_file

SUMATRA_PDF_PATH = r"C:\PortableApps\SumatraPDFPortable\SumatraPDFPortable.exe"

def parse_args():
    parser = argparse.ArgumentParser(
        description='CSV-Plotter und Tabellenexport mit PDF-Ausgabe',
        add_help=False,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('csv_files', nargs='+', help='CSV-Dateien mit Messdaten')
    # Option für y=0-Linie
    parser.add_argument('--y0', action='store_true', help='Y=0-Linie und Y-Achse ab 0 anzeigen')
    parser.add_argument('--bw', action='store_true', help='Schwarz-Weiß-Darstellung')
    parser.add_argument('--no-pdf-view', action='store_true', help='PDFs nach Erstellung nicht automatisch öffnen')
    parser.add_argument('--force-dot', action='store_true', help='Zwingt Dezimalpunkt als Separator (".") statt lokaler Einstellung')
    parser.add_argument('-?', '--help', action='help', help='Diese Hilfe anzeigen und beenden')
    return parser.parse_args()

def plot_data(processed_files, args):
    single_file = len(processed_files) == 1
    first_file = processed_files[0]

    # ---------------------------
    # Plot vorbereiten
    # ---------------------------
    fig, ax = plt.subplots(figsize=(10,6))
    plot_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']  # Farbplot
    markers = ['o', 's', '^', 'x', 'D', 'v', '*', 'P', 'H']   # Schwarz-Weiß Symbole

    # Ergebnisse für beide Achsen sammeln
    x_has_date = False
    for i, processed_data in enumerate(processed_files):
        label = processed_data.filename

        # Direkt aus parsed_columns auslesen (typsicher)
        x_data = processed_data.parsed_columns[0].series
        y_data = processed_data.parsed_columns[1].series

        # Prüfe, ob die X-Spalte (Spalte 0) dieser Datei eine Datumsspalte ist
        if not x_has_date and processed_data.parsed_columns[0].column_type == ColumnType.DATE:
            x_has_date = True

        # ---------------------------
        # Plot (compact handling for BW and color)
        # ---------------------------
        if args.bw:
            color = 'black'
            marker = markers[i % len(markers)]
        else:
            color = plot_colors[i % len(plot_colors)]
            marker = 'o'
        ax.scatter(x_data, y_data, color=color, marker=marker, s=15, label=f"{label}")
        ax.plot(x_data, y_data, color=color, linestyle='--')

    # Nach der Schleife: Wenn X eine Datumsspalte ist, formatiere die x-Achse entsprechend
    if x_has_date:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()

    # ---------------------------
    # Achsenbeschriftung aus erster Datei übernehmen
    # (angenommen alle Dateien haben die gleichen Spaltennamen)
    # ---------------------------
    try:
        x_label = first_file.parsed_columns[0].column_name.replace("\\n", "\n")
    except Exception:
        x_label = ""
    try:
        y_label = first_file.parsed_columns[1].column_name.replace("\\n", "\n")
    except Exception:
        y_label = ""

    # Achsen und Titel
    ax.set_xlabel(x_label, fontsize=8)
    ax.set_ylabel(y_label)
    ax.set_title("Messdaten" if single_file else "Vergleich Messungen")
    ax.grid(True)
    ax.legend()
    # X-Achse drehen

    # Mehr Platz für die x-Achsen-Beschriftung
    plt.xticks(rotation=90)
    plt.subplots_adjust(bottom=0.22)

    # Y-Achse: Immer mindestens ab 0
    if args.y0:
        ax.set_ylim(bottom=0)
        ax.axhline(0, color='gray', linestyle=':', linewidth=1)

    # ---------------------------
    # PDF Plot speichern
    # ---------------------------
    pdf_plot = os.path.splitext(first_file.filename)[0] + "_plot.pdf" if single_file else "Vergleich_Messungen.pdf"
    plt.savefig(pdf_plot, dpi=300)
    plt.close(fig)
    print(f"Plot gespeichert als {pdf_plot}")
    return pdf_plot

# ---------------------------
# Tabellen für jede CSV als PDF
# ---------------------------
def export_tables(processed_files, args):
    styles = getSampleStyleSheet()
    centered_header_style = ParagraphStyle(
        name='CenteredHeader',
        parent=styles['Normal'],
        alignment=1  # 0=links, 1=mitte, 2=rechts
    )
    pdf_tables = []

    def _format_cell(value, col_type: ColumnType) -> str:
        # Convert NaN/NaT to empty string
        if pd.isna(value):
            return ""
        if col_type == ColumnType.DATE:
            try:
                ts = pd.to_datetime(value)
                if pd.isna(ts):
                    return ""
                return ts.strftime('%d.%m.%Y')
            except Exception:
                return str(value)
        # Numeric formatting: use locale-aware formatting when possible.
        # `str()` does NOT respect locale (it always uses '.'), so use
        # `format(..., 'n')` (locale-aware) or fall back to a stable representation.
        if col_type == ColumnType.NUMERIC:
            if not args.force_dot:
                try:
                    locale.setlocale(locale.LC_NUMERIC, '')
                    return format(value, 'n')
                except Exception:
                    # Fallback if locale formatting fails
                    pass

        return str(value)

    for processed_file in processed_files:
        # processed_file is expected to be a ProcessedCSVFile (from csv_parser.parse_csv_file)
        cols = processed_file.parsed_columns
        if not cols:
            continue

        columns_reportlab = [
            Paragraph(col.column_name.replace("\\n", "<br/>"), centered_header_style)
            for col in processed_file.parsed_columns
        ]
        pdf_filename = f"{processed_file.filename}_tabelle.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4)
        elements = []
        table_title = processed_file.filename
        elements.append(Paragraph(f"Messwerte Tabelle: {table_title}", styles['Heading1']))
        max_rows_per_col = 30

        # number of rows is the minimum length of all parsed column series
        num_rows = min(len(col.series) for col in cols)
        num_subtables = math.ceil(num_rows / max_rows_per_col)
        subtables = []

        for i in range(num_subtables):
            start = i * max_rows_per_col
            end = min((i+1) * max_rows_per_col, num_rows)
            # build row-wise data from parsed columns using the formatted values
            subrows = []
            for row_idx in range(start, end):
                row = [
                    _format_cell(col.series.iloc[row_idx], col.column_type)
                    for col in cols
                ]
                subrows.append(row)

            table_data = [columns_reportlab] + subrows
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
                ('ALIGN', (0,1), (-1,-1), 'CENTER'),
                ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
                ('FONT', (0,0), (-1,0), 'Helvetica-Bold')
            ]))
            subtables.append(table)
        layout_data = [[t for t in subtables]]
        layout_table = LayoutTable(layout_data, hAlign='CENTER')
        layout_table.setStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP')
        ])
        elements.append(layout_table)
        doc.build(elements)
        print(f"Tabelle gespeichert als {pdf_filename}")
        pdf_tables.append(pdf_filename)
    return pdf_tables

# ---------------------------
# Alle PDFs automatisch öffnen in SumatraPDF Portable
# ---------------------------
def open_pdfs(pdf_files):
    for pdf in pdf_files:
        subprocess.Popen([SUMATRA_PDF_PATH, "/n", pdf])

def main():
    args = parse_args()

    # CSV-Dateien außerhalb von plot_data verarbeiten
    processed_files = []
    for file in args.csv_files:
        processed_files.append(parse_csv_file(file))

    pdf_plot = plot_data(processed_files, args)

    pdf_tables = export_tables(processed_files, args)
    if not args.no_pdf_view:
        open_pdfs([pdf_plot] + pdf_tables)

if __name__ == "__main__":
    main()