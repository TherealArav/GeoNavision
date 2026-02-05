import pandas as pd
import io
from typing import Any

from langchain_core.documents import Document

def parse_markdown_table(md_string: str,docs: list[Document] = []) -> pd.DataFrame:
    """
    Parses a raw markdown string to extract the first table found.
    ---
    Logic:
    1. Filter lines to find those containing '|'
    2. Split and clean headers from the first line
    3. Skip the alignment row (dashes)
    4. Extract data from subsequent lines
    5. Store data in a DataFrame for easy manipulation and retrieval. 
    """

    # Extract documents for data if available
    meta_data = []
    for doc in docs:
        
        try:
            meta: dict = doc.metadata
            # Only include metadata if it has valid latitude and longitude values
            if not meta.latitude or  not meta.longitude:
                meta.latitude = 0.0
                meta.longitude = 0.0
                print(f"DEBUG: Document metadata missing lat/lon, defaulting to 0.0: {meta}\n")
            meta_data.append(meta)
        except Exception as e:
            print(f"Error extracting metadata from document: {e}")
            meta_data.append({})
    
    meta_df = pd.DataFrame(meta_data) if meta_data else pd.DataFrame()
        
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
    
    # Create Dataframe from extracted data
    parsed_df = pd.DataFrame(data_rows, columns=headers)
    meta_df = meta_df.iloc[:len(parsed_df)].reset_index(drop=True)
    
    # Joined LLM parsed data with metadata
    # Final DataFrame will have [Place Name, Distance, Accessibility Features, Additional Information, poi_name,address,distance_km,latitude,longitude,wheelchair]
    return pd.concat([parsed_df, meta_df], axis=1)


