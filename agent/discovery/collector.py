import httpx
import feedparser
import asyncio
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime
import re

from agent.config import settings, DISCOVERY_SOURCES
from agent.models.schemas import Topic


class TopicCollector:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ML-Agent/1.0)"},
        )

    async def close(self):
        await self.client.aclose()

    async def collect_all(self, agent_id: str, existing_hashes: set) -> List[Topic]:
        all_topics = []
        
        tasks = [
            self._collect_from_source(source, agent_id, existing_hashes)
            for source in DISCOVERY_SOURCES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            if isinstance(result, list):
                all_topics.extend(result)
        
        all_topics.sort(key=lambda t: t.discovered_at, reverse=True)
        return all_topics[: settings.max_topics_per_run]

    async def _collect_from_source(
        self, source: Dict[str, Any], agent_id: str, existing_hashes: set
    ) -> List[Topic]:
        try:
            if source["type"] == "rss":
                return await self._collect_rss(source, agent_id, existing_hashes)
            elif source["type"] == "hn_api":
                return await self._collect_hn_api(source, agent_id, existing_hashes)
            elif source["type"] == "github_trending":
                return await self._collect_github_trending(source, agent_id, existing_hashes)
            elif source["type"] == "pwc_html":
                return await self._collect_pwc(source, agent_id, existing_hashes)
        except Exception as e:
            print(f"Error collecting from {source['name']}: {e}")
        return []

    async def _collect_rss(
        self, source: Dict[str, Any], agent_id: str, existing_hashes: set
    ) -> List[Topic]:
        response = await self.client.get(source["url"])
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        
        topics = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            
            content_hash = Topic.create_hash(title, url)
            if content_hash in existing_hashes:
                continue
            
            summary = self._clean_html(summary)[:500]
            
            topics.append(
                Topic(
                    agent_id=agent_id,
                    title=title,
                    url=url,
                    source=source["name"],
                    source_category=source["category"],
                    summary=summary,
                    content_hash=content_hash,
                )
            )
        return topics

    async def _collect_hn_api(
        self, source: Dict[str, Any], agent_id: str, existing_hashes: set
    ) -> List[Topic]:
        response = await self.client.get(source["url"])
        response.raise_for_status()
        data = response.json()
        
        topics = []
        for hit in data.get("hits", [])[:20]:
            title = hit.get("title", "").strip()
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            summary = hit.get("story_text", "").strip() or f"HN Discussion: {hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments"
            
            content_hash = Topic.create_hash(title, url)
            if content_hash in existing_hashes:
                continue
            
            summary = self._clean_html(summary)[:500]
            
            topics.append(
                Topic(
                    agent_id=agent_id,
                    title=title,
                    url=url,
                    source=source["name"],
                    source_category=source["category"],
                    summary=summary,
                    content_hash=content_hash,
                )
            )
        return topics

    async def _collect_github_trending(
        self, source: Dict[str, Any], agent_id: str, existing_hashes: set
    ) -> List[Topic]:
        response = await self.client.get(source["url"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        topics = []
        for article in soup.select("article.Box-row")[:15]:
            title_elem = article.select_one("h2 a")
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            url = "https://github.com" + title_elem.get("href", "")
            desc_elem = article.select_one("p")
            summary = desc_elem.get_text(strip=True) if desc_elem else ""
            
            content_hash = Topic.create_hash(title, url)
            if content_hash in existing_hashes:
                continue
            
            topics.append(
                Topic(
                    agent_id=agent_id,
                    title=f"GitHub Trending: {title}",
                    url=url,
                    source=source["name"],
                    source_category=source["category"],
                    summary=summary[:500],
                    content_hash=content_hash,
                )
            )
        return topics

    async def _collect_pwc(
        self, source: Dict[str, Any], agent_id: str, existing_hashes: set
    ) -> List[Topic]:
        response = await self.client.get(source["url"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        topics = []
        for item in soup.select(".infinite-item .paper-item")[:15]:
            title_elem = item.select_one("h3 a, h1 a")
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            url = "https://paperswithcode.com" + title_elem.get("href", "")
            summary_elem = item.select_one(".paper-abstract, .abstract")
            summary = summary_elem.get_text(strip=True) if summary_elem else ""
            
            content_hash = Topic.create_hash(title, url)
            if content_hash in existing_hashes:
                continue
            
            topics.append(
                Topic(
                    agent_id=agent_id,
                    title=f"Papers With Code: {title}",
                    url=url,
                    source=source["name"],
                    source_category=source["category"],
                    summary=summary[:500],
                    content_hash=content_hash,
                )
            )
        return topics

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
        text = re.sub(r"\s+", " ", text).strip()
        return text


async def discover_topics(agent_id: str, existing_hashes: set) -> List[Topic]:
    collector = TopicCollector()
    try:
        return await collector.collect_all(agent_id, existing_hashes)
    finally:
        await collector.close()