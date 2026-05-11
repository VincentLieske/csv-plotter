# -------------------------------------------------
# ColumnParser – centralised parsing of CSV columns
# -------------------------------------------------
from enum import Enum
import pandas as pd
from date_format_detector import DateFormatDetector
import re
from enum import Enum
from dataclasses import dataclass

class ColumnType(Enum):
    DATE = 'date'
    NUMERIC = 'numeric'
    TEXT = 'text'

@dataclass
class ColumnResult:
    """Ergebnis-Objekt für ColumnParser.parse_column_to_series()"""
    series: pd.Series
    column_type: ColumnType
    column_name: str

# Re‑use the existing ColumnType enum and helpers
# (assume they are imported in the same module)

class ColumnParser:
    """
    Utility class that knows how to turn a raw pandas Series
    (the raw CSV column) into the correctly typed representation
    used by the plotting code.
    """

    @staticmethod
    def parse_column_to_series(column_values: pd.Series, column_name: str = "") -> ColumnResult:
        """
        Parse *series* automatisch und bestimme den Typ.
        
        Parameters
        ----------
        column_values : pd.Series
            Raw values read from the CSV file.
        column_name : str, optional
            Name of the column (header)

        Returns
        -------
        ColumnResult
            Objekt mit:
            - series: Geparste Series (DATE → datetime64[ns] (invalid → NaT), NUMERIC → float64 (comma/point handled, invalid → NaN), TEXT → string)
            - column_type: Der automatisch erkannte ColumnType
            - column_name: Name der Spalte (header)
        """
        # Automatische Typenerkennung
        column_type = ColumnParser.detect_column_type(column_values)
        print(f"[DEBUG] Achse erkannt als: {column_type.name} ({column_type.value})")

        # Series entsprechend dem Typ parsen
        if column_type == ColumnType.DATE:
            parsed_series = ColumnParser._parse_date_column(column_values)
        elif column_type == ColumnType.NUMERIC:
            parsed_series = ColumnParser._parse_numeric_column(column_values)
        else:  # TEXT
            parsed_series = ColumnParser._parse_text_column(column_values)
        return ColumnResult(series=parsed_series, column_type=column_type, column_name=column_name)


    @staticmethod
    def _parse_text_column(column_values: pd.Series) -> pd.Series:
        """Simple string column – strip whitespace."""
        return column_values.astype(str).str.strip()

    # -----------------------------------------------------------------
    # Private helpers – keep the original parsing logic in one place
    # -----------------------------------------------------------------
    @staticmethod
    def _parse_date_column(column_values: pd.Series) -> pd.Series:
        """
        Parses a date column to datetime format.
        
        Args:
            column_values: Series of date values
        
        Returns:
            Series with datetime64[ns] format (invalid values coerced to NaT)
        """
        detector = DateFormatDetector()
        dayfirst = detector.detect_dayfirst(column_values)
        print(f"[DEBUG] Detected dayfirst in parse_date_column: {dayfirst}")
        # `errors='coerce'` turns unparsable entries into NaT
        return pd.to_datetime(column_values, dayfirst=dayfirst, errors='coerce')

    @staticmethod
    def _parse_numeric_column(column_values: pd.Series) -> pd.Series:
        """
        Convert column values to numeric, handling both . and , as decimal separators.
        """
        """
        Exact copy of the original `parse_numeric_column` implementation,
        but kept private to avoid polluting the public API.
        """
        def convert_value(val):
            val_str = str(val).strip()
            if not val_str:
                return float('nan')
            # Replace German decimal comma with point
            val_str = val_str.replace(',', '.')
            try:
                return float(val_str)
            except ValueError:
                return float('nan')

        return column_values.apply(convert_value)

    # ---------------------------
    # Hilfsfunktion zur automatischen Spalten-Typ-Erkennung
    # ---------------------------
    @staticmethod
    def detect_column_type(column_values):
        """
        Detect column type: ColumnType.DATE, ColumnType.NUMERIC, or ColumnType.TEXT.
        
        Returns:
        - ColumnType.DATE: If column contains date values
        - ColumnType.NUMERIC: If column contains numeric values (robust against . and , decimal separators)
        - ColumnType.TEXT: Otherwise
        
        Handles common missing value indicators like NA, N/A, None, NaN, empty strings, etc.
        """
        # Datumsformate zum Testen
        date_patterns = [
            r'^\d{1,2}\.\d{1,2}\.\d{4}$',  # DD.MM.YYYY
            r'^\d{4}-\d{1,2}-\d{1,2}$',    # YYYY-MM-DD
            r'^\d{1,2}/\d{1,2}/\d{4}$',    # DD/MM/YYYY
            r'^\d{4}/\d{1,2}/\d{2}$',      # YYYY/MM/DD
            r'^\d{1,2}\.\d{1,2}\.\d{2}$',  # DD.MM.YY
            r'^\d{4}-\d{1,2}-\d{2}$',      # YYYY-MM-YY
        ]
        
        date_count = 0
        numeric_count = 0
        total_count = 0
        
        missing_indicators = {'nan', 'na', 'n/a', '-', '--', 'null', 'none', ''}
        
        # Auf Zahlen prüfen, indem wir convert_column_to_numeric simulieren
        # Wir casten zuerst auf Series, falls nicht bereits einer ist
        col_series = pd.Series(column_values)
        converted = ColumnParser._parse_numeric_column(col_series)

        for val in col_series.head(min(100, len(col_series))):
            val_str = str(val).strip().lower()
            
            # Skip missing value indicators
            if val_str in missing_indicators or not val_str.strip():
                continue
            
            total_count += 1
            
            # Prüfung auf Datumsformat
            is_date = any(re.match(pattern, val_str) for pattern in date_patterns)
            if is_date:
                date_count += 1
                continue
            
            # Wenn nach Convertierung numerisch, dann zählen
            # Wir nutzen `pd.isna(...)` statt direktem float-Vergleich, um NaN zu erkennen
            try:
                if not pd.isna(converted.iloc[total_count - 1]):
                    numeric_count += 1
            except IndexError:
                pass
        
        if total_count == 0:
            return ColumnType.TEXT
        
        # Mehrheitslogik: Wenn >60% Datumsformat, dann Datum
        if date_count / total_count > 0.6:
            return ColumnType.DATE
        # Wenn >60% numerisch, dann numerisch
        elif numeric_count / total_count > 0.6:
            return ColumnType.NUMERIC
        else:
            return ColumnType.TEXT
