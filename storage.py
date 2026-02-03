import sqlite3
import pandas as pd
import json
from datetime import datetime
from geopy.distance import great_circle
from typing import Optional, Dict, Any

class QueryStorage:
    def __init__(self, db_path: str = "spatial_cache.db"):
        """
        Initializes the SQLite database.
        Row-based storage is used for optimal single-record retrieval.
        """
        self.db_path = db_path
        self._create_table()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
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

    def save_query_result(self, query_text: str, lat: float, lon: float, df: pd.DataFrame, summary: str):
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

if __name__ == "__main__":
    storage = QueryStorage("test_cache.db")
    print("Local SQLite Storage Initialized with indexing.")