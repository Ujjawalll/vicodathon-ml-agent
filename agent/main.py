from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import uvicorn

from agent.config import settings
from agent.api.routes import router
from agent.scheduler.runner import run_publishing_cycle, run_scheduled_cycle


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting ML Engineer Agent on port 8000")
    print(f"Scheduler interval: {settings.scheduler_interval_hours} hours")
    print(f"Ollama: {settings.ollama_host} (model: {settings.ollama_model})")
    
    # Add the publishing job
    scheduler.add_job(
        run_scheduled_cycle,
        trigger=IntervalTrigger(hours=settings.scheduler_interval_hours),
        id="publishing_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print("Scheduler started")
    
    yield
    
    # Shutdown
    scheduler.shutdown()
    print("Scheduler stopped")


app = FastAPI(
    title="Autonomous ML Engineer Agent",
    description="An autonomous AI agent that discovers, evaluates, and publishes ML engineering content",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "next_run": str(scheduler.get_job("publishing_cycle").next_run_time) if scheduler.get_job("publishing_cycle") else None,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)