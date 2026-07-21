# -*- coding: utf-8 -*-
"""Ship Delivery Intelligence API.

공공 OpenAPI/RSS 수집, 프로젝트 병합, 영업 팔로업 저장, 정적 대시보드 제공을
한 프로세스에서 담당한다. 공개 조회와 관리자 변경 API를 명확히 분리한다.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager, closing, suppress
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

import psycopg2
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from psycopg2.extras import Json, RealDictCursor
from pydantic import BaseModel, Field

from collector import (
    AwardCollector,
    BidCollector,
    ContractCollector,
    IncheonPortCollector,
    NewsCollector,
    OrderPlanCollector,
    PrespecCollector,
    PublicDataCollector,
    PublicNoticeCollector,
    ShipOperationCollector,
    ShipSupportCollector,
    UserInfoCollector,
)

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("sdi.api")

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
STYLES_FILE = BASE_DIR / "styles.css"
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
STRICT_STARTUP = os.getenv("STRICT_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}
COLLECTOR_TIMEOUT_SECONDS = max(
    30,
    int(os.getenv("COLLECTOR_TIMEOUT_SECONDS", os.getenv("COLLECT_TASK_TIMEOUT_SECONDS", "300"))),
)
DEFAULT_PIPELINE_ALIASES = [
    item.strip()
    for item in os.getenv(
        "DEFAULT_PIPELINE_ALIASES",
        "bid,contract,award,prespec,order_plan,public_data,news,public_notice,ship_support",
    ).split(",")
    if item.strip()
]

STAGES = ["LEAD", "PLAN", "PRESPEC", "BID", "EVALUATION", "CONTRACT", "BUILD", "DELIVERED"]
STAGE_RANK = {stage: index for index, stage in enumerate(STAGES)}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def env_origins() -> List[str]:
    defaults = (
        "https://marinesalesbyminsu.netlify.app,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )
    return [item.strip() for item in os.getenv("ALLOWED_ORIGINS", defaults).split(",") if item.strip()]


def new_collect_job() -> Dict[str, Any]:
    return {
        "running": False,
        "jobId": None,
        "mode": None,
        "collectorAlias": None,
        "status": "IDLE",
        "currentStep": None,
        "progress": 0,
        "savedCount": 0,
        "rawCount": 0,
        "message": None,
        "error": None,
        "errors": [],
        "startedAt": None,
        "finishedAt": None,
        "lastCollectedAt": None,
    }


COLLECT_JOB: Dict[str, Any] = new_collect_job()
COLLECT_TASK: Optional[asyncio.Task[Any]] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await asyncio.to_thread(ensure_tables)
        logger.info("데이터베이스 스키마 준비 완료")
    except Exception as exc:
        logger.error("데이터베이스 초기화 실패: %s", exc)
        if STRICT_STARTUP:
            raise
    yield
    if COLLECT_TASK and not COLLECT_TASK.done():
        COLLECT_TASK.cancel()
        with suppress(asyncio.CancelledError):
            await COLLECT_TASK


app = FastAPI(
    title="Ship Delivery Intelligence API",
    description="국내 관공선·특수선 조달/건조 프로젝트 수집 및 영업 팔로업 API",
    version="3.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=env_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Accept", "Content-Type", "X-Admin-Token"],
)


class FollowupUpdate(BaseModel):
    stage: Optional[str] = None
    owner: Optional[str] = Field(default=None, max_length=100)
    nextActionDate: Optional[str] = Field(default=None, max_length=10)
    nextAction: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=4000)
    favorite: Optional[bool] = None


def require_admin(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")) -> None:
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="서버에 ADMIN_API_KEY가 설정되지 않았습니다.")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_API_KEY):
        raise HTTPException(status_code=401, detail="관리자 키가 올바르지 않습니다.")


def get_db_connection():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    return psycopg2.connect(
        database_url,
        cursor_factory=RealDictCursor,
        connect_timeout=max(3, int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))),
        application_name="ship-delivery-intelligence",
    )


def ensure_tables() -> None:
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    dedupe_key TEXT PRIMARY KEY,
                    identity_key TEXT,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
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
                    stage TEXT NOT NULL DEFAULT 'LEAD',
                    source_type TEXT,
                    source_service TEXT,
                    source_operation TEXT,
                    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                    matched_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
                    keyword_text TEXT,
                    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    history JSONB NOT NULL DEFAULT '[]'::jsonb,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    owner TEXT,
                    next_action_date TEXT,
                    next_action TEXT,
                    notes TEXT,
                    favorite BOOLEAN NOT NULL DEFAULT FALSE,
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            migrations = {
                "identity_key": "TEXT",
                "stage": "TEXT NOT NULL DEFAULT 'LEAD'",
                "owner": "TEXT",
                "next_action_date": "TEXT",
                "next_action": "TEXT",
                "notes": "TEXT",
                "favorite": "BOOLEAN NOT NULL DEFAULT FALSE",
                "first_seen_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
                "last_seen_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            }
            for column, definition in migrations.items():
                cur.execute(f"ALTER TABLE projects ADD COLUMN IF NOT EXISTS {column} {definition}")
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
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_identity ON projects(identity_key)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_stage ON projects(stage)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_next_action ON projects(next_action_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_announcement ON projects(announcement_no)")
            conn.commit()


def make_registry() -> Dict[str, Any]:
    return {
        "bid": BidCollector(),
        "contract": ContractCollector(),
        "award": AwardCollector(),
        "prespec": PrespecCollector(),
        "order_plan": OrderPlanCollector(),
        "public_data": PublicDataCollector(),
        "news": NewsCollector(),
        "public_notice": PublicNoticeCollector(),
        "ship_support": ShipSupportCollector(),
        "ship_operation": ShipOperationCollector(),
        "user_info": UserInfoCollector(),
        "incheon_port": IncheonPortCollector(),
    }


def normalize_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())


def identity_key(project: Dict[str, Any]) -> str:
    title = normalize_key(project.get("name"))
    for term in ("입찰공고", "사전규격", "낙찰결과", "계약현황", "발주계획"):
        title = title.replace(normalize_key(term), "")
    company = normalize_key(project.get("company"))
    year = str(project.get("registeredAt") or "")[:4]
    digest = hashlib.sha256(f"{title[:180]}|{company[:80]}|{year}".encode("utf-8")).hexdigest()[:32]
    return f"IDENTITY:{digest}"


def merge_unique(items: Iterable[Dict[str, Any]], fields: Iterable[str]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = "|".join(str(item.get(field) or "") for field in fields) or json.dumps(item, ensure_ascii=False, sort_keys=True)
        previous = merged.get(key)
        if previous is None or len(json.dumps(item, ensure_ascii=False)) > len(json.dumps(previous, ensure_ascii=False)):
            merged[key] = item
    return list(merged.values())


def merge_projects(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(current)
    richer_fields = (
        "name", "company", "announcementNo", "contractNo", "projectNo", "region", "orderValue",
        "currency", "registeredAt", "contractDate", "deliveryDate", "shipyard", "sourceType",
        "sourceService", "sourceOperation", "verificationStatus",
    )
    for field in richer_fields:
        old, new = merged.get(field), incoming.get(field)
        if new not in (None, "", [], {}) and (old in (None, "", [], {}) or len(str(new)) > len(str(old))):
            merged[field] = new
    old_stage = str(merged.get("stage") or "LEAD").upper()
    new_stage = str(incoming.get("stage") or "LEAD").upper()
    merged["stage"] = new_stage if STAGE_RANK.get(new_stage, 0) >= STAGE_RANK.get(old_stage, 0) else old_stage
    merged["matchedKeywords"] = sorted(set((merged.get("matchedKeywords") or []) + (incoming.get("matchedKeywords") or [])))
    merged["keywordText"] = " ".join(merged["matchedKeywords"])
    merged["sources"] = merge_unique((merged.get("sources") or []) + (incoming.get("sources") or []), ("url", "title"))
    merged["history"] = merge_unique((merged.get("history") or []) + (incoming.get("history") or []), ("id", "date", "action"))
    merged["rawPayload"] = {**(merged.get("rawPayload") or {}), **(incoming.get("rawPayload") or {})}
    return merged


def dedupe_projects(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    aliases: Dict[str, str] = {}
    for project in projects:
        if not project or not project.get("name"):
            continue
        keys = [
            str(project.get("dedupeKey") or ""),
            *[f"ANN:{normalize_key(project.get(field))}" for field in ("announcementNo", "contractNo", "projectNo") if project.get(field)],
            identity_key(project),
        ]
        canonical = next((aliases[key] for key in keys if key and key in aliases), keys[0] or keys[-1])
        if canonical in merged:
            merged[canonical] = merge_projects(merged[canonical], project)
        else:
            merged[canonical] = dict(project)
            merged[canonical]["dedupeKey"] = canonical
        for key in keys:
            if key:
                aliases[key] = canonical
    return list(merged.values())


UPSERT_SQL = """
    INSERT INTO projects (
        dedupe_key, identity_key, id, name, company, announcement_no, contract_no, project_no,
        region, order_value, currency, registered_at, contract_date, delivery_date, shipyard, stage,
        source_type, source_service, source_operation, verification_status, matched_keywords,
        keyword_text, raw_payload, history, sources, last_seen_at, updated_at
    ) VALUES (
        %(dedupe_key)s, %(identity_key)s, %(id)s, %(name)s, %(company)s, %(announcement_no)s,
        %(contract_no)s, %(project_no)s, %(region)s, %(order_value)s, %(currency)s, %(registered_at)s,
        %(contract_date)s, %(delivery_date)s, %(shipyard)s, %(stage)s, %(source_type)s,
        %(source_service)s, %(source_operation)s, %(verification_status)s, %(matched_keywords)s,
        %(keyword_text)s, %(raw_payload)s, %(history)s, %(sources)s, NOW(), NOW()
    )
    ON CONFLICT (dedupe_key) DO UPDATE SET
        identity_key = COALESCE(NULLIF(EXCLUDED.identity_key, ''), projects.identity_key),
        name = COALESCE(NULLIF(EXCLUDED.name, ''), projects.name),
        company = COALESCE(NULLIF(EXCLUDED.company, ''), projects.company),
        announcement_no = COALESCE(NULLIF(EXCLUDED.announcement_no, ''), projects.announcement_no),
        contract_no = COALESCE(NULLIF(EXCLUDED.contract_no, ''), projects.contract_no),
        project_no = COALESCE(NULLIF(EXCLUDED.project_no, ''), projects.project_no),
        region = COALESCE(NULLIF(EXCLUDED.region, ''), projects.region),
        order_value = COALESCE(NULLIF(EXCLUDED.order_value, ''), projects.order_value),
        currency = COALESCE(NULLIF(EXCLUDED.currency, ''), projects.currency),
        registered_at = COALESCE(NULLIF(EXCLUDED.registered_at, ''), projects.registered_at),
        contract_date = COALESCE(NULLIF(EXCLUDED.contract_date, ''), projects.contract_date),
        delivery_date = COALESCE(NULLIF(EXCLUDED.delivery_date, ''), projects.delivery_date),
        shipyard = COALESCE(NULLIF(EXCLUDED.shipyard, ''), projects.shipyard),
        stage = CASE
            WHEN array_position(ARRAY['LEAD','PLAN','PRESPEC','BID','EVALUATION','CONTRACT','BUILD','DELIVERED'], EXCLUDED.stage)
               >= array_position(ARRAY['LEAD','PLAN','PRESPEC','BID','EVALUATION','CONTRACT','BUILD','DELIVERED'], projects.stage)
            THEN EXCLUDED.stage ELSE projects.stage END,
        source_type = COALESCE(NULLIF(EXCLUDED.source_type, ''), projects.source_type),
        source_service = COALESCE(NULLIF(EXCLUDED.source_service, ''), projects.source_service),
        source_operation = COALESCE(NULLIF(EXCLUDED.source_operation, ''), projects.source_operation),
        verification_status = CASE WHEN projects.verification_status = 'VERIFIED' THEN projects.verification_status ELSE EXCLUDED.verification_status END,
        matched_keywords = (
            SELECT COALESCE(jsonb_agg(value), '[]'::jsonb)
            FROM (SELECT DISTINCT value FROM jsonb_array_elements(projects.matched_keywords || EXCLUDED.matched_keywords)) AS keyword_values
        ),
        keyword_text = CONCAT_WS(' ', projects.keyword_text, EXCLUDED.keyword_text),
        raw_payload = projects.raw_payload || EXCLUDED.raw_payload,
        history = (
            SELECT COALESCE(jsonb_agg(value), '[]'::jsonb)
            FROM (SELECT DISTINCT value FROM jsonb_array_elements(projects.history || EXCLUDED.history)) AS history_values
        ),
        sources = (
            SELECT COALESCE(jsonb_agg(value), '[]'::jsonb)
            FROM (SELECT DISTINCT value FROM jsonb_array_elements(projects.sources || EXCLUDED.sources)) AS source_values
        ),
        last_seen_at = NOW(),
        updated_at = NOW()
