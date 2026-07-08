"""
Datumsformat-Erkennung für deutsche und internationale Formate.

Unterstützte Formate:
- DD.MM.YYYY, DD.MM.YY (Deutsch/Europäisch)
- DD-MM-YYYY, DD/MM/YYYY (Europäisch)
- YYYY-MM-DD, YYYY/MM/DD (ISO)
"""
import re
import pandas as pd


def detect_dayfirst(series: pd.Series) -> bool:
    """
    Erkennt automatisch, ob die Spalte deutsches/europäisches (Tag zuerst)
    oder US-amerikanisches (Monat zuerst) Datumsformat verwendet.

    Strategie:
    - Wenn erste Komponente > 12: muss ein Tag sein → dayfirst=True
    - Wenn zweite Komponente > 12: muss ein Tag sein → dayfirst=False
    - Bei mehrdeutigen Werten (z.B. 01-02-2026): Mehrheitsvoting über alle erkannten Werte
    - ISO-Datum YYYY-MM-DD: wird ignoriert (erste Komponente ist Jahr, keine Aussage über Reihenfolge)
    - Fallback: True (deutsches Format ist wahrscheinlicher)

    Returns:
        bool: True wenn dayfirst (DD.MM.YYYY), False wenn monthfirst (MM.DD.YYYY)
    """
    day_evidence = 0      # Zähler für Tag-zuerst-Indizien
    month_evidence = 0    # Zähler für Monat-zuerst-Indizien

    # Scanne alle nicht-leeren Werte
    for val in series.dropna():
        # Teile Datum in Komponenten (Trennzeichen: -, /, .)
        parts = re.split(r"[-/.]", str(val).strip())
        if len(parts) != 3:
            continue

        try:
            first, second, third = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue

        # ISO-Format YYYY-MM-DD: erste Komponente ist Jahr (> 31), überspringen
        if first > 31:
            continue

        # Wenn erste Komponente > 12: kann kein Monat sein → Tag zuerst
        if first > 12:
            day_evidence += 1
        # Wenn zweite Komponente > 12: kann kein Monat sein → Monat zuerst
        elif second > 12:
            month_evidence += 1

    # Mehrheitsvoting: dayfirst=True wenn Tag-Indizien >= Monat-Indizien (Fallback auf Deutsch)
    return month_evidence <= day_evidence
