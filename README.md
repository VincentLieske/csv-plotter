# CSV-Plotter und Tabellenexport

Dieses Python-Skript hilft dir, Messdaten aus CSV-Dateien zu visualisieren. Es erstellt coole Diagramme und exportiert die Daten in tabellarischer Form als PDF. Es ist besonders nützlich für den Vergleich mehrerer Datensätze und schnelle Berichte.

## Funktionen

- **Diagramme erstellen**: Scatterplots und Liniendiagramme aus deinen CSV-Daten.
- **Tabellen exportieren**: PDFs mit Tabellen für jede CSV-Datei.
- **Anpassbare Optionen**: Verschiedene Command-Line-Parameter für individuelle Einstellungen.
- **Automatische PDF-Anzeige**: PDFs öffnen sich automatisch (kann ausgeschaltet werden).

## Vorteile

- **Keine Dateisperrung durch SumatraPDF**: Anders als viele PDF-Viewer sperrt SumatraPDF die Dateien nicht. So kannst du das Skript erneut laufen lassen und aktualisierte PDFs erstellen, ohne die Fenster zu schließen. Das macht iterative Anpassungen und Ausdrucke viel einfacher.
- **Korrekte X-Achsen-Skalierung**: Anders als Excel, das Messpunkte oft äquidistant auf der X-Achse platziert, positioniert dieses Skript die Punkte entsprechend ihrem tatsächlichen Zahlenwert. Bei Datumsangaben klappt das super mit dem Parameter `--date-x`, wodurch Zeitreihen richtig dargestellt werden.

## Voraussetzungen

- Python 3.x
- Benötigte Bibliotheken:
  - pandas
  - matplotlib
  - reportlab

Installiere die Abhängigkeiten mit:
```
pip install -r requirements.txt
```

## Verwendung

### Grundlegende Syntax
```
python csv-plotter.py <CSV-Datei1> [<CSV-Datei2> ...] [Optionen]
```

### Beispiele
- Eine einzelne Datei plotten:
  ```
  python csv-plotter.py Messung4.csv
  ```
- Mehrere Dateien vergleichen:
  ```
  python csv-plotter.py Messung4.csv Messung4b.csv --y0 --bw
  ```

## Command-Line-Parameter

- `csv_files`: Eine oder mehrere CSV-Dateien mit Messdaten (erforderlich).
- `--y0`: Zeigt die Y=0-Linie und setzt die Y-Achse auf mindestens 0. Praktisch wenn die Daten die 0 sonst nicht enthalten.
- `--bw`: Aktiviert Schwarz-Weiß-Darstellung mit verschiedenen Markern. Damit sieht's auf einem Schwarz-Weiß-Drucker besser aus – viel klarer als Graustufen-Konvertierung.
- `--no-pdf-view`: Verhindert automatisches Öffnen der PDFs nach der Erstelung. Nützlich für Skripte oder Server ohne GUI.
- `-?` oder `--help`: Zeigt die Hilfe an und beendet das Programm.

## Workflow zur Datenerstellung

1. **Daten sammeln**: Erfasse deine Messdaten in einem Tabellenprogramm wie Excel.

2. **CSV-Format vorbereiten**:
   - Verwende Semikolon (`;`) als Spaltentrennzeichen.
   - Verwende Komma (`,`) als Dezimaltrennzeichen (deutsches Format).
   - Die erste Spalte sollte die X-Werte enthalten (z.B. Zeit oder Messpunkt).
   - Die zweite Spalte sollte die Y-Werte enthalten (z.B. Temperatur oder Messwert).
   - Die erste Zeile sollte die Spaltenüberschriften enthalten.

3. **CSV speichern**:
   - **Tipp**: Speichere die Datei als CSV (Trennzeichen-getrennt) in Excel.
   - Excel ab 2019: Wähle "CSV UTF-8 (Trennzeichen-getrennt)" für Sonderzeichen.
   - Ältere Excel: Verwende "CSV (Trennzeichen-getrennt)", aber beachte dass Umlaute möglicherweise nicht korrekt dargestellt werden. Öffne die Datei dann in einem Texteditor wie Notepad++ und speichere als UTF-8.
   - Achte darauf, dass keine extra Anführungszeichen oder Formatierungen drin sind.

4. **Skript ausführen**: Starte das Skript mit deinen CSV-Dateien, um Diagramme und Tabellen zu generieren.

5. **Ergebnisse checken**: PDFs öffnen sich automatisch (außer bei `--no-pdf-view`). Schau dir die Diagramme an.

## Ausgaben

- **Plot-PDF**: Ein Diagramm mit den Datenpunkten und Linien. Bei mehreren Dateien werden sie gemeinsam im Diagramm angezeigt.

- **Tabellen-PDFs**: Für jede CSV-Datei wird eine separate PDF-Tabelle generiert, die die Rohdaten anzeigt.

## Hinweise

- Das Skript versucht das Datumsformat automatisch zu erkennen und passt Datumsformate entsprechend an.
- Bei Problemen mit der Datumsinterpretation überprüfe das Format in deinen CSVs.
- Bei großen Datensätzen teilt das Skript Tabellen automatisch in mehrere Spalten auf.

## Lizenz

Dieses Projekt steht unter der MIT License. Siehe [LICENSE](LICENSE) für den vollständigen Text.

**Kurz erklärt (Deutsch):** Du kannst die Software frei nutzen, kopieren, modifizieren und verteilen – auch kommerziell. Die einzige Bedingung ist, dass du den Copyright-Vermerk und die Lizenz beifügst. Die Software kommt ohne Garantie.

## Beiträge

Mach mit und hilf, das Projekt zu verbessern! Ich freue mich über deine Ideen, Bug-Reports, Feature-Vorschläge und Pull Requests auf GitHub. 
