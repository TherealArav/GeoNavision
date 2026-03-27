from geopy.distance import great_circle
from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd
import sqlite3
import json


class QueryStorage:
    def __init__(self, db_path: str = "spatial_cache.db"):
        """
        Initializes the SQLite database.
        Row-based storage is used for optimal single-record retrieval.
        """
        self.db_path = db_path
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _create_table(self) -> None:
        """
        Creates the cache table and indices for performance.
        """
        with self._get_connection() as conn:
            # Table for storing RAG results
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    summary TEXT,
                    table_data TEXT,
                    timestamp TEXT
                )
            """)
            # Indexing the query column makes text lookups instantaneous
            conn.execute("CREATE INDEX IF NOT EXISTS idx_query ON cached_queries(query)")
            conn.commit()
    
    def _display_db_size(self) -> None:
        """
        Docstring for _display_db_size
        Interal method to display the size of the database file for debugging purposes.

        :param self: Description
        """

        with self._get_connection() as conn:
            cursor = conn.execute("PRAGMA page_count;")
            page_count = cursor.fetchone()[0]
            cursor = conn.execute("PRAGMA page_size;")
            page_size = cursor.fetchone()[0]
            db_size_bytes = page_count * page_size
            print(f"DEBUG: Database size is {db_size_bytes / (1024 * 1024):.2f} MB")
        
    
    def _display_table(self, cols="*") -> None:
        """
        Internal method to display records in the cached_queries table.
        Secured against SQL injection via strict column allowlisting.

        :param cols: List of column names to retrieve, or '*' for all columns.
        """
        # 1. Define the absolute source of truth for allowed columns
        VALID_COLUMNS = {"id", "query", "lat", "lon", "summary", "table_data", "timestamp"}

        with self._get_connection() as conn:
            if cols == "*":
                safe_cols = "*"
            elif isinstance(cols, list):
                # 2. Check for any injected or invalid columns
                invalid_cols = [col for col in cols if col not in VALID_COLUMNS]
                if invalid_cols:
                    # Immediately reject the request if an unknown column is passed
                    raise ValueError(f"Invalid or unauthorized column names provided: {invalid_cols}")
                
                # 3. Safe to join because we've proven the contents are strictly from our list
                safe_cols = ", ".join(cols)
            else:
                raise ValueError("cols must be a list of column names or '*'")
            
            # The f-string is now 100% safe because 'safe_cols' is completely controlled
            df = pd.read_sql_query(f"SELECT {safe_cols} FROM cached_queries", conn)
            
            if df.empty:
                print('DEBUG: No records found')
                return 'DEBUG: No records found'
            else:
                print(df)
                return df
        
    def find_nearby_query(self, query_text: str, lat: float, lon: float, threshold_meters: int = 100) -> Optional[Dict[str, Any]]:
        """
        Retrieves a cached result if the user is within the threshold distance.
        """
        query_text = query_text.lower()
        user_loc = (lat, lon)
        
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row 
            # The index 'idx_query' makes this SELECT extremely fast
            cursor = conn.execute(
                "SELECT * FROM cached_queries WHERE query = ?", 
                (query_text,)
            )
            rows = cursor.fetchall()

        valid_results = []
        for row in rows:
            stored_loc = (row["lat"], row["lon"])
            distance = great_circle(user_loc, stored_loc).meters
            
            if distance <= threshold_meters:
                data = dict(row)
                data["table_data"] = json.loads(data["table_data"])
                valid_results.append(data)

        if not valid_results:
            return None

        # Return the most recent record matching the location
        return sorted(valid_results, key=lambda x: x["timestamp"], reverse=True)[0]

    def save_query_result(self, query_text: str, lat: float, lon: float, df: pd.DataFrame, summary: str) -> None:
        """
        Saves result to local storage, serializing the DataFrame to JSON.
        """
        table_json = json.dumps(df.to_dict('records'))
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO cached_queries (query, lat, lon, summary, table_data, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (query_text.lower(), lat, lon, summary, table_json, timestamp))
            conn.commit()

    def _delete_query_result(self,query_text: str, lat: float, lon: float) -> None:
        """
        Delete old query results from local storage based on query text and location.
        This method is for clearing cache entries that are no longer relevant or to manage storage size. 

        :param self: Description
        :param query_text: The text of the query to identify  which cache entry to delete.
        :param lat: The latitude of the location associated with the cache entry to delete.
        :param lon: The longitude of the location associated with the cache entry to delete.
        """

        with self._get_connection() as conn:
            conn.execute(
            """DELETE FROM cached_queries 
               WHERE query = ? AND lat = ? AND lon = ?"""
            ,(query_text,lat,lon))
            conn.commit()

if __name__ == "__main__":
    storage = QueryStorage("spatial_cache.db")
    print("Local SQLite Storage Initialized with indexing.")
    storage._display_table(['id','query'])

    