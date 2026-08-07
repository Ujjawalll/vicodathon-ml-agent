import sqlite3
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from agent.config import settings
from agent.models.schemas import Agent, Topic, Post


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = Path(settings.database_path)
        self._init_db()
        self._initialized = True

    @contextmanager
    def get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    persona_name TEXT NOT NULL,
                    persona_domain TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_run TEXT,
                    config TEXT
                );

                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    evaluated_at TEXT,
                    score REAL,
                    judgment_reasoning TEXT,
                    published INTEGER DEFAULT 0,
                    FOREIGN KEY (agent_id) REFERENCES agents (id)
                );

                CREATE INDEX IF NOT EXISTS idx_topics_agent ON topics(agent_id);
                CREATE INDEX IF NOT EXISTS idx_topics_hash ON topics(content_hash);
                CREATE INDEX IF NOT EXISTS idx_topics_published ON topics(published);

                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    topic_id TEXT,
                    created_at TEXT NOT NULL,
                    text TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES agents (id),
                    FOREIGN KEY (topic_id) REFERENCES topics (id)
                );

                CREATE INDEX IF NOT EXISTS idx_posts_agent ON posts(agent_id);
                CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
            """)

    def create_agent(self, agent: Agent) -> Agent:
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO agents (id, persona_name, persona_domain, created_at, last_run, config)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    agent.id,
                    agent.persona_name,
                    agent.persona_domain,
                    agent.created_at.isoformat(),
                    agent.last_run.isoformat() if agent.last_run else None,
                    json.dumps(agent.config),
                ),
            )
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()
            if row:
                return Agent(
                    id=row["id"],
                    persona_name=row["persona_name"],
                    persona_domain=row["persona_domain"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_run=datetime.fromisoformat(row["last_run"]) if row["last_run"] else None,
                    config=json.loads(row["config"]) if row["config"] else {},
                )
        return None

    def update_agent_last_run(self, agent_id: str, last_run: datetime):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE agents SET last_run = ? WHERE id = ?",
                (last_run.isoformat(), agent_id),
            )

    def topic_exists(self, agent_id: str, content_hash: str) -> bool:
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM topics WHERE agent_id = ? AND content_hash = ?",
                (agent_id, content_hash),
            ).fetchone()
        return row is not None

    def save_topic(self, topic: Topic) -> Topic:
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO topics (id, agent_id, title, url, source, source_category,
                   summary, content_hash, discovered_at, evaluated_at, score, judgment_reasoning, published)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    topic.id,
                    topic.agent_id,
                    topic.title,
                    topic.url,
                    topic.source,
                    topic.source_category,
                    topic.summary,
                    topic.content_hash,
                    topic.discovered_at.isoformat(),
                    topic.evaluated_at.isoformat() if topic.evaluated_at else None,
                    topic.score,
                    topic.judgment_reasoning,
                    1 if topic.published else 0,
                ),
            )
        return topic

    def update_topic_evaluation(
        self, topic_id: str, score: float, reasoning: str, published: bool
    ):
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE topics SET evaluated_at = ?, score = ?, judgment_reasoning = ?, published = ?
                   WHERE id = ?""",
                (datetime.utcnow().isoformat(), score, reasoning, 1 if published else 0, topic_id),
            )

    def get_unpublished_topics(self, agent_id: str, limit: int = 50) -> List[Topic]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM topics 
                   WHERE agent_id = ? AND published = 0 
                   ORDER BY discovered_at DESC LIMIT ?""",
                (agent_id, limit),
            ).fetchall()
        return [self._row_to_topic(row) for row in rows]

    def get_recent_posts(self, agent_id: str, limit: int = 10) -> List[Post]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM posts 
                   WHERE agent_id = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (agent_id, limit),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def save_post(self, post: Post) -> Post:
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO posts (id, agent_id, topic_id, created_at, text, rationale, sources)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    post.id,
                    post.agent_id,
                    post.topic_id,
                    post.created_at.isoformat(),
                    post.text,
                    post.rationale,
                    json.dumps(post.sources),
                ),
            )
        return post

    def get_all_posts(self, agent_id: str) -> List[Post]:
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM posts 
                   WHERE agent_id = ? 
                   ORDER BY created_at DESC""",
                (agent_id,),
            ).fetchall()
        return [self._row_to_post(row) for row in rows]

    def _row_to_topic(self, row: sqlite3.Row) -> Topic:
        return Topic(
            id=row["id"],
            agent_id=row["agent_id"],
            title=row["title"],
            url=row["url"],
            source=row["source"],
            source_category=row["source_category"],
            summary=row["summary"],
            content_hash=row["content_hash"],
            discovered_at=datetime.fromisoformat(row["discovered_at"]),
            evaluated_at=datetime.fromisoformat(row["evaluated_at"]) if row["evaluated_at"] else None,
            score=row["score"],
            judgment_reasoning=row["judgment_reasoning"],
            published=bool(row["published"]),
        )

    def _row_to_post(self, row: sqlite3.Row) -> Post:
        return Post(
            id=row["id"],
            agent_id=row["agent_id"],
            topic_id=row["topic_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            text=row["text"],
            rationale=row["rationale"],
            sources=json.loads(row["sources"]) if row["sources"] else [],
        )


db = Database()