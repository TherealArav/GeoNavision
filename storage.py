"""Module for handling data storage and retrieval, including caching query results based on user location and query text. This module provides a structured way to manage cached data, ensuring efficient retrieval and storage while maintaining data integrity and security."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, ConfigDict
from geopy.distance import great_circle
from typing import TYPE_CHECKING, Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
from numpy.linalg import norm
import numpy as np
import sqlite3
import json

if TYPE_CHECKING:
    import pandas as pd


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""

    if not vec1 or not vec2:
        return 0.0

    # Ensure both vectors are of the same length/dimension
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must be of the same length for cosine similarity.")

    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product: float = np.dot(vec1_np, vec2_np)
    norm_vec1: float = norm(vec1_np)
    norm_vec2: float = norm(vec2_np)

    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0

    return dot_product / (norm_vec1 * norm_vec2)


class QueryRecord(BaseModel):
    """Schema for a cached spatial query result."""

    # Allows Pydantic to read data directly from objects like sqlite3.Row
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    query: str
    lat: float = Field(ge=-90.0, le=90.0, description="Valid latitude")
    lon: float = Field(ge=-180.0, le=180.0, description="Valid longitude")
    summary: Optional[str] = None
    # We enforce that table_data is a list of records, not just a raw string
    table_data: List[Dict[str, Any]] = Field(default_factory=list)
    # Store the 384-dimensional vector
    embedding: List[float] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        """Automatically lowercase and strip whitespace from queries before they are used."""
        return v.strip().lower()


class QueryStorage:
    def __init__(self, db_path: str = "spatial_cache.db"):
        """
        Initializes the SQLite database.
        Row-based storage is used for optimal single-record retrieval.
        """
        self.db_path = Path(db_path)
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _create_table(self) -> None:
        """
        Creates the cache table and indices for performance.
        """
        with self._get_connection() as conn:
            # Table for storing RAG results
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    summary TEXT,
                    table_data TEXT,
                    embedding TEXT,
                    timestamp TEXT
                )
            """
            )
            # Indexing the query column makes text lookups instantaneous
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_query ON cached_queries(query)"
            )
            conn.commit()

    def find_nearby_query(
        self,
        query_text: str,
        user_embedding: List[float],
        lat: float,
        lon: float,
        threshold_meters: int = 500,
        similarity_threshold: float = 0.85,
    ) -> Optional[QueryRecord]:
        """
        Retrieves a cached result if the user is within the threshold distance.
        """

        user_loc = (lat, lon)

        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM cached_queries")
            rows: List[Dict[str, Any]] = cursor.fetchall()

        best_record: Optional[QueryRecord] = None
        highest_score = -1
        valid_results = []
        for row in rows:
            try:
                raw_data = dict(row)
                raw_data["table_data"] = json.loads(raw_data["table_data"])

                if raw_data["embedding"]:
                    raw_data["embedding"] = json.loads(raw_data["embedding"])

                record = QueryRecord.model_validate(raw_data)

                stored_loc = (record.lat, record.lon)
                distance = great_circle(user_loc, stored_loc).meters

                if distance > threshold_meters:
                    continue

                score = cosine_similarity(user_embedding, record.embedding)

                if score >= similarity_threshold and score > highest_score:
                    best_record = record
                    highest_score = score

            except Exception as e:
                print(f"Error processing cached record ID {row['id']}: {e}")
                continue

        if not best_record:
            return None

        # Return the most recent record matching the location
        return best_record

    def save_query_result(self, record: Optional[QueryRecord]) -> None:
        """
        Saves result to local storage, serializing the DataFrame to JSON.
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cached_queries (query, lat, lon, summary, table_data, embedding, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.query,
                    record.lat,
                    record.lon,
                    record.summary,
                    json.dumps(record.table_data),
                    json.dumps(record.embedding),  # Serialize vector to JSON
                    record.timestamp.isoformat(),
                ),
            )
            conn.commit()

    def _delete_query_result(self, query_text: str, lat: float, lon: float) -> None:
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
               WHERE query = ? AND lat = ? AND lon = ?""",
                (query_text, lat, lon),
            )
            conn.commit()
