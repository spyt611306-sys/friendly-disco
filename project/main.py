# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
from contextlib import closing, suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from psycopg2.extras import Json, RealDictCursor

from collector import (
    AwardCollector,
    BidCollector,
    ContractCollector,
    IncheonPortCollector,
    OrderPlanCollector,
    PrespecCollector,
    PublicDataCollector,
    ShipOperationCollector,
    ShipSupportCollector,
    UserInfoCollector,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sdi-backend")

app = FastAPI(
    title="ABB SDI API Server",
    description="실제 공공 OpenAPI 기반 조선/선박 관련 프로젝트 수집 서버",
    version="2.0.0",
)

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "https://marinesales.netlify.app,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def new_collect_job() -> Dict[str, Any]:
    return {
        "running": False,
        "jobId": None,
        "mode": None,
        "collectorAlias": None,
        "status": "IDLE",
        "currentStep": None,
        "savedCount": 0,
        "rawCount": 0,
        "message": None,
        "error": None,
        "startedAt": None,
        "finishedAt": None,
        "lastCollectedAt": None,
    }


COLLECT_JOB: Dict[str, Any] = new_collect_job()
COLLECT_TASK: Optional[asyncio.Task] = None
COLLECT_TASK_TIMEOUT_SECONDS = int(os.getenv("COLLECT_TASK_TIMEOUT_SECONDS", "180"))


def start_collect_job(mode: str, collector_alias: Optional[str] = None) -> Dict[str, Any]:
    global COLLECT_JOB
    COLLECT_JOB = {
        **new_collect_job(),
        "running": True,
        "jobId": str(uuid4()),
        "mode": mode,
        "collectorAlias": collector_alias,
        "status": "RUNNING",
        "message": "수집 작업을 시작했습니다.",
        "startedAt": utc_now_iso(),
    }
    return COLLECT_JOB


def finish_collect_job(status: str, message: str, error: Optional[str] = None, current_step: Optional[str] = None) -> None:
    global COLLECT_TASK
    COLLECT_JOB["running"] = False
    COLLECT_JOB["status"] = status
    COLLECT_JOB["message"] = message
    COLLECT_JOB["error"] = error
    COLLECT_JOB["currentStep"] = current_step
    COLLECT_JOB["finishedAt"] = utc_now_iso()
    COLLECT_TASK = None


def reset_collect_job_state() -> None:
    global COLLECT_JOB, COLLECT_TASK
    COLLECT_JOB = new_collect_job()
    COLLECT_TASK = None


def get_db_connection():
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


def ensure_tables() -> None:
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    dedupe_key TEXT PRIMARY KEY,
                    id TEXT NOT NULL,
                    name TEXT,
                    company TEXT,
                    announcement_no TEXT,
                    contract_no TEXT,
                    project_no TEXT,
                    region TEXT,
                    order_value TEXT,
                    currency TEXT,
                    registered_at TEXT,
                    contract_date TEXT,
                    delivery_date TEXT,
                    shipyard TEXT,
                    source_type TEXT,
                    source_service TEXT,
                    source_operation TEXT,
                    verification_status TEXT,
                    matched_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
                    keyword_text TEXT,
                    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    history JSONB NOT NULL DEFAULT '[]'::jsonb,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS collector_run_logs (
                    id TEXT PRIMARY KEY,
                    collector_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    collected_count INTEGER NOT NULL DEFAULT 0,
                    response_ms NUMERIC NOT NULL DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            conn.commit()


def make_registry() -> Dict[str, Any]:
    return {
        "bid": BidCollector(),
        "contract": ContractCollector(),
        "award": AwardCollector(),
        "order_plan": OrderPlanCollector(),
        "prespec": PrespecCollector(),
        "public_data": PublicDataCollector(),
        "ship_support": ShipSupportCollector(),
        "ship_operation": ShipOperationCollector(),
        "user_info": UserInfoCollector(),
        "incheon_port": IncheonPortCollector(),
    }


def dedupe_projects(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for project in projects:
        key = project["dedupeKey"]
        if key not in best:
            best[key] = project
            continue
        current_score = sum(1 for v in best[key].values() if v not in (None, "", [], {}))
        new_score = sum(1 for v in project.values() if v not in (None, "", [], {}))
        if new_score > current_score:
            best[key] = project
    return list(best.values())


def save_projects(projects: List[Dict[str, Any]]) -> None:
    if not projects:
        return
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            for project in projects:
                cur.execute(
                    """
                    INSERT INTO projects (
                        dedupe_key, id, name, company, announcement_no, contract_no, project_no,
                        region, order_value, currency, registered_at, contract_date, delivery_date,
                        shipyard, source_type, source_service, source_operation, verification_status,
                        matched_keywords, keyword_text, raw_payload, history, sources, updated_at
                    ) VALUES (
                        %(dedupe_key)s, %(id)s, %(name)s, %(company)s, %(announcement_no)s, %(contract_no)s,
                        %(project_no)s, %(region)s, %(order_value)s, %(currency)s, %(registered_at)s,
                        %(contract_date)s, %(delivery_date)s, %(shipyard)s, %(source_type)s,
                        %(source_service)s, %(source_operation)s, %(verification_status)s,
                        %(matched_keywords)s, %(keyword_text)s, %(raw_payload)s, %(history)s, %(sources)s, NOW()
                    )
                    ON CONFLICT (dedupe_key) DO UPDATE SET
                        name = EXCLUDED.name,
                        company = EXCLUDED.company,
                        announcement_no = EXCLUDED.announcement_no,
                        contract_no = EXCLUDED.contract_no,
                        project_no = EXCLUDED.project_no,
                        region = EXCLUDED.region,
                        order_value = EXCLUDED.order_value,
                        currency = EXCLUDED.currency,
                        registered_at = EXCLUDED.registered_at,
                        contract_date = EXCLUDED.contract_date,
                        delivery_date = EXCLUDED.delivery_date,
                        shipyard = EXCLUDED.shipyard,
                        source_type = EXCLUDED.source_type,
                        source_service = EXCLUDED.source_service,
                        source_operation = EXCLUDED.source_operation,
                        verification_status = EXCLUDED.verification_status,
                        matched_keywords = EXCLUDED.matched_keywords,
                        keyword_text = EXCLUDED.keyword_text,
                        raw_payload = EXCLUDED.raw_payload,
                        history = EXCLUDED.history,
                        sources = EXCLUDED.sources,
                        updated_at = NOW();
                    """,
                    {
                        "dedupe_key": project["dedupeKey"],
                        "id": project["id"],
                        "name": project.get("name"),
                        "company": project.get("company"),
                        "announcement_no": project.get("announcementNo"),
                        "contract_no": project.get("contractNo"),
                        "project_no": project.get("projectNo"),
                        "region": project.get("region"),
                        "order_value": project.get("orderValue"),
                        "currency": project.get("currency"),
                        "registered_at": project.get("registeredAt"),
                        "contract_date": project.get("contractDate"),
                        "delivery_date": project.get("deliveryDate"),
                        "shipyard": project.get("shipyard"),
                        "source_type": project.get("sourceType"),
                        "source_service": project.get("sourceService"),
                        "source_operation": project.get("sourceOperation"),
                        "verification_status": project.get("verificationStatus"),
                        "matched_keywords": Json(project.get("matchedKeywords", [])),
                        "keyword_text": project.get("keywordText"),
                        "raw_payload": Json(project.get("rawPayload", {})),
                        "history": Json(project.get("history", [])),
                        "sources": Json(project.get("sources", [])),
                    },
                )
            conn.commit()


def write_run_log(collector_name: str, status: str, collected_count: int, response_ms: float, error_message: Optional[str] = None) -> None:
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collector_run_logs (id, collector_name, status, collected_count, response_ms, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (str(uuid4()), collector_name, status, collected_count, response_ms, error_message),
                )
                conn.commit()
    except Exception as exc:
        logger.exception("collector log 저장 실패: %s", str(exc))


def row_to_project(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row.get("name") or "이름없음",
        "company": row.get("company") or "-",
        "announcementNo": row.get("announcement_no"),
        "contractNo": row.get("contract_no"),
        "projectNo": row.get("project_no"),
        "region": row.get("region"),
        "orderValue": row.get("order_value"),
        "currency": row.get("currency") or "KRW",
        "registeredAt": row.get("registered_at"),
        "contractDate": row.get("contract_date"),
        "deliveryDate": row.get("delivery_date"),
        "shipyard": row.get("shipyard"),
        "sourceType": row.get("source_type"),
        "sourceService": row.get("source_service"),
        "sourceOperation": row.get("source_operation"),
        "verificationStatus": row.get("verification_status") or "COLLECTED",
        "matchedKeywords": row.get("matched_keywords") or [],
        "keywordText": row.get("keyword_text") or "",
        "rawPayload": row.get("raw_payload") or {},
        "history": row.get("history") or [],
        "sources": row.get("sources") or [],
    }


def fetch_projects_from_db(q: str = "") -> Dict[str, Any]:
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor() as cur:
                if q:
                    like_q = f"%{q}%"
                    cur.execute(
                        """
                        SELECT *
                        FROM projects
                        WHERE COALESCE(name,'') ILIKE %s
                           OR COALESCE(company,'') ILIKE %s
                           OR COALESCE(announcement_no,'') ILIKE %s
                           OR COALESCE(project_no,'') ILIKE %s
                           OR COALESCE(region,'') ILIKE %s
                           OR COALESCE(keyword_text,'') ILIKE %s
                           OR COALESCE(order_value,'') ILIKE %s
                           OR COALESCE(registered_at,'') ILIKE %s
                        ORDER BY updated_at DESC
                        """,
                        (like_q, like_q, like_q, like_q, like_q, like_q, like_q, like_q),
                    )
                else:
                    cur.execute("SELECT * FROM projects ORDER BY updated_at DESC")
                rows = cur.fetchall()
                last_collected_at = None
                cur.execute("SELECT created_at FROM collector_run_logs ORDER BY created_at DESC LIMIT 1")
                log_row = cur.fetchone()
                if log_row:
                    last_collected_at = str(log_row["created_at"])
                return {
                    "projects": [row_to_project(row) for row in rows],
                    "lastCollectedAt": last_collected_at,
                }
    except Exception as exc:
        logger.exception("프로젝트 조회 실패: %s", str(exc))
        return {"projects": [], "lastCollectedAt": None}


async def execute_single_collector(alias: str, collector: Any, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    started = datetime.utcnow()
    try:
        projects = await collector.collect(seed_projects=seed_projects)
        elapsed = (datetime.utcnow() - started).total_seconds() * 1000
        write_run_log(alias, "SUCCESS", len(projects), elapsed)
        return projects
    except Exception as exc:
        elapsed = (datetime.utcnow() - started).total_seconds() * 1000
        write_run_log(alias, "FAILED", 0, elapsed, str(exc))
        logger.exception("collector 실패 alias=%s error=%s", alias, str(exc))
        return []


async def execute_pipeline() -> Dict[str, Any]:
    registry = make_registry()
    all_projects: List[Dict[str, Any]] = []

    ordered_aliases = [
        "bid",
        "contract",
        "award",
        "order_plan",
        "prespec",
        "public_data",
        "ship_support",
        "ship_operation",
    ]

    for alias in ordered_aliases:
        collector = registry[alias]
        seed_input = all_projects if alias in {"ship_support", "ship_operation"} else None
        projects = await execute_single_collector(alias, collector, seed_input)
        all_projects.extend(projects)

    deduped = dedupe_projects(all_projects)
    save_projects(deduped)
    return {
        "status": "SUCCESS",
        "message": f"수집 완료: 원본 {len(all_projects)}건 / 중복제거 후 {len(deduped)}건",
        "rawCount": len(all_projects),
        "savedCount": len(deduped),
    }


async def execute_pipeline_in_background(job_id: str) -> None:
    registry = make_registry()
    all_projects: List[Dict[str, Any]] = []
    processed_count = 0

    ordered_aliases = [
        "bid",
        "contract",
        "award",
        "order_plan",
        "prespec",
        "public_data",
        "ship_support",
        "ship_operation",
    ]

    try:
        for alias in ordered_aliases:
            if COLLECT_JOB.get("jobId") != job_id:
                return

            COLLECT_JOB["currentStep"] = alias
            COLLECT_JOB["message"] = f"{alias} 수집 중"

            collector = registry[alias]
            seed_input = all_projects if alias in {"ship_support", "ship_operation"} else None
            try:
                projects = await asyncio.wait_for(
                    execute_single_collector(alias, collector, seed_input),
                    timeout=COLLECT_TASK_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                raise RuntimeError(f"{alias} 수집이 {COLLECT_TASK_TIMEOUT_SECONDS}초를 초과하여 중단되었습니다.")
            all_projects.extend(projects)

            per_collector_deduped = dedupe_projects(projects)
            if per_collector_deduped:
                save_projects(per_collector_deduped)
                processed_count += len(per_collector_deduped)

            COLLECT_JOB["rawCount"] = len(all_projects)
            COLLECT_JOB["savedCount"] = processed_count
            COLLECT_JOB["message"] = f"{alias} 완료: 원본 {len(projects)}건 / 임시 저장 {len(per_collector_deduped)}건"

        overall_deduped = dedupe_projects(all_projects)
        if overall_deduped:
            save_projects(overall_deduped)

        snapshot = fetch_projects_from_db()
        COLLECT_JOB["savedCount"] = len(snapshot.get("projects", []))
        COLLECT_JOB["lastCollectedAt"] = snapshot.get("lastCollectedAt")
        finish_collect_job(
            status="SUCCESS",
            message=f"수집 완료: 원본 {len(all_projects)}건 / 최종 저장 {len(overall_deduped)}건",
        )
    except asyncio.CancelledError:
        logger.warning("백그라운드 수집이 취소되었습니다. job_id=%s", job_id)
        finish_collect_job(status="CANCELLED", message="수집 작업이 취소되었습니다.")
        raise
    except Exception as exc:
        logger.exception("백그라운드 수집 실패: %s", str(exc))
        finish_collect_job(status="FAILED", message="수집 작업이 실패했습니다.", error=str(exc))


async def execute_single_collector_in_background(job_id: str, collector_alias: str) -> None:
    registry = make_registry()
    collector = registry[collector_alias]

    try:
        COLLECT_JOB["currentStep"] = collector_alias
        COLLECT_JOB["message"] = f"{collector_alias} 수집 중"

        seed_projects = None
        if collector_alias in {"ship_support", "ship_operation"}:
            seed_projects = fetch_projects_from_db().get("projects", [])

        try:
            projects = await asyncio.wait_for(
                execute_single_collector(collector_alias, collector, seed_projects),
                timeout=COLLECT_TASK_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"{collector_alias} 수집이 {COLLECT_TASK_TIMEOUT_SECONDS}초를 초과하여 중단되었습니다.")

        deduped = dedupe_projects(projects)
        if deduped:
            save_projects(deduped)

        snapshot = fetch_projects_from_db()
        COLLECT_JOB["rawCount"] = len(projects)
        COLLECT_JOB["savedCount"] = len(snapshot.get("projects", []))
        COLLECT_JOB["lastCollectedAt"] = snapshot.get("lastCollectedAt")
        finish_collect_job(
            status="SUCCESS",
            message=f"{collector_alias} 완료: 원본 {len(projects)}건 / 저장 {len(deduped)}건",
        )
    except asyncio.CancelledError:
        logger.warning("단일 collector 수집이 취소되었습니다. alias=%s job_id=%s", collector_alias, job_id)
        finish_collect_job(status="CANCELLED", message=f"{collector_alias} 수집이 취소되었습니다.")
        raise
    except Exception as exc:
        logger.exception("단일 collector 백그라운드 수집 실패 alias=%s error=%s", collector_alias, str(exc))
        finish_collect_job(status="FAILED", message=f"{collector_alias} 수집 실패", error=str(exc))


@app.on_event("startup")
def startup_event() -> None:
    ensure_tables()
    logger.info("SDI backend started")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_FILE)


@app.get("/api/projects")
def get_projects(q: str = Query(default="")) -> Dict[str, Any]:
    return fetch_projects_from_db(q=q)


@app.get("/api/meta/apis")
def get_api_meta() -> Dict[str, Any]:
    registry = make_registry()
    return {
        alias: {
            "collector": collector.name,
            "baseUrl": collector.base_url,
            "sourceType": collector.source_type,
            "operations": list(collector.operations.keys()),
        }
        for alias, collector in registry.items()
    }


@app.get("/api/collect/status")
def collect_status() -> Dict[str, Any]:
    return COLLECT_JOB


@app.post("/api/collect/reset")
async def collect_reset() -> Dict[str, Any]:
    global COLLECT_TASK

    if COLLECT_TASK and not COLLECT_TASK.done():
        COLLECT_TASK.cancel()
        with suppress(asyncio.CancelledError):
            await COLLECT_TASK

    reset_collect_job_state()
    return {
        "status": "RESET",
        "message": "수집 상태를 초기화했습니다.",
    }


@app.post("/api/collect")
async def collect_all() -> Dict[str, Any]:
    global COLLECT_TASK

    if COLLECT_JOB.get("running"):
        return {
            "status": "RUNNING",
            "jobId": COLLECT_JOB.get("jobId"),
            "message": "이미 수집 작업이 실행 중입니다.",
        }

    job = start_collect_job(mode="ALL")
    COLLECT_TASK = asyncio.create_task(execute_pipeline_in_background(job["jobId"]))
    return {
        "status": "STARTED",
        "jobId": job["jobId"],
        "message": "백그라운드 수집을 시작했습니다.",
    }


@app.post("/api/collect/{collector_alias}")
async def collect_one(collector_alias: str) -> Dict[str, Any]:
    global COLLECT_TASK

    registry = make_registry()
    if collector_alias not in registry:
        raise HTTPException(status_code=404, detail="collector not found")

    if COLLECT_JOB.get("running"):
        return {
            "status": "RUNNING",
            "jobId": COLLECT_JOB.get("jobId"),
            "message": "이미 다른 수집 작업이 실행 중입니다.",
        }

    job = start_collect_job(mode="SINGLE", collector_alias=collector_alias)
    COLLECT_TASK = asyncio.create_task(execute_single_collector_in_background(job["jobId"], collector_alias))
    return {
        "status": "STARTED",
        "jobId": job["jobId"],
        "message": f"{collector_alias} 백그라운드 수집을 시작했습니다.",
    }


@app.get("/api/run-operation/{collector_alias}/{operation_name}")
async def run_operation(collector_alias: str, operation_name: str, request: Request) -> Dict[str, Any]:
    registry = make_registry()
    collector = registry.get(collector_alias)
    if collector is None:
        raise HTTPException(status_code=404, detail="collector not found")
    if operation_name not in collector.operations:
        raise HTTPException(status_code=404, detail="operation not found")
    params = dict(request.query_params)
    result = await collector.request_operation(operation_name, params)
    return {
        "collector": collector_alias,
        "operation": operation_name,
        "header": result["header"],
        "body": result["body"],
        "count": len(result["items"]),
        "elapsedMs": result["elapsed_ms"],
        "items": result["items"],
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_fallback(full_path: str) -> FileResponse:
    reserved_prefixes = ("api", "docs", "redoc", "openapi.json", "health")
    if full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(INDEX_FILE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
