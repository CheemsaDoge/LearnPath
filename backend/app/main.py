from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.me import router as me_router
from app.api.routes import router
from app.config import get_settings
from app.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("learnpath")


def recover_interrupted_graphs() -> None:
    """A restart kills background pipelines; finish grounding-complete graphs and mark the rest failed (retryable)."""
    from app.db import session_factory
    from app.models import Graph

    db = session_factory()()
    try:
        for graph in db.query(Graph).filter(Graph.status.in_(["generating", "grounding"])).all():
            pending = [n for n in graph.nodes if n.grounding_status == "pending"]
            if graph.status == "grounding" and graph.nodes and not pending:
                graph.status = "ready"
                graph.progress = {"step": "ready", "done": 1, "total": 1}
            elif graph.status == "grounding" and graph.nodes:
                for node in pending:
                    node.grounding_status = "failed"
                graph.status = "ready"
                graph.progress = {"step": "ready", "done": 1, "total": 1}
                log.warning("graph %s: grounding interrupted by restart; %d nodes left without sources", graph.id, len(pending))
            else:
                graph.status = "failed"
                graph.error = "生成过程被服务重启中断，请点击「重试」。"
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recover_interrupted_graphs()
    settings = get_settings()
    log.info("LearnPath backend ready · llm=%s · search=%s · reader=%s", settings.resolved_llm_provider, settings.search_backend_list, settings.reader_base)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="知径 LearnPath API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(me_router)

    dist = Path(settings.frontend_dist)
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
