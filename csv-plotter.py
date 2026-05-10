import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import locale
import argparse
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table as LayoutTable
import os
import sys
import math
import subprocess

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
    # Option für Datums-x-Achse
    parser.add_argument('--date-x', action='store_true', help='X-Achse als Datum interpretieren (automatisch deutsches Format bei deutschem System)')
    parser.add_argument('--no-pdf-view', action='store_true', help='PDFs nach Erstellung nicht automatisch öffnen')
    parser.add_argument('-?', '--help', action='help', help='Diese Hilfe anzeigen und beenden')
    return parser.parse_args()

def detect_locale():
    try:
        locale.setlocale(locale.LC_TIME, '')
        current_locale = locale.getlocale(locale.LC_TIME)
    except Exception as e:
        print(f"[DEBUG] Fehler beim Setzen des Locale: {e}")
        current_locale = (None, None)
    is_german_locale = current_locale[0] is not None and current_locale[0].lower().startswith('de')
    print(f"[DEBUG] Erkanntes Locale: {current_locale}")
    print(f"[DEBUG] is_german_locale: {is_german_locale}")
    return is_german_locale

def plot_data(csv_files, args, is_german_locale):
    single_file = len(csv_files) == 1
    # ---------------------------
    # Achsenbeschriftung aus erster CSV
    # ---------------------------
    first_data = pd.read_csv(csv_files[0], sep=';', decimal=',')
    x_label = first_data.columns[0].replace("\\n", "\n")
    y_label = first_data.columns[1].replace("\\n", "\n")

    # ---------------------------
    # Plot vorbereiten
    # ---------------------------
    fig, ax = plt.subplots(figsize=(10,6))
    plot_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']  # Farbplot
    markers = ['o', 's', '^', 'x', 'D', 'v', '*', 'P', 'H']   # Schwarz-Weiß Symbole

    # ---------------------------
    # CSV-Dateien übergeben
    # ---------------------------
    for i, file in enumerate(csv_files):
        data = pd.read_csv(file, sep=';', decimal=',')
        x = data.iloc[:,0]
        y = data.iloc[:,1]
        label = os.path.basename(file).replace('.csv','')

        # Falls --date-x gesetzt ist, x als Datum interpretieren
        if args.date_x:
            print(f"[DEBUG] Parsen der x-Achse als Datum. dayfirst={is_german_locale}")
            if is_german_locale:
                x_parsed = pd.to_datetime(x, dayfirst=True, errors='coerce')
            else:
                x_parsed = pd.to_datetime(x, errors='coerce')
            num_nat = x_parsed.isna().sum()
            if num_nat > 0:
                print(f"[DEBUG] Warnung: {num_nat} von {len(x_parsed)} Datumswerten konnten nicht geparst werden!")
                print(f"[DEBUG] Ursprüngliche Werte: {list(x)}")
                print(f"[DEBUG] Geparste Werte: {list(x_parsed)}")
            x = x_parsed

        # ---------------------------
        # Schwarz-Weiß Flag aus cmdline
        # ---------------------------
        if args.bw:
            marker = markers[i % len(markers)]
            ax.scatter(x, y, color='black', marker=marker, s=15, label=f"{label}")
            ax.plot(x, y, color='black', linestyle='--')
        else:
            color = plot_colors[i % len(plot_colors)]
            ax.scatter(x, y, color=color, label=f"{label}", s=15)
            ax.plot(x, y, color=color, linestyle='--')

    # Falls --date-x gesetzt ist, x-Achse als Datum formatieren
    if args.date_x:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.%Y'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate()


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
    pdf_plot = os.path.splitext(csv_files[0])[0] + "_plot.pdf" if single_file else "Vergleich_Messungen.pdf"
    plt.savefig(pdf_plot, dpi=300)
    plt.close(fig)
    print(f"Plot gespeichert als {pdf_plot}")
    return pdf_plot

# ---------------------------
# Tabellen für jede CSV als PDF
# ---------------------------
def export_tables(csv_files):
    styles = getSampleStyleSheet()
    centered_header_style = ParagraphStyle(
        name='CenteredHeader',
        parent=styles['Normal'],
        alignment=1  # 0=links, 1=mitte, 2=rechts
    )
    pdf_tables = []
    for file in csv_files:
        data = pd.read_csv(file, sep=';', decimal=',')
        columns_reportlab = [
            Paragraph(col.replace("\\n", "<br/>"), centered_header_style)
            for col in data.columns
        ]
        pdf_filename = os.path.splitext(file)[0] + "_tabelle.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4)
        elements = []
        table_title = os.path.basename(file).replace('.csv', '')
        elements.append(Paragraph(f"Messwerte Tabelle: {table_title}", styles['Heading1']))
        max_rows_per_col = 30
        num_rows = len(data)
        num_subtables = math.ceil(num_rows / max_rows_per_col)
        subtables = []
        for i in range(num_subtables):
            start = i * max_rows_per_col
            end = min((i+1) * max_rows_per_col, num_rows)
            subdata = data.iloc[start:end, :]
            table_data = [columns_reportlab] + subdata.values.tolist()
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
    sumatra_path = r"C:\PortableApps\SumatraPDFPortable\SumatraPDFPortable.exe"  # Pfad ggf. anpassen
    for pdf in pdf_files:
        subprocess.Popen([sumatra_path, "/n", pdf])

def main():
    args = parse_args()
    is_german_locale = detect_locale()
    pdf_plot = plot_data(args.csv_files, args, is_german_locale)
    pdf_tables = export_tables(args.csv_files)
    if not args.no_pdf_view:
        open_pdfs([pdf_plot] + pdf_tables)

if __name__ == "__main__":
    main()