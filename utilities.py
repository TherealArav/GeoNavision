import pandas as pd
import io

def parse_markdown_table(md_string: str) -> pd.DataFrame:
    """
    Parses a raw markdown string to extract the first table found.
    ---
    Logic:
    1. Filter lines to find those containing '|'
    2. Split and clean headers from the first line
    3. Skip the alignment row (dashes)
    4. Extract data from subsequent lines
    """
    # Filter for table lines
    lines = [line.strip() for line in md_string.split('\n') if '|' in line]
    
    if not lines:
        return pd.DataFrame()

    def split_row(row_str):
        # Remove leading/trailing pipes and split
        parts = row_str.strip('|').split('|')
        return [p.strip() for p in parts]

    # Extract Headers (Line 0)
    headers = split_row(lines[0])
    
    # Extract Data (Skip Line 1 - the separator/alignment row)
    data_rows = []
    for line in lines[2:]:
        row_data = split_row(line)
        # Ensure row matches header length to avoid misalignment
        if len(row_data) == len(headers):
            data_rows.append(row_data)
    
    return pd.DataFrame(data_rows, columns=headers)


