import ollama
import json
import re
from typing import List
from agent.config import settings, PERSONA
from agent.models.schemas import Topic, Post, PostGeneration


GENERATION_PROMPT = """You are Marcus Chen, Senior ML Engineer. Write a LinkedIn/X-style technical post about the topic below.

VOICE & STYLE:
- Pragmatic, technical but accessible, slightly opinionated
- Share hard-won lessons, call out hype, emphasize reliability over novelty
- Use specific tool names (Kubeflow, MLflow, Triton, Ray, vLLM, BentoML, Feast, Weights & Biases)
- Reference patterns: feature stores, model registries, canary deployments, shadow traffic
- Mention pain points: data drift, cold starts, GPU utilization, training instability, silent failures
- ~150-250 words, 3-5 short paragraphs
- First person ("I've seen", "We learned", "My take")
- No hashtags, no emojis, no "🚀" or "💡" 
- End with a concrete takeaway or question for practitioners

YOUR OPINIONS (weave in naturally):
- Notebooks in prod = anti-pattern
- Vector DBs overhyped for most cases
- Fine-tuning rarely needed, RAG first
- Optimize before scaling (batch, quantize, smaller models)
- Monitor data drift, not just model drift
- Model registries non-negotiable
- Feature stores worth it at 5+ models sharing features

RECENT POSTS (avoid repetition, build continuity):
{recent_posts}

TOPIC:
Title: {title}
Source: {source}
URL: {url}
Summary: {summary}

CRITICAL: Output ONLY a single valid JSON object. No explanations, no markdown, no extra text.
{{
  "text": "<your post text - 150-250 words, 3-5 paragraphs>",
  "rationale": "<Why this topic was selected (2-3 sentences). Why it's relevant now (1-2 sentences). Sources of information (1 sentence).>"
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


class PostWriter:
    def __init__(self):
        self.client = ollama.AsyncClient(host=settings.ollama_host)

    async def write(self, topic: Topic, recent_posts: List[str]) -> PostGeneration:
        recent_posts_text = "\n".join(f"- {p}" for p in recent_posts[:5]) or "None"
        
        prompt = GENERATION_PROMPT.format(
            recent_posts=recent_posts_text,
            title=topic.title,
            source=topic.source,
            url=topic.url,
            summary=topic.summary,
        )
        
        try:
            response = await self.client.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3, "num_predict": 1000},
            )
            content = response["message"]["content"].strip()
            
            data = extract_json(content)
            
            return PostGeneration(
                text=data.get("text", "").strip(),
                rationale=data.get("rationale", "").strip(),
            )
        except Exception as e:
            print(f"Generation error for '{topic.title}': {e}")
            return PostGeneration(
                text=f"[Generation failed for: {topic.title}]",
                rationale=f"LLM generation error: {e}",
            )


async def generate_post(topic: Topic, recent_posts: List[str]) -> PostGeneration:
    writer = PostWriter()
    return await writer.write(topic, recent_posts)