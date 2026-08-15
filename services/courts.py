"""网球场馆统一库（SQLite）+ 低延迟附近/关键词搜索 API。"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Query

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _REPO_ROOT / "data" / "courts.db"
SEED_JSON = _REPO_ROOT / "data" / "shanghai_tennis_data.json"

# 地球半径（米）；附近搜索默认半径
EARTH_R = 6371000.0
DEFAULT_RADIUS_M = 30000
DEFAULT_LIMIT = 25
MAX_LIMIT = 50


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_courts_db(*, auto_import: bool = True) -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS courts (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT '',
                external_id TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                county TEXT NOT NULL DEFAULT '',
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                hours TEXT NOT NULL DEFAULT '',
                stadium_type TEXT NOT NULL DEFAULT '',
                court_surface TEXT NOT NULL DEFAULT '',
                sports_type TEXT NOT NULL DEFAULT '网球',
                biz_type TEXT NOT NULL DEFAULT '',
                courts_num INTEGER NOT NULL DEFAULT 0,
                indoor_courts INTEGER NOT NULL DEFAULT -1,
                outdoor_courts INTEGER NOT NULL DEFAULT -1,
                min_price REAL,
                price_range TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                facilities_json TEXT NOT NULL DEFAULT '[]',
                photos_json TEXT NOT NULL DEFAULT '[]',
                booking_json TEXT NOT NULL DEFAULT '[]',
                status INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_courts_geo ON courts(lat, lng);
            CREATE INDEX IF NOT EXISTS idx_courts_county ON courts(county);
            CREATE INDEX IF NOT EXISTS idx_courts_min_price ON courts(min_price);
            CREATE INDEX IF NOT EXISTS idx_courts_status ON courts(status);
            CREATE INDEX IF NOT EXISTS idx_courts_source_ext ON courts(source, external_id);
            CREATE INDEX IF NOT EXISTS idx_courts_name ON courts(name);

            CREATE VIRTUAL TABLE IF NOT EXISTS courts_fts USING fts5(
                court_id UNINDEXED,
                name,
                address,
                county,
                tokenize = 'unicode61'
            );
            """
        )
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM courts WHERE status=1"
        ).fetchone()["n"]

    if auto_import and int(n or 0) == 0 and SEED_JSON.exists():
        logger.info("courts.db empty — importing seed from %s", SEED_JSON.name)
        try:
            result = import_shanghai_json(SEED_JSON)
            logger.info("courts import done: %s", result)
        except Exception:
            logger.exception("courts auto-import failed")


def _parse_lng_lat(raw: str) -> tuple[float, float] | None:
    s = (raw or "").strip()
    if not s or "," not in s:
        return None
    a, b = s.split(",", 1)
    try:
        lng, lat = float(a.strip()), float(b.strip())
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    if abs(lat) < 1e-6 and abs(lng) < 1e-6:
        return None
    return lng, lat


def _hours_from_open(open_time: str) -> str:
    s = (open_time or "").strip()
    if not s:
        return ""
    if "-" in s and ":" not in s:
        # "8-22" → "08:00-22:00"
        parts = s.split("-", 1)
        try:
            a, b = int(parts[0]), int(parts[1])
            return f"{a:02d}:00-{b:02d}:00"
        except ValueError:
            return s
    return s


def _indoor_outdoor(stadium_type: str, courts_num: int) -> tuple[int, int]:
    st = (stadium_type or "").strip()
    n = max(0, int(courts_num or 0))
    if "室内" in st and "室外" in st:
        # 未知拆分
        return (n if n else -1, n if n else -1) if n else (-1, -1)
    if "室内" in st:
        return (n if n else -1, 0)
    if "室外" in st:
        return (0, n if n else -1)
    return (-1, -1)


