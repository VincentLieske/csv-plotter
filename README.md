# CSV-Plotter und Tabellenexport

Dieses Python-Skript hilft dir, Messdaten aus CSV-Dateien zu visualisieren. Es erstellt coole Diagramme und exportiert die Daten in tabellarischer Form als PDF. Es ist besonders nützlich für den Vergleich mehrerer Datensätze und schnelle Berichte.

## Funktionen

- **Diagramme erstellen**: Scatterplots und Liniendiagramme aus deinen CSV-Daten.
- **Tabellen exportieren**: PDFs mit Tabellen für jede CSV-Datei.
- **Anpassbare Optionen**: Verschiedene Command-Line-Parameter für individuelle Einstellungen.
- **Automatische PDF-Anzeige**: PDFs öffnen sich automatisch (kann ausgeschaltet werden).

## Vorteile

- **Keine Dateisperrung durch SumatraPDF**: Anders als viele PDF-Viewer sperrt SumatraPDF die Dateien nicht. So kannst du das Skript erneut laufen lassen und aktualisierte PDFs erstellen, ohne die Fenster zu schließen. Das macht iterative Anpassungen und Ausdrucke viel einfacher.
- **Korrekte X-Achsen-Skalierung**: Anders als Excel, das Messpunkte oft äquidistant auf der X-Achse platziert, positioniert dieses Skript die Punkte entsprechend ihrem tatsächlichen Zahlenwert. Bei Datumsangaben wird das Format automatisch erkannt und Zeitreihen richtig dargestellt. Mit `--date-x` kann das Format auch explizit erzwungen werden.

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
python csv_plotter.py <CSV-Datei1> [<CSV-Datei2> ...] [Optionen]
```

### Beispiele
- Eine einzelne Datei plotten:
  ```
  python csv_plotter.py Messung4.csv
  ```
- Mehrere Dateien vergleichen:
  ```
  python csv_plotter.py Messung4.csv Messung4b.csv --y0 --bw
  ```
- Datumsformat für X-Achse erzwingen:
  ```
  python csv_plotter.py Messung4.csv --date-x
  ```

## Command-Line-Parameter

- `csv_files`: Eine oder mehrere CSV-Dateien mit Messdaten (erforderlich).
- `--y0`: Zeigt die Y=0-Linie und setzt die Y-Achse auf mindestens 0. Praktisch wenn die Daten die 0 sonst nicht enthalten.
- `--bw`: Aktiviert Schwarz-Weiß-Darstellung mit verschiedenen Markern. Damit sieht's auf einem Schwarz-Weiß-Drucker besser aus – viel klarer als Graustufen-Konvertierung.
- `--no-pdf-view`: Verhindert automatisches Öffnen der PDFs nach der Erstelung. Nützlich für Skripte oder Server ohne GUI.
- `--date-x`: Erzwingt Datumsformat für die X-Achse (erste Spalte). Nützlich wenn die automatische Erkennung versagt oder wenn die X-Spalte wie ein Datum aussieht (z.B. "01.01.2024") aber fälschlicherweise als Zahl erkannt wurde.
- `--dayfirst {auto,true,false}`: Übersteuert die Tag/Monat-zuerst-Erkennung für Datumsspalten (Default: `auto`). Siehe [Konvertierungs-Policy](#konvertierungs-policy-für-datum-und-zahlenspalten).
- `--decimal {auto,comma,dot}`: Übersteuert die Dezimaltrenner-Erkennung für Zahlenspalten (Default: `auto`). Siehe [Konvertierungs-Policy](#konvertierungs-policy-für-datum-und-zahlenspalten).
- `-?` oder `--help`: Zeigt die Hilfe an und beendet das Programm.

## Konvertierungs-Policy für Datum- und Zahlenspalten

Datum- und Zahlenspalten werden nach demselben Prinzip geparst:

- Das Format (Tag- vs. Monat-zuerst bei Daten, Komma- vs. Punkt-Dezimaltrenner bei Zahlen) wird pro Datei per Heuristik aus einer Stichprobe der Spalte erkannt. Es wird angenommen, dass das Format **innerhalb einer Datei konsistent** ist. Über mehrere Dateien hinweg wird das Format unabhängig neu erkannt und kann abweichen.
- Werte, die sich mit dem erkannten Format trotzdem nicht konvertieren lassen, werden **nicht stillschweigend verworfen**: Sie werden als `NaN`/`NaT` behandelt (ignoriert) und als Warnung auf der Konsole ausgegeben (Dateiname, Spalte, Anzahl, Beispielwerte).
- Tauchen viele solche Warnungen auf, ist das das Signal, entweder die Quelldaten zu bereinigen oder die Heuristik gezielt zu übersteuern:
  - `--dayfirst true|false` erzwingt Tag- bzw. Monat-zuerst für alle Datumsspalten.
  - `--decimal comma|dot` erzwingt deutsches Komma bzw. englischen Punkt für alle Zahlenspalten.

  Beide Parameter gelten für den gesamten Lauf (alle übergebenen Dateien).

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
- Bei Problemen mit der Datumsinterpretation überprüfe das Format in deinen CSVs, verwende `--date-x` oder übersteuere die Erkennung mit `--dayfirst`/`--decimal` (siehe [Konvertierungs-Policy](#konvertierungs-policy-für-datum-und-zahlenspalten)).
- **Bekannte Einschränkung:** Bei stark gemischten Datumsformaten innerhalb einer Spalte (z.B. ISO `2024-03-15` neben deutschem `DD.MM.YYYY`, wenn ISO überwiegt) kann die automatische Erkennung danebenliegen. Betroffene Werte werden dann nicht stillschweigend verworfen, sondern als Warnung gemeldet und als `NaT` behandelt — in dem Fall hilft `--dayfirst` zur Übersteuerung. In der Praxis kommen gemischte Formate extrem selten vor.
- Bei großen Datensätzen teilt das Skript Tabellen automatisch in mehrere Spalten auf.
- **Hinweis:** Unterschiedlich lange Spalten werden mit einer Warnung versehen. Die kürzere Länge wird verwendet, überschüssige Werte werden ignoriert.

## Lizenz

Dieses Projekt steht unter der MIT License. Siehe [LICENSE](LICENSE) für den vollständigen Text.

**Kurz erklärt (Deutsch):** Du kannst die Software frei nutzen, kopieren, modifizieren und verteilen – auch kommerziell. Die einzige Bedingung ist, dass du den Copyright-Vermerk und die Lizenz beifügst. Die Software kommt ohne Garantie.

## Tests ausführen

Das Projekt verwendet `pytest` für automatisierte Tests. Alle Tests findest du im `tests/`-Verzeichnis.

Tests manuell ausführen:
```
python -m pytest tests/ -v
```

### Pre-Commit Hook (empfohlen)

Ein Pre-Commit Hook stellt sicher, dass alle Tests vor jedem Commit automatisch durchlaufen. Der Hook ist im Repository unter `githooks/pre-commit` versioniert.

Installation (einmalig):
```
git config core.hooksPath githooks/
```

Danach wird bei jedem `git commit` automatisch `pytest` ausgeführt. Bei fehlgeschlagenen Tests wird der Commit abgebrochen.

Zum Überspringen (z.B. für WIP-Commits):
```
git commit --no-verify
```

## Beiträge

Mach mit und hilf, das Projekt zu verbessern! Ich freue mich über deine Ideen, Bug-Reports, Feature-Vorschläge und Pull Requests auf GitHub.