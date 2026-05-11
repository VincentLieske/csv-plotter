from collections import Counter
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Iterable, Optional

import re

from enum import Enum

class DateFormat(Enum):
    ISO = "ISO"
    DAYFIRST = "DAYFIRST"
    MONTHFIRST = "MONTHFIRST"

# =========================================================
# Result Object
# =========================================================

@dataclass
class ParsedDate:
    original: str
    parsed: Optional[datetime]
    detected_format: Optional[DateFormat]
    confidence: float
    ambiguous: bool
    reason: str

# =========================================================
# Date Format Detector
# =========================================================

class DateFormatDetector:
    """
    Erkennt automatisch:
    - DAYFIRST (DE/EU)
    - MONTHFIRST (US)
    - ISO
    - Mehrdeutigkeiten
    - statistische Präferenzen über viele Werte

    Unterstützte Formate:
    ---------------------
    01-02-2026
    1/2/2026
    2026-02-01
    2026/02/01
    01.02.2026
    20260201
    """

    FORMATS = {
        DateFormat.ISO: [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%Y%m%d",
        ],
        DateFormat.DAYFIRST: [
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%d-%m-%y",
            "%d/%m/%y",
            "%d.%m.%y",
        ],
        DateFormat.MONTHFIRST: [
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%m.%d.%Y",
            "%m-%d-%y",
            "%m/%d/%y",
            "%m.%d.%y",
        ],
    }

    def __init__(self):
        self.stats = Counter()

    # =====================================================
    # Public API
    # =====================================================

    def fit(self, values: Iterable[str]) -> None:
        """
        Analysiert alle Werte und sammelt statistische Evidenz.
        """

        self.stats.clear()

        for value in values:
            self._collect_evidence(str(value))

    def parse(self, value: str) -> ParsedDate:
        """
        Parst einen einzelnen Wert.
        """

        s = str(value).strip()

        # -------------------------------------------------
        # ISO zuerst
        # -------------------------------------------------

        iso = self._try_formats(s, DateFormat.ISO)

        if iso:
            return ParsedDate(
                original=s,
                parsed=iso,
                detected_format=DateFormat.ISO,
                confidence=1.0,
                ambiguous=False,
                reason="ISO format is unambiguous",
            )

        # -------------------------------------------------
        # Numerische Analyse
        # -------------------------------------------------

        numeric = self._extract_numeric_parts(s)

        if numeric:

            a, b, _ = numeric

            # ---------------------------------------------
            # Eindeutig DAYFIRST
            # ---------------------------------------------

            if a > 12:

                dt = self._try_formats(s, DateFormat.DAYFIRST)

                return ParsedDate(
                    original=s,
                    parsed=dt,
                    detected_format=DateFormat.DAYFIRST,
                    confidence=1.0,
                    ambiguous=False,
                    reason=f"First number ({a}) cannot be month",
                )

            # ---------------------------------------------
            # Eindeutig MONTHFIRST
            # ---------------------------------------------

            if b > 12:

                dt = self._try_formats(s, DateFormat.MONTHFIRST)

                return ParsedDate(
                    original=s,
                    parsed=dt,
                    detected_format=DateFormat.MONTHFIRST,
                    confidence=1.0,
                    ambiguous=False,
                    reason=f"Second number ({b}) cannot be month",
                )

            # ---------------------------------------------
            # Mehrdeutig -> Statistik verwenden
            # ---------------------------------------------

            return self._resolve_ambiguous(s)

        # -------------------------------------------------
        # Kein gültiges Format
        # -------------------------------------------------

        return ParsedDate(
            original=s,
            parsed=None,
            detected_format=None,
            confidence=0.0,
            ambiguous=True,
            reason="Unsupported or invalid format",
        )

    def parse_many(self, values: Iterable[str]) -> list[ParsedDate]:
        """
            Komplettanalyse:
            1. Statistik lernen
            2. Werte parsen
        """
        values = list(values)
        self.fit(values)
        return [self.parse(v) for v in values]


    def parse_series_generic(self, values: Iterable[str]) -> dict[ParsedDate]:
        """
            Generische Komfortfunktion, die ein Dictionary anstelle eines DataFrames zurückgibt. 
        """
        results = self.parse_many(values)

        return {
            f.name: [getattr(r, f.name) for r in results]
            for f in fields(ParsedDate)
        }
        

    def detect_dayfirst(self, column_values: Iterable[str]) -> bool:
        """
        Analysiert eine Spalte und gibt True zurück, wenn das Format 
        wahrscheinlich DAYFIRST (z.B. DD.MM.YYYY) ist.
        """
        # Wir nutzen parse_series_generic, um die statistische Analyse über die Spalte zu fahren
        results = self.parse_many(column_values)  # Wir nehmen das erste Ergebnis, da parse_many eine Liste zurückgibt
        first_result = results[0] if results else None

        # Wir prüfen den ersten erkannten Typ. 
        # Falls die Liste leer ist, fallback auf False.
        if not first_result or not first_result.detected_format:
            return False
            
        return first_result.detected_format == DateFormat.DAYFIRST  # ISO und MONTHFIRST werden hier als False gewertet, da sie nicht DAYFIRST sind 


    # =====================================================
    # Internal
    # =====================================================

    def _collect_evidence(self, s: str) -> None:

        numeric = self._extract_numeric_parts(s)

        if not numeric:
            return

        a, b, _ = numeric

        # eindeutig DAYFIRST
        if a > 12:
            self.stats[DateFormat.DAYFIRST] += 1

        # eindeutig MONTHFIRST
        elif b > 12:
            self.stats[DateFormat.MONTHFIRST] += 1

    def _resolve_ambiguous(self, s: str) -> ParsedDate:

        day_score = self.stats[DateFormat.DAYFIRST]
        month_score = self.stats[DateFormat.MONTHFIRST]

        total = day_score + month_score

        # -------------------------------------------------
        # Keine Evidenz
        # -------------------------------------------------

        if total == 0:

            dt = self._try_formats(s, DateFormat.DAYFIRST)

            return ParsedDate(
                original=s,
                parsed=dt,
                detected_format=DateFormat.DAYFIRST,
                confidence=0.5,
                ambiguous=True,
                reason="No statistical evidence, defaulting to DAYFIRST",
            )

        # -------------------------------------------------
        # Wahrscheinlichkeit berechnen
        # -------------------------------------------------

        day_prob = day_score / total
        month_prob = month_score / total

        # -------------------------------------------------
        # DAYFIRST gewinnt
        # -------------------------------------------------

        if day_prob >= month_prob:

            dt = self._try_formats(s, DateFormat.DAYFIRST)

            return ParsedDate(
                original=s,
                parsed=dt,
                detected_format=DateFormat.DAYFIRST,
                confidence=round(day_prob, 2),
                ambiguous=True,
                reason=f"Statistical preference DAYFIRST ({day_score}:{month_score})",
            )

        # -------------------------------------------------
        # MONTHFIRST gewinnt
        # -------------------------------------------------

        dt = self._try_formats(s, DateFormat.MONTHFIRST)

        return ParsedDate(
            original=s,
            parsed=dt,
            detected_format=DateFormat.MONTHFIRST,
            confidence=round(month_prob, 2),
            ambiguous=True,
            reason=f"Statistical preference MONTHFIRST ({month_score}:{day_score})",
        )

    def _try_formats(
        self,
        s: str,
        group: DateFormat,
    ) -> Optional[datetime]:

        for fmt in self.FORMATS[group]:

            try:
                return datetime.strptime(s, fmt)

            except ValueError:
                pass

        return None

    def _extract_numeric_parts(
        self,
        s: str,
    ) -> Optional[tuple[int, int, int]]:

        parts = re.split(r"[-/.]", s)

        if len(parts) != 3:
            return None

        try:
            return tuple(map(int, parts))

        except ValueError:
            return None


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":

    series = [
            "1-2-2026",
            "15-2-2026",
            "28-3-2026",
            "04/05/2026",
            "2026-12-01",
            "7/8/26",
            "1.2.2026",
            "14.2.2026",
            "2026.03.28",
        ]
    

    detector = DateFormatDetector()

    result = detector.parse_many(series)

    for r in result:
        print(r)