"""


def save_projects(projects: List[Dict[str, Any]]) -> int:
    projects = dedupe_projects(projects)
    if not projects:
        return 0
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT dedupe_key, identity_key, announcement_no, contract_no, project_no FROM projects")
            existing = cur.fetchall()
            key_map: Dict[str, str] = {}
            for row in existing:
                for value in (row.get("identity_key"), row.get("announcement_no"), row.get("contract_no"), row.get("project_no")):
                    if value:
                        key_map[normalize_key(value)] = row["dedupe_key"]
            for project in projects:
                project_identity = identity_key(project)
                candidates = [
                    normalize_key(project_identity),
                    normalize_key(project.get("announcementNo")),
                    normalize_key(project.get("contractNo")),
                    normalize_key(project.get("projectNo")),
                ]
                resolved = next((key_map[value] for value in candidates if value and value in key_map), project["dedupeKey"])
                project["dedupeKey"] = resolved
                params = {
                    "dedupe_key": resolved,
                    "identity_key": project_identity,
                    "id": project.get("id") or f"SDI-{hashlib.sha1(resolved.encode()).hexdigest()[:16].upper()}",
                    "name": project.get("name") or "이름 없음",
                    "company": project.get("company"),
                    "announcement_no": project.get("announcementNo"),
                    "contract_no": project.get("contractNo"),
                    "project_no": project.get("projectNo"),
                    "region": project.get("region"),
                    "order_value": project.get("orderValue"),
                    "currency": project.get("currency") or "KRW",
                    "registered_at": project.get("registeredAt"),
                    "contract_date": project.get("contractDate"),
                    "delivery_date": project.get("deliveryDate"),
                    "shipyard": project.get("shipyard"),
                    "stage": str(project.get("stage") or "LEAD").upper() if str(project.get("stage") or "LEAD").upper() in STAGES else "LEAD",
                    "source_type": project.get("sourceType"),
                    "source_service": project.get("sourceService"),
                    "source_operation": project.get("sourceOperation"),
                    "verification_status": project.get("verificationStatus") or "UNVERIFIED",
                    "matched_keywords": Json(project.get("matchedKeywords") or []),
                    "keyword_text": project.get("keywordText") or "",
                    "raw_payload": Json(project.get("rawPayload") or {}),
                    "history": Json(project.get("history") or []),
                    "sources": Json(project.get("sources") or []),
                }
                cur.execute(UPSERT_SQL, params)
                for value in candidates:
                    if value:
                        key_map[value] = resolved
            conn.commit()
    return len(projects)


def extract_abb(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = (raw_payload or {}).get("_abbTargeting") or {}
    detail = meta.get("detail") or {}
    components = detail.get("componentScores") or {}
    return {
        "score": int(meta.get("score") or 0),
        "priority": meta.get("priority") or "WATCH",
        "driveScore": int(components.get("driveScore") or 0),
        "motorScore": int(components.get("motorScore") or 0),
        "powerScore": int(components.get("powerScore") or 0),
        "buyerKeywords": detail.get("buyerKeywords") or [],
        "equipmentKeywords": detail.get("equipmentKeywords") or [],
        "platformKeywords": detail.get("platformKeywords") or [],
        "shipyardKeywords": detail.get("shipyardKeywords") or [],
        "buildKeywords": detail.get("buildKeywords") or [],
        "watchlistHits": detail.get("watchlistHits") or [],
    }


def row_to_project(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw_payload") or {}
    abb = extract_abb(raw)
    updated = row.get("updated_at")
    first_seen = row.get("first_seen_at")
    last_seen = row.get("last_seen_at")
    return {
        "id": row["id"],
        "dedupeKey": row.get("dedupe_key"),
        "name": row.get("name") or "이름 없음",
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
        "stage": row.get("stage") or "LEAD",
        "sourceType": row.get("source_type") or "OTHER",
        "sourceService": row.get("source_service"),
        "sourceOperation": row.get("source_operation"),
        "verificationStatus": row.get("verification_status") or "UNVERIFIED",
        "matchedKeywords": row.get("matched_keywords") or [],
        "keywordText": row.get("keyword_text") or "",
        "rawPayload": raw,
        "history": row.get("history") or [],
        "sources": row.get("sources") or [],
        "owner": row.get("owner") or "",
        "nextActionDate": row.get("next_action_date"),
        "nextAction": row.get("next_action") or "",
        "notes": row.get("notes") or "",
        "favorite": bool(row.get("favorite")),
        "firstSeenAt": first_seen.isoformat() if hasattr(first_seen, "isoformat") else first_seen,
        "lastSeenAt": last_seen.isoformat() if hasattr(last_seen, "isoformat") else last_seen,
        "updatedAt": updated.isoformat() if hasattr(updated, "isoformat") else updated,
        "abbScore": abb["score"],
        "abbPriority": abb["priority"],
        "driveScore": abb["driveScore"],
        "motorScore": abb["motorScore"],
        "powerScore": abb["powerScore"],
        "buyerKeywords": abb["buyerKeywords"],
        "equipmentKeywords": abb["equipmentKeywords"],
        "platformKeywords": abb["platformKeywords"],
        "shipyardKeywords": abb["shipyardKeywords"],
        "buildKeywords": abb["buildKeywords"],
        "watchlistHits": abb["watchlistHits"],
    }


def project_data_quality(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(projects)
    today = date.today()
    overdue_actions = 0
    due_soon = 0
    for project in projects:
        value = project.get("nextActionDate")
        try:
            action_date = date.fromisoformat(value) if value else None
        except ValueError:
            action_date = None
        if action_date and action_date < today:
            overdue_actions += 1
        elif action_date and (action_date - today).days <= 14:
            due_soon += 1
    return {
        "total": total,
        "verifiedCount": sum(1 for item in projects if item.get("verificationStatus") == "VERIFIED"),
        "withDeliveryDate": sum(1 for item in projects if item.get("deliveryDate")),
        "withOwner": sum(1 for item in projects if item.get("owner")),
        "overdueActions": overdue_actions,
        "dueSoonActions": due_soon,
        "favoriteCount": sum(1 for item in projects if item.get("favorite")),
        "stageCounts": {stage: sum(1 for item in projects if item.get("stage") == stage) for stage in STAGES},
    }


def fetch_projects_from_db(q: str = "", stage: str = "ALL", limit: int = 500, offset: int = 0) -> Dict[str, Any]:
    clauses: List[str] = []
    params: List[Any] = []
    if q.strip():
        clauses.append(
            "(COALESCE(name,'') ILIKE %s OR COALESCE(company,'') ILIKE %s OR "
            "COALESCE(announcement_no,'') ILIKE %s OR COALESCE(project_no,'') ILIKE %s OR "
            "COALESCE(region,'') ILIKE %s OR COALESCE(keyword_text,'') ILIKE %s)"
        )
        params.extend([f"%{q.strip()}%"] * 6)
    if stage in STAGES:
        clauses.append("stage = %s")
        params.append(stage)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS count FROM projects{where}", params)
            total = int(cur.fetchone()["count"])
            cur.execute(
                f"SELECT * FROM projects{where} ORDER BY favorite DESC, updated_at DESC LIMIT %s OFFSET %s",
                [*params, limit, offset],
            )
            projects = [row_to_project(row) for row in cur.fetchall()]
            cur.execute("SELECT created_at FROM collector_run_logs WHERE status IN ('SUCCESS','PARTIAL') ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
            last_collected = row["created_at"].isoformat() if row and row.get("created_at") else None
    return {
        "projects": projects,
        "total": total,
        "limit": limit,
        "offset": offset,
        "lastCollectedAt": last_collected,
        "dataQuality": project_data_quality(projects),
    }


def fetch_seed_projects() -> List[Dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM projects ORDER BY updated_at DESC LIMIT 300")
            return [row_to_project(row) for row in cur.fetchall()]


def save_followup(project_id: str, values: Dict[str, Any]) -> Dict[str, Any]:
    stage = str(values.get("stage") or "").upper() or None
    if stage and stage not in STAGES:
        raise ValueError(f"허용되지 않는 단계입니다: {stage}")
    action_date = values.get("nextActionDate") or None
    if action_date:
        try:
            date.fromisoformat(action_date)
        except ValueError as exc:
            raise ValueError("nextActionDate는 YYYY-MM-DD 형식이어야 합니다.") from exc
    event = {
        "id": f"F-{uuid4().hex[:16]}",
        "date": date.today().isoformat(),
        "action": "FOLLOWUP_UPDATED",
        "detail": values.get("nextAction") or "영업 팔로업 정보 변경",
    }
    with closing(get_db_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE projects SET
                    stage = COALESCE(%s, stage),
                    owner = %s,
                    next_action_date = %s,
                    next_action = %s,
                    notes = %s,
                    favorite = COALESCE(%s, favorite),
                    history = history || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s OR dedupe_key = %s
                RETURNING *
                """,
                (
                    stage,
                    values.get("owner") or None,
                    action_date,
                    values.get("nextAction") or None,
                    values.get("notes") or None,
                    values.get("favorite"),
                    json.dumps([event], ensure_ascii=False),
                    project_id,
                    project_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(project_id)
            conn.commit()
            return row_to_project(row)


def write_run_log(collector_name: str, status: str, count: int, response_ms: float, error: Optional[str] = None) -> None:
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO collector_run_logs (id, collector_name, status, collected_count, response_ms, error_message) VALUES (%s,%s,%s,%s,%s,%s)",
                    (str(uuid4()), collector_name, status, count, response_ms, error),
                )
                conn.commit()
    except Exception as exc:
        logger.warning("수집 로그 저장 실패: %s", exc)


