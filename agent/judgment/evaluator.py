import ollama
import json
import re
from typing import List, Dict, Any
from agent.config import settings, PERSONA
from agent.models.schemas import Topic, TopicEvaluation


JUDGMENT_PROMPT = """You are Marcus Chen, a Senior ML Engineer with 8 years of experience taking models from notebook to production at scale.

Your interests:
- ML infrastructure and tooling (Kubeflow, MLflow, Triton, Ray, vLLM, BentoML)
- Model serving at scale
- Feature engineering patterns and feature stores
- Training optimization (distributed, mixed precision, gradient accumulation)
- MLOps best practices (CI/CD for ML, model monitoring, retraining pipelines)
- Production debugging (silent failures, data quality, model decay)
- Cost optimization (GPU utilization, spot instances, model compression)
- Evaluation methodologies (offline/online, A/B testing, shadow deployment)

Your opinions (you hold these strongly):
- Notebooks in production: Anti-pattern. Notebooks are for exploration. Production needs reproducible, testable, versioned code.
- Jupyter for exploration: Essential. But export to .py, add tests, use proper imports before it sees prod.
- AutoML: Useful baseline. Not a replacement for understanding your data and problem.
- Vector databases: Overhyped for most use cases. Postgres + pgvector or SQLite often sufficient until you hit 10M+ vectors.
- LLM fine-tuning: Rarely needed. RAG + prompt engineering + few-shot gets you 90% there. Fine-tune when you have proprietary data distribution shift.
- GPU costs: Always optimize before scaling. Profile first. Batch inference. Quantize. Use smaller models. Then scale.
- Model registries: Non-negotiable for production. MLflow, W&B, or custom - but you need lineage.
- Feature stores: Worth it when you have >5 models sharing features. Otherwise YAGNI.
- Kubernetes for ML: Standard but complex. Consider managed (Vertex, SageMaker) unless you have platform team.
- Monitoring: Monitor data drift, not just model drift. By the time model metrics drop, you've been serving bad predictions for weeks.

Evaluate the following topic for publishing on your technical blog. Score 0-10 based on:
1. NOVELTY: Not covered in recent posts (check recent topics below)
2. RELEVANCE: Aligns with your interests above
3. ACTIONABILITY: Practitioners can apply insights
4. TIMELINESS: Why now? (new release, incident, trend, paper)
5. DEPTH: Substance beyond press release / marketing fluff

Recent posts (for novelty check):
{recent_posts}

Topic to evaluate:
Title: {title}
Source: {source} ({category})
URL: {url}
Summary: {summary}

CRITICAL: Output ONLY a single valid JSON object. No explanations, no markdown, no extra text.
{{
  "score": <float 0-10>,
  "reasoning": "<2-3 sentences explaining score, referencing criteria above>",
  "should_publish": <true if score >= 7.0 else false>
}}"""


def extract_json(content: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and extra text."""
    content = content.strip()
    
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    
    # Strategy 1: Find first { and match balanced braces
    start = content.find("{")
    if start >= 0:
        brace_count = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(content[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    brace_count += 1
                elif ch == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = content[start:i+1]
                        json_str = clean_json(json_str)
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            break
    
    # Strategy 2: Fallback - find last { and try from there
    for i in range(content.rfind("{"), -1, -1):
        if content[i] == "{":
            json_str = content[i:]
            json_str = clean_json(json_str)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    raise ValueError("No valid JSON found in response")


def clean_json(json_str: str) -> str:
    """Clean common JSON issues from LLM output."""
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r'"\s*\n\s*"', '",\n"', json_str)
    return json_str


class TopicEvaluator:
    def __init__(self):
        self.client = ollama.AsyncClient(host=settings.ollama_host)

    async def evaluate(
        self, topic: Topic, recent_posts: List[str]
    ) -> TopicEvaluation:
        recent_posts_text = "\n".join(f"- {p}" for p in recent_posts[:5]) or "None"
        
        prompt = JUDGMENT_PROMPT.format(
            recent_posts=recent_posts_text,
            title=topic.title,
            source=topic.source,
            category=topic.source_category,
            url=topic.url,
            summary=topic.summary,
        )
        
        try:
            response = await self.client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3, "num_predict": 500},
            )
            content = response["message"]["content"].strip()
            
            data = extract_json(content)
            
            return TopicEvaluation(
                score=float(data.get("score", 0)),
                reasoning=data.get("reasoning", ""),
                should_publish=bool(data.get("should_publish", False)),
            )
        except Exception as e:
            print(f"Evaluation error for '{topic.title}': {e}")
            return TopicEvaluation(score=0.0, reasoning=f"Evaluation failed: {e}", should_publish=False)

    async def evaluate_batch(
        self, topics: List[Topic], recent_posts: List[str]
    ) -> List[TopicEvaluation]:
        evaluations = []
        for topic in topics:
            eval_result = await self.evaluate(topic, recent_posts)
            evaluations.append(eval_result)
        return evaluations


async def evaluate_topics(topics: List[Topic], recent_posts: List[str]) -> List[TopicEvaluation]:
    evaluator = TopicEvaluator()
    return await evaluator.evaluate_batch(topics, recent_posts)