def map_seed_item(item: dict[str, Any]) -> dict[str, Any] | None:
    sports = (item.get("SportsType") or "").strip()
    if sports and "网球" not in sports:
        return None
    coords = _parse_lng_lat(str(item.get("LngLat") or ""))
    if not coords:
        return None
    lng, lat = coords
    ext = str(item.get("StadiumId") or "").strip()
    if not ext:
        return None
    cid = f"ydb-{ext}"
    courts_num = 0
    try:
        courts_num = int(str(item.get("CourtsNum") or "0").strip() or "0")
    except ValueError:
        courts_num = 0
    stadium_type = (item.get("StadiumType") or "").strip()
    indoor, outdoor = _indoor_outdoor(stadium_type, courts_num)
    min_price = item.get("MinPrice")
    try:
        min_price_f = float(min_price) if min_price is not None and min_price != "" else None
    except (TypeError, ValueError):
        min_price_f = None
    price_range = ""
    if min_price_f is not None:
        price_range = str(int(min_price_f)) if min_price_f == int(min_price_f) else str(min_price_f)

    platform = (item.get("ReservationPlatform") or "").strip()
    phone = (item.get("StadiumTel") or "").strip()
    booking = []
    if platform:
        booking.append({"name": platform, "type": "miniprogram", "appId": ""})
    if phone:
        booking.append({"name": "电话预约", "type": "phone", "phone": phone})

    imgs = item.get("ImgUrls") or []
    if not isinstance(imgs, list):
        imgs = []
    cover = (item.get("ImgUrl") or "").strip()
    photos = [str(u) for u in imgs if u] or ([cover] if cover else [])

    county = (item.get("CountyName") or "").strip()
    address = (item.get("Address") or "").strip()
    if county and county not in address:
        address = f"{county}{address}" if address else county

    name = (item.get("StadiumName") or "").strip()
    if not name:
        return None

    now = time.time()
    return {
        "id": cid,
        "source": "ydb",
        "external_id": ext,
        "name": name,
        "address": address,
        "county": county,
        "lat": lat,
        "lng": lng,
        "phone": phone,
        "hours": _hours_from_open(str(item.get("openTime") or "")),
        "stadium_type": stadium_type,
        "court_surface": (item.get("CourtType") or "").strip(),
        "sports_type": sports or "网球",
        "biz_type": (item.get("StadiumBizType") or "").strip(),
        "courts_num": courts_num,
        "indoor_courts": indoor,
        "outdoor_courts": outdoor,
        "min_price": min_price_f,
        "price_range": price_range,
        "detail": (item.get("Detail") or "").strip(),
        "facilities_json": "[]",
        "photos_json": json.dumps(photos, ensure_ascii=False),
        "booking_json": json.dumps(booking, ensure_ascii=False),
        "status": 1 if int(item.get("Status") or 1) == 1 else 0,
        "created_at": now,
        "updated_at": now,
    }