def start_collect_job(mode: str, alias: Optional[str] = None) -> Dict[str, Any]:
    global COLLECT_JOB
    COLLECT_JOB = {
        **new_collect_job(),
        "running": True,
        "jobId": str(uuid4()),
        "mode": mode,
        "collectorAlias": alias,
        "status": "RUNNING",
        "message": "수집 작업을 시작했습니다.",
        "startedAt": utc_now_iso(),
    }
    return dict(COLLECT_JOB)


def finish_collect_job(status: str, message: str, error: Optional[str] = None) -> None:
    COLLECT_JOB.update(
        running=False,
        status=status,
        message=message,
        error=error,
        progress=100,
        finishedAt=utc_now_iso(),
        lastCollectedAt=utc_now_iso() if status in {"SUCCESS", "PARTIAL"} else COLLECT_JOB.get("lastCollectedAt"),
    )


async def run_collector(alias: str, collector: Any, seed: List[Dict[str, Any]]) -> int:
    started = time.perf_counter()
    try:
        items = await asyncio.wait_for(collector.collect(seed), timeout=COLLECTOR_TIMEOUT_SECONDS)
        COLLECT_JOB["rawCount"] += len(items)
        saved = await asyncio.to_thread(save_projects, items)
        await asyncio.to_thread(write_run_log, alias, "SUCCESS", saved, (time.perf_counter() - started) * 1000)
        return saved
    except Exception as exc:
        await asyncio.to_thread(write_run_log, alias, "FAILED", 0, (time.perf_counter() - started) * 1000, str(exc)[:1000])
        raise
    finally:
        if hasattr(collector, "aclose"):
            await collector.aclose()


