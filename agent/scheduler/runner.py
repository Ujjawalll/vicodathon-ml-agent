from datetime import datetime
from agent.config import settings
from agent.storage.database import db
from agent.discovery.collector import discover_topics
from agent.judgment.evaluator import evaluate_topics
from agent.generation.writer import generate_post
from agent.models.schemas import Topic, Post


async def run_publishing_cycle(agent_id: str):
    print(f"[{datetime.utcnow().isoformat()}] Starting publishing cycle for agent {agent_id}")
    
    # Get existing topic hashes to avoid duplicates
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT content_hash FROM topics WHERE agent_id = ?", (agent_id,)
        ).fetchall()
    existing_hashes = {row["content_hash"] for row in rows}
    
    # Get recent posts for context
    recent_posts = db.get_recent_posts(agent_id, limit=settings.max_posts_in_context)
    recent_post_texts = [p.text for p in recent_posts]
    
    # Discover new topics
    print(f"  Discovering topics...")
    topics = await discover_topics(agent_id, existing_hashes)
    print(f"  Found {len(topics)} new topics")
    
    if not topics:
        print("  No new topics, skipping cycle")
        db.update_agent_last_run(agent_id, datetime.utcnow())
        return
    
    # Save discovered topics
    for topic in topics:
        db.save_topic(topic)
    
    # Evaluate topics
    print(f"  Evaluating {len(topics)} topics...")
    evaluations = await evaluate_topics(topics, recent_post_texts)
    
    published_count = 0
    for topic, evaluation in zip(topics, evaluations):
        db.update_topic_evaluation(
            topic.id, evaluation.score, evaluation.reasoning, evaluation.should_publish
        )
        
        if evaluation.should_publish and evaluation.score >= settings.publish_threshold:
            print(f"  Publishing: {topic.title} (score: {evaluation.score})")
            generation = await generate_post(topic, recent_post_texts)
            
            post = Post(
                agent_id=agent_id,
                topic_id=topic.id,
                created_at=datetime.utcnow(),
                text=generation.text,
                rationale=generation.rationale,
                sources=[topic.url],
            )
            db.save_post(post)
            published_count += 1
            
            # Update recent posts for next generation in this cycle
            recent_post_texts.insert(0, generation.text)
        else:
            print(f"  Rejected: {topic.title} (score: {evaluation.score}) - {evaluation.reasoning[:80]}...")
    
    db.update_agent_last_run(agent_id, datetime.utcnow())
    print(f"  Cycle complete. Published {published_count} posts.")


async def initialize_agent(persona_name: str, persona_domain: str) -> str:
    from agent.models.schemas import Agent
    import uuid
    
    agent = Agent(
        id=str(uuid.uuid4()),
        persona_name=persona_name,
        persona_domain=persona_domain,
    )
    db.create_agent(agent)
    return agent.id


async def run_scheduled_cycle():
    """Wrapper that finds the active agent and runs the publishing cycle."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT id FROM agents ORDER BY created_at DESC LIMIT 1").fetchone()
    if row:
        await run_publishing_cycle(row["id"])
    else:
        print("No agent found, skipping cycle")