def _upsert_court(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO courts (
            id, source, external_id, name, address, county, lat, lng,
            phone, hours, stadium_type, court_surface, sports_type, biz_type,
            courts_num, indoor_courts, outdoor_courts, min_price, price_range,
            detail, facilities_json, photos_json, booking_json, status,
            created_at, updated_at
        ) VALUES (
            :id, :source, :external_id, :name, :address, :county, :lat, :lng,
            :phone, :hours, :stadium_type, :court_surface, :sports_type, :biz_type,
            :courts_num, :indoor_courts, :outdoor_courts, :min_price, :price_range,
            :detail, :facilities_json, :photos_json, :booking_json, :status,
            :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            source=excluded.source,
            external_id=excluded.external_id,
            name=excluded.name,
            address=excluded.address,
            county=excluded.county,
            lat=excluded.lat,
            lng=excluded.lng,
            phone=excluded.phone,
            hours=excluded.hours,
            stadium_type=excluded.stadium_type,
            court_surface=excluded.court_surface,
            sports_type=excluded.sports_type,
            biz_type=excluded.biz_type,
            courts_num=excluded.courts_num,
            indoor_courts=excluded.indoor_courts,
            outdoor_courts=excluded.outdoor_courts,
            min_price=excluded.min_price,
            price_range=excluded.price_range,
            detail=excluded.detail,
            facilities_json=excluded.facilities_json,
            photos_json=excluded.photos_json,
            booking_json=excluded.booking_json,
            status=excluded.status,
            updated_at=excluded.updated_at
        """,
        row,
    )
    conn.execute("DELETE FROM courts_fts WHERE court_id=?", (row["id"],))
    conn.execute(
        """
        INSERT INTO courts_fts (court_id, name, address, county)
        VALUES (?, ?, ?, ?)
        """,
        (row["id"], row["name"], row["address"], row["county"]),
    )


def import_shanghai_json(path: Path | None = None) -> dict[str, Any]:
    path = path or SEED_JSON
    if not path.exists():
        raise FileNotFoundError(str(path))
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("data") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("invalid seed json")

    init_courts_db(auto_import=False)
    imported = 0
    skipped = 0
    with _conn() as conn:
        for item in items:
            if not isinstance(item, dict):
                skipped += 1
                continue
            mapped = map_seed_item(item)
            if not mapped:
                skipped += 1
                continue
            _upsert_court(conn, mapped)
            imported += 1
        conn.commit()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM courts WHERE status=1"
        ).fetchone()["n"]
    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "active_total": int(total),
        "db": str(DB_PATH),
    }


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _format_distance(m: float | None) -> str:
    if m is None:
        return ""
    if m < 1000:
        return f"{int(round(m))}m"
    return f"{m / 1000:.1f}km"


def _loads_list(s: str) -> list:
    try:
        v = json.loads(s or "[]")
        return v if isinstance(v, list) else []
    except Exception:
        return []


def row_to_court(
    row: sqlite3.Row,
    *,
    distance: float | None = None,
    lite: bool = False,
) -> dict[str, Any]:
    keys = set(row.keys())
    indoor = int(row["indoor_courts"] if "indoor_courts" in keys else -1)
    outdoor = int(row["outdoor_courts"] if "outdoor_courts" in keys else -1)
    stadium_type = (row["stadium_type"] if "stadium_type" in keys else "") or ""
    if indoor > 0 and outdoor > 0:
        court_type = "室内外"
    elif indoor > 0 or "室内" in stadium_type:
        court_type = "室内"
    elif outdoor > 0 or "室外" in stadium_type:
        court_type = "室外"
    else:
        court_type = stadium_type or ""

    courts_num = int(row["courts_num"] if "courts_num" in keys else 0) or 0
    total = -1
    if indoor >= 0 and outdoor >= 0:
        total = indoor + outdoor
    elif courts_num > 0:
        total = courts_num

    min_price = row["min_price"] if "min_price" in keys else None
    price_range = (row["price_range"] if "price_range" in keys else "") or ""
    if not price_range and min_price is not None:
        price_range = str(int(min_price)) if float(min_price) == int(min_price) else str(min_price)

    name = row["name"]
    dist = None if distance is None else float(distance)
    out: dict[str, Any] = {
        "id": row["id"],
        "name": name,
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "address": (row["address"] if "address" in keys else "") or "",
        "county": (row["county"] if "county" in keys else "") or "",
        "distance": dist,
        "distanceText": _format_distance(dist),
        "priceRange": price_range,
        "indoorCourts": indoor,
        "outdoorCourts": outdoor,
        "totalCourts": total,
        "courtType": court_type,
        "phone": (row["phone"] if "phone" in keys else "") or "",
    }
    if lite:
        # 列表：只带首图 URL，前端再决定是否渲染（如前 10 条）
        cover = ""
        try:
            photos = _loads_list(row["photos_json"] if "photos_json" in keys else "[]")
            if photos:
                cover = str(photos[0] or "")
        except Exception:
            cover = ""
        out["cover"] = cover
        out["photos"] = []
        out["bookingOptions"] = []
        out["facilities"] = []
        out["detail"] = ""
        out["extSources"] = []
        out["hours"] = ""
        out["rating"] = -1
        return out

    photos = _loads_list(row["photos_json"] if "photos_json" in keys else "[]")[:3]
    booking = _loads_list(row["booking_json"] if "booking_json" in keys else "[]")
    facilities = _loads_list(row["facilities_json"] if "facilities_json" in keys else "[]")
    surface = ((row["court_surface"] if "court_surface" in keys else "") or "").strip()
    if surface and surface not in facilities:
        facilities = [surface] + list(facilities)

    out.update(
        {
            "source": (row["source"] if "source" in keys else "") or "",
            "rating": -1,
            "minPrice": float(min_price) if min_price is not None else None,
            "courtSurface": surface,
            "facilities": facilities,
            "photos": photos,
            "hours": (row["hours"] if "hours" in keys else "") or "",
            "detail": ((row["detail"] if "detail" in keys else "") or "")[:500],
            "bookingOptions": booking,
            "extSources": [
                {"name": "大众点评", "icon": "⭐", "keyword": name},
                {"name": "小红书", "icon": "📕", "keyword": name + " 网球场"},
            ],
            "sportsType": (row["sports_type"] if "sports_type" in keys else "") or "网球",
            "bizType": (row["biz_type"] if "biz_type" in keys else "") or "",
        }
    )
    return out


def get_court(court_id: str) -> dict[str, Any] | None:
    cid = (court_id or "").strip()
    if not cid:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM courts WHERE id=? AND status=1", (cid,)
        ).fetchone()
        if not row:
            return None
        return row_to_court(row, lite=False)


_LITE_COLS = (
    "c.id, c.name, c.address, c.county, c.lat, c.lng, c.phone, "
    "c.stadium_type, c.courts_num, c.indoor_courts, c.outdoor_courts, "
    "c.min_price, c.price_range, c.photos_json"
)


def search_courts(
    *,
    lat: float | None = None,
    lng: float | None = None,
    keyword: str = "",
    court_type: str = "all",
    price: str = "all",
    county: str = "",
    radius_m: int = DEFAULT_RADIUS_M,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    lite: bool = True,
) -> dict[str, Any]:
    """低延迟搜索：轻量字段 + 包围盒预筛 + 距离排序。"""
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    offset = max(0, int(offset or 0))
    radius_m = max(500, min(int(radius_m or DEFAULT_RADIUS_M), 200000))
    kw = (keyword or "").strip()
    county_q = (county or "").strip()
    ctype = (court_type or "all").strip().lower()
    price_k = (price or "all").strip()

    where = ["c.status=1"]
    params: list[Any] = []

    if kw:
        where.append("(c.name LIKE ? OR c.address LIKE ? OR c.county LIKE ?)")
        like = f"%{kw}%"
        params.extend([like, like, like])

    if county_q:
        where.append("c.county LIKE ?")
        params.append(f"%{county_q}%")

    if ctype == "indoor":
        where.append("(c.indoor_courts > 0 OR c.stadium_type LIKE '%室内%')")
    elif ctype == "outdoor":
        where.append("(c.outdoor_courts > 0 OR c.stadium_type LIKE '%室外%')")

    if price_k == "free":
        where.append("(c.price_range LIKE '%免费%' OR c.min_price = 0)")
    elif price_k == "0-60":
        where.append("c.min_price IS NOT NULL AND c.min_price <= 60")
    elif price_k == "60-120":
        where.append("c.min_price IS NOT NULL AND c.min_price > 60 AND c.min_price <= 120")
    elif price_k == "120-200":
        where.append("c.min_price IS NOT NULL AND c.min_price > 120 AND c.min_price <= 200")
    elif price_k == "200+":
        where.append("c.min_price IS NOT NULL AND c.min_price > 200")

    use_geo = lat is not None and lng is not None
    if use_geo:
        dlat = radius_m / 111000.0
        cos_lat = max(0.2, abs(math.cos(math.radians(float(lat)))))
        dlng = radius_m / (111000.0 * cos_lat)
        where.append("c.lat BETWEEN ? AND ? AND c.lng BETWEEN ? AND ?")
        params.extend([float(lat) - dlat, float(lat) + dlat, float(lng) - dlng, float(lng) + dlng])

    cols = _LITE_COLS if lite else "c.*"
    sql = f"SELECT {cols} FROM courts c WHERE {' AND '.join(where)}"
    with _conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    scored: list[tuple[float, Any]] = []
    for r in rows:
        dist = 0.0
        if use_geo:
            dist = _haversine_m(float(lat), float(lng), float(r["lat"]), float(r["lng"]))
            if dist > radius_m:
                continue
        scored.append((dist if use_geo else 0.0, r))

    if use_geo:
        scored.sort(key=lambda x: x[0])
    else:
        scored.sort(key=lambda x: (x[1]["name"] or ""))

    total = len(scored)
    page = scored[offset : offset + limit]
    items = [
        row_to_court(r, distance=(d if use_geo else None), lite=lite) for d, r in page
    ]
    return {
        "items": items,
        "total": total,
        "source": "courts.db",
        "limit": limit,
        "offset": offset,
        "lite": bool(lite),
    }


def courts_stats() -> dict[str, Any]:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM courts").fetchone()["n"]
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM courts WHERE status=1"
        ).fetchone()["n"]
        by_source = conn.execute(
            """
            SELECT source, COUNT(*) AS n FROM courts
            WHERE status=1 GROUP BY source ORDER BY n DESC
            """
        ).fetchall()
    return {
        "db": str(DB_PATH),
        "total": int(total),
        "active": int(active),
        "by_source": {r["source"]: int(r["n"]) for r in by_source},
        "seed_json_exists": SEED_JSON.exists(),
    }


def register_courts_routes(api) -> None:
    @api.get("/api/courts/stats")
    def api_courts_stats():
        return courts_stats()

    @api.get("/api/courts/search")
    def api_courts_search(
        lat: float | None = Query(None),
        lng: float | None = Query(None),
        keyword: str = Query(""),
        court_type: str = Query("all", alias="type"),
        price: str = Query("all"),
        county: str = Query(""),
        radius_m: int = Query(DEFAULT_RADIUS_M, ge=500, le=200000),
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
        lite: int = Query(1, ge=0, le=1),
    ):
        return search_courts(
            lat=lat,
            lng=lng,
            keyword=keyword,
            court_type=court_type,
            price=price,
            county=county,
            radius_m=radius_m,
            limit=limit,
            offset=offset,
            lite=bool(lite),
        )

    @api.get("/api/courts/{court_id}")
    def api_court_detail(court_id: str):
        court = get_court(court_id)
        if not court:
            raise HTTPException(status_code=404, detail="球场不存在")
        return court

    @api.post("/api/courts/import/shanghai")
    def api_courts_import():
        """运维：从 data/shanghai_tennis_data.json 重新导入（幂等 upsert）。"""
        try:
            return import_shanghai_json()
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