async def collection_runner(job_id: str, aliases: List[str]) -> None:
    global COLLECT_TASK
    registry = make_registry()
    errors: List[Dict[str, str]] = []
    saved_total = 0
    try:
        seed = await asyncio.to_thread(fetch_seed_projects)
        for index, alias in enumerate(aliases):
            if COLLECT_JOB.get("jobId") != job_id:
                return
            collector = registry[alias]
            COLLECT_JOB.update(
                currentStep=alias,
                progress=round(index / max(1, len(aliases)) * 100),
                message=f"{alias} 채널을 수집하고 있습니다.",
            )
            try:
                saved = await run_collector(alias, collector, seed)
                saved_total += saved
                COLLECT_JOB["savedCount"] = saved_total
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("%s 수집 실패: %s", alias, exc)
                errors.append({"collector": alias, "message": str(exc)[:500]})
                COLLECT_JOB["errors"] = errors
        if errors and saved_total == 0:
            finish_collect_job("FAILED", "수집에 성공한 채널이 없습니다.", errors[0]["message"])
        elif errors:
            finish_collect_job("PARTIAL", f"{saved_total}건 저장, {len(errors)}개 채널 경고")
        else:
            finish_collect_job("SUCCESS", f"수집 및 병합 완료: {saved_total}건 저장")
    except asyncio.CancelledError:
        finish_collect_job("CANCELLED", "수집 작업이 취소되었습니다.")
        raise
    except Exception as exc:
        logger.exception("수집 작업 실패")
        finish_collect_job("FAILED", "수집 작업이 실패했습니다.", str(exc))
    finally:
        COLLECT_TASK = None


