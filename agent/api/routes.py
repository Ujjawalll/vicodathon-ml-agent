from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from agent.models.schemas import AgentInitRequest, AgentInitResponse, FeedResponse, Topic, Post
from agent.scheduler.runner import initialize_agent
from agent.storage.database import db

router = APIRouter()


@router.post("/api/agent/init", response_model=AgentInitResponse)
async def init_agent(request: AgentInitRequest):
    persona_name = request.persona.get("name", "Marcus")
    persona_domain = request.persona.get("domain", "ML Engineering")
    
    agent_id = await initialize_agent(persona_name, persona_domain)
    
    return AgentInitResponse(agentId=agent_id)


@router.get("/api/agent/feed", response_model=FeedResponse)
async def get_feed(agentId: str = Query(..., alias="agentId")):
    agent = db.get_agent(agentId)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    posts = db.get_all_posts(agentId)
    
    return FeedResponse(posts=posts)


class TopicStatus(BaseModel):
    id: str
    title: str
    url: str
    source: str
    source_category: str
    summary: str
    discovered_at: str
    evaluated_at: Optional[str]
    score: Optional[float]
    judgment_reasoning: Optional[str]
    published: bool


class AgentProgressResponse(BaseModel):
    agent_id: str
    persona_name: str
    persona_domain: str
    created_at: str
    last_run: Optional[str]
    total_topics_discovered: int
    topics_evaluated: int
    topics_published: int
    topics_pending: int
    topics_rejected: int
    recent_topics: List[TopicStatus]
    recent_posts: List[Post]


@router.get("/api/agent/progress", response_model=AgentProgressResponse)
async def get_progress(agentId: str = Query(..., alias="agentId")):
    agent = db.get_agent(agentId)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    with db.get_conn() as conn:
        topic_rows = conn.execute(
            """SELECT * FROM topics 
               WHERE agent_id = ? 
               ORDER BY discovered_at DESC""",
            (agentId,)
        ).fetchall()
    
    topics = [db._row_to_topic(row) for row in topic_rows]
    
    total_discovered = len(topics)
    evaluated = sum(1 for t in topics if t.evaluated_at is not None)
    published = sum(1 for t in topics if t.published)
    pending = sum(1 for t in topics if t.evaluated_at is None)
    rejected = sum(1 for t in topics if t.evaluated_at is not None and not t.published)
    
    recent_topics = [
        TopicStatus(
            id=t.id,
            title=t.title,
            url=t.url,
            source=t.source,
            source_category=t.source_category,
            summary=t.summary,
            discovered_at=t.discovered_at.isoformat(),
            evaluated_at=t.evaluated_at.isoformat() if t.evaluated_at else None,
            score=t.score,
            judgment_reasoning=t.judgment_reasoning,
            published=t.published,
        )
        for t in topics[:20]
    ]
    
    posts = db.get_all_posts(agentId)
    recent_posts = posts[:10]
    
    return AgentProgressResponse(
        agent_id=agent.id,
        persona_name=agent.persona_name,
        persona_domain=agent.persona_domain,
        created_at=agent.created_at.isoformat(),
        last_run=agent.last_run.isoformat() if agent.last_run else None,
        total_topics_discovered=total_discovered,
        topics_evaluated=evaluated,
        topics_published=published,
        topics_pending=pending,
        topics_rejected=rejected,
        recent_topics=recent_topics,
        recent_posts=recent_posts,
    )