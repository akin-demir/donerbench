from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from donerbench.agents import list_agents
from donerbench.benchmark import run_benchmark
from donerbench.benchmark.jobs import job_manager
from donerbench.schemas import (
    AgentInfo,
    BenchmarkJobStart,
    BenchmarkJobStatus,
    BenchmarkRequest,
    BenchmarkResult,
)

app = FastAPI(title="DönerBench API", version="0.1.0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("donerbench.api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/agents", response_model=list[AgentInfo])
def agents() -> list[AgentInfo]:
    return list_agents()


@app.post("/api/benchmark/run", response_model=BenchmarkResult)
def benchmark(request: BenchmarkRequest) -> BenchmarkResult:
    try:
        return run_benchmark(request)
    except ValueError as exc:
        logger.exception("Benchmark request failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/benchmark/jobs", response_model=BenchmarkJobStart)
def start_benchmark_job(request: BenchmarkRequest) -> BenchmarkJobStart:
    return job_manager.start(request)


@app.get("/api/benchmark/jobs/{job_id}", response_model=BenchmarkJobStatus)
def benchmark_job_status(job_id: str) -> BenchmarkJobStatus:
    status = job_manager.status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Benchmark job not found")
    return status