@app.get("/health")
def health() -> JSONResponse:
    try:
        with closing(get_db_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        return JSONResponse({"status": "ok", "database": "connected", "version": app.version})
    except Exception as exc:
        return JSONResponse(
            {"status": "degraded", "database": "unavailable", "version": app.version, "detail": str(exc)},
            status_code=503,
        )


@app.get("/", include_in_schema=False)
async def serve_index() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="index.html을 찾을 수 없습니다.")
    return FileResponse(INDEX_FILE)


@app.get("/styles.css", include_in_schema=False)
async def serve_styles() -> FileResponse:
    if not STYLES_FILE.exists():
        raise HTTPException(status_code=404, detail="styles.css를 찾을 수 없습니다.")
    return FileResponse(STYLES_FILE, media_type="text/css")


@app.get("/api/projects")
def get_projects(
    q: str = Query(default="", max_length=200),
    stage: str = Query(default="ALL"),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    try:
        return fetch_projects_from_db(q=q, stage=stage.upper(), limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("프로젝트 조회 실패")
        raise HTTPException(status_code=503, detail=f"프로젝트 데이터베이스 조회 실패: {exc}") from exc


@app.put("/api/projects/{project_id}/followup", dependencies=[Depends(require_admin)])
def update_followup(project_id: str, payload: FollowupUpdate) -> Dict[str, Any]:
    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return {"project": save_followup(project_id, values), "message": "팔로업 정보가 저장되었습니다."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("팔로업 저장 실패")
        raise HTTPException(status_code=503, detail=f"팔로업 저장 실패: {exc}") from exc


@app.get("/api/meta/apis")
def api_meta() -> Dict[str, Any]:
    registry = make_registry()
    return {
        "version": app.version,
        "collectors": [
            {
                "alias": alias,
                "name": collector.name,
                "sourceType": collector.source_type,
                "operations": list(collector.operations),
                "configured": bool(collector.api_key()) if collector.operations else bool(
                    os.getenv(getattr(collector, "feed_env_name", ""), "")
                ),
            }
            for alias, collector in registry.items()
        ],
        "stages": STAGES,
        "mutationsProtected": True,
    }


@app.get("/api/collect/status")
def collect_status() -> Dict[str, Any]:
    return dict(COLLECT_JOB)


@app.post("/api/collect/reset", dependencies=[Depends(require_admin)])
async def reset_collect() -> Dict[str, Any]:
    global COLLECT_JOB
    if COLLECT_JOB.get("running"):
        raise HTTPException(status_code=409, detail="실행 중인 수집 작업은 초기화할 수 없습니다.")
    COLLECT_JOB = new_collect_job()
    return {"message": "수집 상태를 초기화했습니다.", **COLLECT_JOB}


def validate_collect_start() -> None:
    if COLLECT_JOB.get("running") or (COLLECT_TASK and not COLLECT_TASK.done()):
        raise HTTPException(status_code=409, detail="이미 수집 작업이 실행 중입니다.")


@app.post("/api/collect", dependencies=[Depends(require_admin)])
async def collect_all() -> Dict[str, Any]:
    global COLLECT_TASK
    validate_collect_start()
    registry = make_registry()
    aliases = [alias for alias in DEFAULT_PIPELINE_ALIASES if alias in registry and alias != "incheon_port"]
    if not aliases:
        raise HTTPException(status_code=500, detail="실행할 기본 수집기가 없습니다.")
    job = start_collect_job("PIPELINE")
    COLLECT_TASK = asyncio.create_task(collection_runner(job["jobId"], aliases))
    return job


@app.post("/api/collect/{collector_alias}", dependencies=[Depends(require_admin)])
async def collect_one(collector_alias: str) -> Dict[str, Any]:
    global COLLECT_TASK
    validate_collect_start()
    registry = make_registry()
    if collector_alias not in registry:
        raise HTTPException(status_code=404, detail="지원하지 않는 수집기입니다.")
    if collector_alias == "incheon_port":
        raise HTTPException(status_code=409, detail="인천항만 수집기는 API 사양 확정 전까지 보류 상태입니다.")
    job = start_collect_job("SINGLE", collector_alias)
    COLLECT_TASK = asyncio.create_task(collection_runner(job["jobId"], [collector_alias]))
    return job


@app.get("/api/run-operation/{collector_alias}/{operation_name}", dependencies=[Depends(require_admin)])
async def run_operation(collector_alias: str, operation_name: str, request: Request) -> Dict[str, Any]:
    registry = make_registry()
    collector = registry.get(collector_alias)
    if not collector:
        raise HTTPException(status_code=404, detail="지원하지 않는 수집기입니다.")
    if operation_name not in collector.operations:
        raise HTTPException(status_code=404, detail="지원하지 않는 operation입니다.")
    try:
        return await collector.request_operation(operation_name, dict(request.query_params))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API 경로를 찾을 수 없습니다.")
    return FileResponse(INDEX_FILE)
