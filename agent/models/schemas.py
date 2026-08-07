from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import hashlib


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    persona_name: str
    persona_domain: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_run: Optional[datetime] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class Topic(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    title: str
    url: str
    source: str
    source_category: str
    summary: str
    content_hash: str
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    evaluated_at: Optional[datetime] = None
    score: Optional[float] = None
    judgment_reasoning: Optional[str] = None
    published: bool = False

    @classmethod
    def create_hash(cls, title: str, url: str) -> str:
        content = f"{title}|{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class Post(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    topic_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    text: str
    rationale: str
    sources: List[str] = Field(default_factory=list)


class AgentInitRequest(BaseModel):
    persona: Dict[str, str]


class AgentInitResponse(BaseModel):
    agentId: str


class FeedResponse(BaseModel):
    posts: List[Post]


class TopicEvaluation(BaseModel):
    score: float
    reasoning: str
    should_publish: bool


class PostGeneration(BaseModel):
    text: str
    rationale: str