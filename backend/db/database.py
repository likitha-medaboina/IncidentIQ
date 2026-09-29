import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.models import Incident, ScoreboardMetric

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    service TEXT,
                    severity TEXT,
                    alert_text TEXT,
                    raw_data TEXT,
                    root_cause TEXT,
                    recommended_fix TEXT,
                    outcome TEXT,
                    is_simulated INTEGER DEFAULT 1
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT,
                    action TEXT,
                    edited_fix TEXT,
                    engineer_feedback TEXT,
                    engineer_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scoreboard_evals (
                    interaction INTEGER PRIMARY KEY,
                    incident_id TEXT,
                    root_cause_accuracy REAL,
                    investigation_steps_count INTEGER,
                    acceptance_status TEXT,
                    time_to_recall_ms REAL,
                    confidence TEXT,
                    matched_past_incident INTEGER,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def save_incident(self, incident: Incident):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO incidents 
                (id, timestamp, service, severity, alert_text, raw_data, root_cause, recommended_fix, outcome, is_simulated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                incident.id,
                incident.timestamp,
                incident.service,
                incident.severity,
                incident.alert_text,
                incident.model_dump_json(),
                incident.root_cause,
                incident.recommended_fix,
                incident.outcome,
                1 if incident.is_simulated else 0
            ))
            conn.commit()

    def record_feedback(self, incident_id: str, action: str, edited_fix: Optional[str], feedback: Optional[str], engineer_name: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback_history (incident_id, action, edited_fix, engineer_feedback, engineer_name)
                VALUES (?, ?, ?, ?, ?)
            """, (incident_id, action, edited_fix, feedback, engineer_name))
            conn.commit()

    def record_scoreboard_metric(self, metric: ScoreboardMetric):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scoreboard_evals 
                (interaction, incident_id, root_cause_accuracy, investigation_steps_count, acceptance_status, time_to_recall_ms, confidence, matched_past_incident, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.interaction,
                metric.incident_id,
                metric.root_cause_accuracy,
                metric.investigation_steps_count,
                metric.acceptance_status,
                metric.time_to_recall_ms,
                metric.confidence,
                1 if metric.matched_past_incident else 0,
                metric.notes
            ))
            conn.commit()

    def get_scoreboard_metrics(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scoreboard_evals ORDER BY interaction ASC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def reset_evals(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scoreboard_evals")
            cursor.execute("DELETE FROM feedback_history")
            conn.commit()

db = Database()
