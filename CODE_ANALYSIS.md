# Code Analysis Report — csv-plotter

**Datum:** 2026-07-10  
**Analysierte Dateien:** 4 Hauptmodule + 6 Testdateien  
**Test-Ergebnis:** 266 Tests bestanden, 2 Warnungen

---

## Zusammenfassung

Der Code ist insgesamt **gut strukturiert und getestet**. Alle 266 Tests laufen erfolgreich durch. Es gibt jedoch einige ungewöhnliche Implementierungen, potenzielle Bugs und fehlende Testabdeckung, die im Folgenden dokumentiert sind.

---

## 1. Ungewöhnliche Implementierungen

### 1.1 Hartcodierter Windows-Pfad (csv_plotter.py:30-33)
```python
SUMATRA_PDF_PATH = os.environ.get(
    "SUMATRA_PDF_PATH",
    r"C:\PortableApps\SumatraPDFPortable\SumatraPDFPortable.exe"
)
```
**Problem:** Hartcodierter Windows-spezifischer Pfad als Default.  
**Impact:** Tool funktioniert nur auf Windows mit dieser spezifischen Installation.  
**Empfehlung:** Als Konfigurationsparameter dokumentieren oder bessere Fehlermeldung.

**Status:** Bereits dokumentiert (Kommentar erklärt Windows-Bezug + Override via `SUMATRA_PDF_PATH`-Umgebungsvariable). Kein weiterer Handlungsbedarf.

### 1.2 Magic Number: max_rows_per_col = 30 (csv_plotter.py:360)
```python
max_rows_per_col = 30
```
**Problem:** Keine Erklärung warum 30 Zeilen pro Subtabelle.  
**Impact:** Bei anderen Schriftgrößen oder Seitenrändern könnte die Tabelle nicht mehr auf eine A4-Seite passen.  
**Empfehlung:** Als Konstanten mit Dokumentation oder als konfigurierbarer Parameter.

**Status:** Bereits als `_MAX_ROWS_PER_SUBTABLE`-Konstante mit erklärendem Kommentar umgesetzt.

### 1.3 Toleranz gegenüber doppelten Punkten (column_parser.py:103)
```python
cleaned = re.sub(r'\.+', '.', s)  # "1..234,56" → "1.234,56"
```
**Problem:** Absichtliche Toleranz gegenüber fehlerhaften Eingaben ("1..234,56").  
**Impact:** Könnte legitime Datenmaskierung überschreiben.  
**Empfehlung:** Als bewusste Design-Entscheidung dokumentieren.

**Status:** Bereits im Docstring von `_is_german_number` als bewusste Toleranz dokumentiert.

---

## 2. Potenzielle Bugs

### 2.1 Gemischte ISO- und deutsche Datumsformate (column_parser.py:256-260)

**Beschreibung:** Bei gemischten Datumsformaten innerhalb einer Spalte (>60% ISO-Format) wird `dayfirst=False` verwendet, wodurch einzelne deutsche Datumsangaben zu NaT werden.

**Status: Akzeptierter Trade-off, kein Fix erforderlich.** Die Format-Erkennung arbeitet bewusst spaltenweise (siehe Modul-Docstring in column_parser.py) und versucht das wahrscheinlichste Format für die gesamte Spalte zu bestimmen. Nicht konvertierbare Einzelwerte werden nicht stillschweigend verworfen, sondern über `ColumnResult.warnings` gemeldet (siehe `_collect_conversion_warnings`). Zusätzlich lässt sich die Heuristik bei Bedarf über `--dayfirst`/`--decimal` (CLI) bzw. `dayfirst_override`/`decimal_override` (API) für den gesamten Lauf übersteuern. Damit ist weder stiller Datenverlust noch fehlende Korrekturmöglichkeit gegeben.

### 2.2 _is_german_number erkennt "+1," als gültig (column_parser.py:97)

**Status:** Bereits im Docstring von `_is_german_number` als bewusste Toleranz für Randfälle dokumentiert (Heuristik wird für Mehrheitsentscheide verwendet, nicht für exakte Validierung).

### 2.3 Unklare Logik: detect_column_type prüft NUMERIC zweimal (column_parser.py:207-221)

**Problem:** Zwei separate NUMERIC-Checks (deutsches Format, dann einfache to_numeric) konnten bei gemischten Spalten (z.B. 50% deutsch, 50% englisch notiert) inkonsistent greifen.

**Status: Behoben.** Beide Heuristiken werden jetzt pro Wert kombiniert (`_is_german_number(v) OR to_numeric-erkennbar`) und gemeinsam gegen den 60%-Schwellwert geprüft, statt sequentiell zwei getrennte Schwellwert-Checks durchzuführen.

---

## 3. Fehlende Testabdeckung

Alle acht ursprünglich identifizierten Lücken sind mittlerweile abgedeckt:

1. locale-Fehlerbehandlung (setlocale fehlschlägt) → `test_setlocale_failure_falls_back_gracefully`, `test_setlocale_c_locale_failure_falls_back_gracefully`, `test_setlocale_generic_exception_is_also_caught`
2. _restore_locale mit fehlerhaftem Locale → `test_restore_calls_setlocale_with_original`
3. Komplett leere CSV-Dateien (0 Bytes) → `test_zero_byte_file_raises_pandas_empty_data_error`
4. Grenzfälle bei Subtabellen (31, 59, 61 Zeilen) → `test_subtable_count_at_boundaries` (parametrisiert)
5. _unescape_newlines mit mehrfach-escaped Strings → abgedeckt in `TestUnescapeNewlines`
6. plot_data mit 7+ Dateien (Marker-Wrap-around) → `test_seven_files_wraps_marker_list`, `test_ten_files_wraps_marker_and_color_lists`
7. Y-Achsen-Logarithmus-Skalierung → **kein Feature im Code vorhanden** (keine `set_yscale`-Verwendung); ursprünglicher Punkt war gegenstandslos
8. Integrationstests mit echten PDF-Erstellungen → `test_full_pipeline_end_to_end_from_csv_to_pdfs`

---

## 4. Weitere Auffälligkeiten

### 4.1 Warnungen in Tests
**Status:** Behoben — `pd.to_datetime`-Aufrufe unterdrücken die "Could not infer format"-Warnung gezielt (`_to_datetime_quiet`), da nicht konvertierbare Werte bereits über `_collect_conversion_warnings` gemeldet werden. Testlauf ist warnungsfrei (auch mit `-W error::UserWarning`).

### 4.2 Inkonsistente Fehlerbehandlung
**Status:** Als bewusste Strategie im Docstring von `main()` dokumentiert: csv_plotter.py ist die einzige Stelle mit `sys.exit`, csv_parser.py wirft `ValueError` bei nicht lesbaren Dateien, column_parser.py gibt bewusst Fallback-Werte + Warnungen statt Exceptions zurück (damit einzelne unparsbare Werte nicht den ganzen Lauf abbrechen).

### 4.3 Keine Type Hints in einigen Funktionen
**Status:** Geprüft — alle öffentlichen und internen Funktionen in allen vier Hauptmodulen haben vollständige Type Hints.

### 4.4 Magische Strings
**Status:** Behoben — Plot-Titel ("Messdaten"/"Vergleich Messungen") sind jetzt als `_PLOT_TITLE_SINGLE`/`_PLOT_TITLE_MULTI`-Konstanten definiert; Datumsformat war bereits als `_DATE_DISPLAY_FORMAT` ausgelagert.

---

## 5. Fazit

Alle im ursprünglichen Review als Priorität HOCH/MITTEL/NIEDRIG eingestuften Punkte sind entweder bereits als bewusste Design-Entscheidung dokumentiert, durch bestehende Tests abgedeckt, oder wurden in diesem Durchgang behoben (detect_column_type-Konsolidierung, Magic-String-Konstanten, Fehlerbehandlungs-Dokumentation). Bug 2.1 (gemischte Datumsformate) wird als akzeptierter Trade-off geführt, da Warnung + manuelle Übersteuerung als ausreichende Absicherung gelten.
