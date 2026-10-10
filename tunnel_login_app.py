from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import html
import io
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from email.parser import BytesParser
from email.policy import default as EMAIL_POLICY
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parent
PLATFORM_DIR = ROOT / "platform"
DB_PATH = PLATFORM_DIR / "app.db"
INITIAL_ADMIN = PLATFORM_DIR / "INITIAL_ADMIN.txt"
UPLOAD_DIR = ROOT / "uploads"
UPLOADED_MODEL_DIR = ROOT / "models" / "uploaded"
UPLOAD_REGISTRY = PLATFORM_DIR / "uploaded_tunnels.json"
SESSION_COOKIE = "tunnel_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
PBKDF2_ITERATIONS = 260_000
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
BRAIN_API_BASE = os.environ.get("BRAIN_API_BASE", "http://192.168.12.3:18001/v1").rstrip("/")
BRAIN_MODEL = os.environ.get("BRAIN_MODEL", "qwen2.5-7b")
BRAIN_API_KEY = os.environ.get("BRAIN_API_KEY", "").strip()
BRAIN_PROVIDER = os.environ.get("BRAIN_PROVIDER", "openai-compatible")
BRAIN_TIMEOUT_SECONDS = float(os.environ.get("BRAIN_TIMEOUT_SECONDS", "45"))
BRAIN_HISTORY_LIMIT = 20
BRAIN_HISTORY_TOTAL_LIMIT = 10000
BRAIN_HISTORY_CONTENT_LIMIT = 1200
BRAIN_RAG_ENABLED = os.environ.get("BRAIN_RAG_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
BRAIN_RAG_TOP_K = int(os.environ.get("BRAIN_RAG_TOP_K", "3"))
BRAIN_RAG_CONTEXT_CHARS = int(os.environ.get("BRAIN_RAG_CONTEXT_CHARS", "1800"))
BRAIN_MAX_TOKENS = int(os.environ.get("BRAIN_MAX_TOKENS", "512"))
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_UPLOAD_FILE_BYTES = 80 * 1024 * 1024
MAX_ZIP_MEMBERS = 80
TUNNEL_CORS_ORIGINS = {
    item.strip().rstrip("/")
    for item in os.environ.get("TUNNEL_CORS_ORIGINS", "").split(",")
    if item.strip()
}
CROSS_SITE_COOKIES = os.environ.get("TUNNEL_CROSS_SITE_COOKIES", "0").strip().lower() in {"1", "true", "yes", "on"}

STATION_RE = re.compile(r"([A-Za-z\u4e00-\u9fa5]*)(\d+)\+([0-9]+(?:\.[0-9]+)?)")


def brain_headers(content_type: bool = False) -> dict[str, str]:
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = "application/json"
    if BRAIN_API_KEY:
        headers["Authorization"] = f"Bearer {BRAIN_API_KEY}"
    return headers


LOGIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>隧道智慧管控平台登录</title>
<style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:28px;background:radial-gradient(circle at 72% 26%,#5aa0c833 0,#5aa0c800 32%),linear-gradient(135deg,#081421,#123d5f 46%,#23313b);font-family:Arial,"Microsoft YaHei",sans-serif;color:#172033;overflow:hidden}
body:before{content:"";position:fixed;inset:0;background:linear-gradient(90deg,#0008,#0002),url("/platform/assets/tunnel_excavation_hero.svg") center/cover no-repeat;opacity:.48;filter:saturate(.9)}
body:after{content:"";position:fixed;inset:auto -10% -34% -10%;height:52%;background:radial-gradient(ellipse at center,#f0b35a33 0,#f0b35a00 58%);pointer-events:none}
.box{position:relative;z-index:1;width:min(440px,94vw);background:rgba(255,255,255,.94);border:1px solid rgba(255,255,255,.58);border-radius:22px;padding:34px 34px 28px;box-shadow:0 28px 90px #06142188,0 0 0 1px #ffffff40;backdrop-filter:blur(14px)}
.brand{display:inline-flex;align-items:center;gap:8px;padding:6px 10px;border-radius:999px;background:#eef6ff;color:#1767c2;font-size:12px;font-weight:700;letter-spacing:.08em}
h1{margin:16px 0 8px;font-size:28px;color:#0b3158;letter-spacing:.02em}.sub{margin:0 0 26px;color:#617089;font-size:14px;line-height:1.7}
label{display:block;font-size:13px;color:#526177;margin:15px 0 7px;font-weight:700}input{display:block;width:100%;padding:13px 14px;border:1px solid #cbd6e5;border-radius:12px;font-size:15px;background:#fbfdff;outline:none;transition:border-color .18s ease,box-shadow .18s ease,background .18s ease}
input:focus{border-color:#2785d6;background:#fff;box-shadow:0 0 0 4px #2785d61a}
button{width:100%;margin-top:22px;border:0;border-radius:12px;padding:13px;background:linear-gradient(135deg,#1767c2,#22a6d5);color:#fff;font-weight:700;font-size:15px;cursor:pointer;box-shadow:0 12px 24px #1767c233;transition:transform .18s ease,box-shadow .18s ease}
button:hover{transform:translateY(-1px);box-shadow:0 16px 32px #1767c240}
.err{background:#fff1f1;color:#b61e1e;border:1px solid #f0b8b8;padding:10px 12px;border-radius:10px;margin-bottom:12px;font-size:13px}
.foot{margin:18px 0 0;color:#8794a7;font-size:12px;line-height:1.6;text-align:center}
</style>
</head>
<body>
<form class="box" method="post" action="/login">
  <div class="brand">TUNNEL CONTROL</div>
  <h1>隧道智慧管控平台</h1>
  <p class="sub">请输入账号密码。登录后可查看总览、预警、监控量测、超欠挖和三维模型。</p>
  {error}
  <label>账号</label>
  <input name="username" autocomplete="username" required autofocus>
  <label>密码</label>
  <input name="password" type="password" autocomplete="current-password" required>
  <button type="submit">登录</button>
  <p class="foot">第一版原型使用服务器本地 SQLite 账号库。公网部署前建议配置 HTTPS、反向代理和更细权限。</p>
</form>
</body>
</html>"""


def now() -> int:
    return int(time.time())


def ensure_dirs() -> None:
    PLATFORM_DIR.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def password_hash(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str, int]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        base64.b64encode(digest).decode("ascii"),
        base64.b64encode(salt).decode("ascii"),
        iterations,
    )


def verify_password(password: str, digest_b64: str, salt_b64: str, iterations: int) -> bool:
    digest, _, _ = password_hash(password, base64.b64decode(salt_b64), iterations)
    return hmac.compare_digest(digest, digest_b64)


def init_db() -> None:
    ensure_dirs()
    with db() as conn:
        conn.executescript(
            """
            create table if not exists users (
                id integer primary key autoincrement,
                username text not null unique,
                password_hash text not null,
                salt text not null,
                iterations integer not null,
                role text not null default 'viewer',
                created_at integer not null,
                last_login integer
            );
            create table if not exists sessions (
                token text primary key,
                user_id integer not null references users(id) on delete cascade,
                created_at integer not null,
                expires_at integer not null
            );
            """
        )
        count = conn.execute("select count(*) from users").fetchone()[0]
        if count == 0:
            username = ADMIN_USERNAME
            password = ADMIN_PASSWORD or secrets.token_urlsafe(14)
            digest, salt, iterations = password_hash(password)
            conn.execute(
                """
                insert into users(username, password_hash, salt, iterations, role, created_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (username, digest, salt, iterations, "admin", now()),
            )
            INITIAL_ADMIN.write_text(
                "隧道智慧管控平台初始管理员账号\n"
                "================================\n"
                f"username: {username}\n"
                f"password: {password}\n\n"
                "请首次登录后妥善保存，并在正式部署前改为项目自定义账号密码。\n",
                encoding="utf-8",
            )
            try:
                os.chmod(INITIAL_ADMIN, 0o600)
            except OSError:
                pass


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute("delete from sessions where expires_at < ?", (now(),))
        conn.execute(
            "insert into sessions(token, user_id, created_at, expires_at) values (?, ?, ?, ?)",
            (token, user_id, now(), now() + SESSION_TTL_SECONDS),
        )
    return token


def get_user_by_session(token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            """
            select u.* from sessions s
            join users u on u.id = s.user_id
            where s.token = ? and s.expires_at >= ?
            """,
            (token, now()),
        ).fetchone()
    return row


def clear_session(token: str | None) -> None:
    if not token:
        return
    with db() as conn:
        conn.execute("delete from sessions where token = ?", (token,))


def authenticate(username: str, password: str) -> sqlite3.Row | None:
    with db() as conn:
        user = conn.execute("select * from users where username = ?", (username,)).fetchone()
        if not user:
            return None
        if not verify_password(password, user["password_hash"], user["salt"], user["iterations"]):
            return None
        conn.execute("update users set last_login = ? where id = ?", (now(), user["id"]))
        return user


def cookie_header(token: str, max_age: int = SESSION_TTL_SECONDS) -> str:
    same_site = "SameSite=None; Secure" if CROSS_SITE_COOKIES else "SameSite=Lax"
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; {same_site}; Max-Age={max_age}"


def safe_file_path(request_path: str) -> Path | None:
    parsed = urlparse(request_path)
    raw_path = unquote(parsed.path.lstrip("/"))
    if raw_path in ("", "app"):
        raw_path = "platform/index.html"
    candidate = (ROOT / raw_path).resolve()
    allowed_roots = [ROOT / "platform", ROOT / "models", ROOT / "structured", ROOT / "raw"]
    if candidate == (ROOT / "dashboard.html").resolve():
        return candidate
    for allowed in allowed_roots:
        try:
            candidate.relative_to(allowed.resolve())
            if candidate.is_file():
                return candidate
        except ValueError:
            pass
    return None


def load_json_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    clean = re.sub(r"[^0-9A-Za-z._+\-\u4e00-\u9fa5]+", "_", name).strip("._")
    return clean[:120] or f"upload_{uuid.uuid4().hex[:8]}.bin"


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "").replace("，", "").replace("㎡", "").replace("m²", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def station_chainage(station: str | None) -> float | None:
    if not station:
        return None
    match = STATION_RE.search(str(station))
    if not match:
        return parse_number(station)
    return int(match.group(2)) * 1000 + float(match.group(3))


def first_value(row: dict, names: list[str]):
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        key = name.lower()
        if key in lowered and str(lowered[key]).strip() != "":
            return lowered[key], key
    for key, value in lowered.items():
        if any(name.lower() in key for name in names) and str(value).strip() != "":
            return value, key
    return None, ""


def number_from_columns(row: dict, names: list[str]) -> float | None:
    value, key = first_value(row, names)
    number = parse_number(value)
    if number is None:
        return None
    if "mm" in key or "毫米" in key:
        return number / 1000.0
    return number


def classify_status(status_text: str | None, deviation: float | None, over_area: float | None, under_area: float | None) -> str:
    text = (status_text or "").strip().lower()
    if any(token in text for token in ("欠", "under", "undercut", "underbreak")):
        return "under"
    if any(token in text for token in ("超", "over", "overcut", "overbreak")):
        return "over"
    if any(token in text for token in ("正常", "normal", "ok", "合格")):
        return "normal"
    if deviation is not None:
        if deviation > 0.001:
            return "over"
        if deviation < -0.001:
            return "under"
    if under_area is not None and under_area > 0:
        return "under"
    if over_area is not None and over_area > 0:
        return "over"
    return "normal"


def normalize_upload_row(row: dict, source_name: str, row_index: int) -> dict | None:
    station, _ = first_value(row, ["station", "桩号", "断面", "测试断面", "milepost", "chainage_name"])
    x = number_from_columns(row, ["chainage_offset_m", "chainage_offset", "x", "里程偏移", "轴向", "桩号距离"])
    if x is None:
        x = number_from_columns(row, ["chainage", "里程"])
    y = number_from_columns(row, ["y", "横向", "横坐标", "lateral"])
    z = number_from_columns(row, ["z", "竖向", "高程", "vertical", "elevation"])
    deviation = number_from_columns(row, ["deviation", "delta", "偏差", "超欠挖值", "offset", "差值"])
    over_area = number_from_columns(row, ["over_area", "overbreak_area", "超挖面积", "超挖面积_"])
    under_area = number_from_columns(row, ["under_area", "underbreak_area", "欠挖面积", "欠挖面积_"])
    max_over = number_from_columns(row, ["max_over", "最大超挖", "最大超挖_m", "超挖深度"])
    max_under = number_from_columns(row, ["max_under", "最大欠挖", "最大欠挖_m", "欠挖深度"])
    status_text, _ = first_value(row, ["status", "type", "classification", "类别", "类型", "超欠挖"])
    if station is not None:
        station = str(station).strip()
    chainage_value = station_chainage(station)
    if x is None and chainage_value is not None:
        x = chainage_value
    if x is None and y is None and z is None and over_area is None and under_area is None:
        return None
    status = classify_status(str(status_text) if status_text is not None else None, deviation, over_area, under_area)
    return {
        "station": station or f"section_{row_index + 1}",
        "x": x,
        "y": y,
        "z": z,
        "deviation": deviation,
        "status": status,
        "over_area": over_area,
        "under_area": under_area,
        "max_over": max_over,
        "max_under": max_under,
        "source": source_name,
        "row_index": row_index + 1,
    }


def parse_delimited_records(path: Path, data: bytes) -> list[dict]:
    text = decode_text(data)
    sample = text[:4096]
    delimiter = ","
    if "\t" in sample and sample.count("\t") >= sample.count(","):
        delimiter = "\t"
    elif ";" in sample and sample.count(";") > sample.count(","):
        delimiter = ";"
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    headerish = any(ch.isalpha() or "\u4e00" <= ch <= "\u9fff" for ch in lines[0])
    records: list[dict] = []
    if headerish and delimiter in lines[0]:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for idx, row in enumerate(reader):
            item = normalize_upload_row(row, path.name, idx)
            if item:
                records.append(item)
        return records
    if headerish and "," in lines[0]:
        reader = csv.DictReader(io.StringIO(text))
        for idx, row in enumerate(reader):
            item = normalize_upload_row(row, path.name, idx)
            if item:
                records.append(item)
        return records
    for idx, line in enumerate(lines):
        parts = re.split(r"[\s,;]+", line.strip())
        nums = [parse_number(part) for part in parts]
        nums = [x for x in nums if x is not None]
        if len(nums) < 3:
            continue
        status_text = None
        if len(parts) >= 4 and parse_number(parts[3]) is None:
            status_text = parts[3]
        row = {"x": nums[0], "y": nums[1], "z": nums[2]}
        if len(nums) >= 4:
            row["deviation"] = nums[3]
        if status_text:
            row["status"] = status_text
        item = normalize_upload_row(row, path.name, idx)
        if item:
            records.append(item)
    return records


def parse_json_records(path: Path, data: bytes) -> list[dict]:
    payload = json.loads(decode_text(data))
    records: list[dict] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("points"), list):
            payload = payload["points"]
        elif isinstance(payload.get("sections"), list):
            for idx, sec in enumerate(payload["sections"]):
                if not isinstance(sec, dict):
                    continue
                summary = normalize_upload_row(sec, path.name, idx)
                if summary:
                    records.append(summary)
                for point in sec.get("testPoints3d") or sec.get("points") or []:
                    if isinstance(point, dict):
                        row = dict(point)
                    elif isinstance(point, (list, tuple)) and len(point) >= 3:
                        row = {"x": point[0], "y": point[1], "z": point[2]}
                    else:
                        continue
                    row.setdefault("station", sec.get("station"))
                    row.setdefault("x", sec.get("chainage_offset_m", sec.get("x")))
                    row.setdefault("status", "over" if (sec.get("over_area") or 0) else "normal")
                    item = normalize_upload_row(row, path.name, idx)
                    if item:
                        records.append(item)
            return records
        else:
            payload = [payload]
    if isinstance(payload, list):
        for idx, row in enumerate(payload):
            if isinstance(row, dict):
                item = normalize_upload_row(row, path.name, idx)
            elif isinstance(row, (list, tuple)) and len(row) >= 3:
                item = normalize_upload_row({"x": row[0], "y": row[1], "z": row[2], "deviation": row[3] if len(row) > 3 else None}, path.name, idx)
            else:
                item = None
            if item:
                records.append(item)
    return records


def parse_supported_file(path: Path, data: bytes) -> tuple[list[dict], list[str]]:
    suffix = path.suffix.lower()
    warnings: list[str] = []
    try:
        if suffix in {".json", ".geojson"}:
            return parse_json_records(path, data), warnings
        if suffix in {".csv", ".txt", ".xyz", ".pts", ".tsv"}:
            return parse_delimited_records(path, data), warnings
        warnings.append(f"{path.name}: 当前自动建模原型暂不解析 {suffix or '无扩展名'}，已保存原文件。")
        return [], warnings
    except Exception as exc:
        return [], [f"{path.name}: 解析失败 - {exc}"]


def parse_multipart_form(content_type: str, body: bytes) -> tuple[dict, list[dict]]:
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=EMAIL_POLICY).parsebytes(header + body)
    fields: dict[str, str] = {}
    files: list[dict] = []
    if not message.is_multipart():
        return fields, files
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename:
            files.append(
                {
                    "field": name,
                    "filename": safe_filename(filename),
                    "content_type": part.get_content_type(),
                    "data": payload,
                }
            )
        else:
            fields[name] = decode_text(payload).strip()
    return fields, files


def normalize_model_records(records: list[dict]) -> list[dict]:
    usable = [dict(r) for r in records if r.get("x") is not None or r.get("station")]
    if not usable:
        return []
    chainages = []
    for item in usable:
        if item.get("x") is None:
            item["x"] = station_chainage(item.get("station"))
        if item.get("x") is not None:
            chainages.append(float(item["x"]))
    if not chainages:
        for idx, item in enumerate(usable):
            item["x"] = float(idx)
        chainages = [float(item["x"]) for item in usable]
    base = min(chainages)
    should_offset = base > 1000 or any(item.get("station") for item in usable)
    for idx, item in enumerate(usable):
        if item.get("x") is None:
            item["x"] = float(idx)
        raw_x = float(item["x"])
        item["x_raw"] = raw_x
        item["x"] = raw_x - base if should_offset else raw_x
    return usable


def sample_section(points: list[dict], sample_count: int = 56) -> list[list[float]]:
    valid = [p for p in points if p.get("y") is not None and p.get("z") is not None]
    if len(valid) < 4:
        return []
    cy = sum(float(p["y"]) for p in valid) / len(valid)
    cz = sum(float(p["z"]) for p in valid) / len(valid)
    ordered = sorted(valid, key=lambda p: math.atan2(float(p["z"]) - cz, float(p["y"]) - cy))
    x = sum(float(p["x"]) for p in valid) / len(valid)
    return [[x, float(ordered[int(i * len(ordered) / sample_count)]["y"]), float(ordered[int(i * len(ordered) / sample_count)]["z"])] for i in range(sample_count)]


def conceptual_ring(x: float, over_area: float, under_area: float, sample_count: int = 64) -> list[list[float]]:
    scale = max(-0.22, min(0.28, over_area * 0.012 - under_area * 0.014))
    ry = 6.6 * (1 + scale)
    rz = 4.7 * (1 + scale)
    center_z = 4.6
    return [[x, ry * math.cos(2 * math.pi * i / sample_count), center_z + rz * math.sin(2 * math.pi * i / sample_count)] for i in range(sample_count)]


def build_model_payload(records: list[dict], tunnel_id: str, batch_id: str) -> tuple[dict, list[str]]:
    normalized = normalize_model_records(records)
    warnings: list[str] = []
    point_records = [r for r in normalized if r.get("y") is not None and r.get("z") is not None]
    summary_records = [r for r in normalized if r.get("over_area") is not None or r.get("under_area") is not None or r.get("max_over") is not None or r.get("max_under") is not None]
    points = []
    for r in point_records:
        deviation = r.get("deviation")
        label = f"{r.get('station') or ''} {r.get('status') or ''}".strip()
        points.append(
            {
                "x": round(float(r["x"]), 5),
                "y": round(float(r["y"]), 5),
                "z": round(float(r["z"]), 5),
                "status": r.get("status", "normal"),
                "label": label or r.get("source", "point"),
                "deviation": deviation,
            }
        )
    mesh_points: list[list[list[float]]] = []
    mode = "point_cloud"
    if point_records:
        groups: dict[str, list[dict]] = {}
        for r in point_records:
            key = str(r.get("station") or f"{float(r['x']):.2f}")
            groups.setdefault(key, []).append(r)
        sections = []
        for group in groups.values():
            curve = sample_section(group)
            if curve:
                sections.append(curve)
        sections.sort(key=lambda curve: curve[0][0])
        if len(sections) >= 2:
            mesh_points = sections
            mode = "section_points"
    if not mesh_points and summary_records:
        if point_records:
            warnings.append("空间测点不足以重建连续断面曲面，已使用超欠挖汇总表生成概念隧道外形。")
        else:
            warnings.append("上传数据缺少 y/z 空间点，仅能根据面积/深度汇总生成概念 3D 模型，不能作为精确工程模型。")
        sections = []
        seen = set()
        for idx, r in enumerate(sorted(summary_records, key=lambda item: float(item.get("x", 0)))):
            x = float(r.get("x", idx))
            key = round(x, 4)
            if key in seen:
                continue
            seen.add(key)
            over_area = float(r.get("over_area") or 0)
            under_area = float(r.get("under_area") or 0)
            sections.append(conceptual_ring(x, over_area, under_area))
            status = "under" if under_area > 0 else ("over" if over_area > 0 else "normal")
            if not point_records and status != "normal":
                points.append(
                    {
                        "x": round(x, 5),
                        "y": 0,
                        "z": 9.5,
                        "status": status,
                        "label": f"{r.get('station') or f'S{idx + 1}'} {status}",
                        "deviation": r.get("max_under") if status == "under" else r.get("max_over"),
                    }
                )
        if len(sections) == 1:
            clone = [[p[0] + 1.0, p[1], p[2]] for p in sections[0]]
            sections.append(clone)
        mesh_points = sections
        mode = "summary_concept"
    if not point_records and not summary_records:
        warnings.append("没有识别到可建模字段。至少需要 x/y/z 空间点，或 station + 超欠挖面积/深度汇总。")
    all_xyz = [[p["x"], p["y"], p["z"]] for p in points]
    for curve in mesh_points:
        all_xyz.extend(curve)
    if all_xyz:
        mins = [min(p[i] for p in all_xyz) for i in range(3)]
        maxs = [max(p[i] for p in all_xyz) for i in range(3)]
    else:
        mins, maxs = [0, 0, 0], [1, 1, 1]
    status_counts = {
        "over": sum(1 for p in points if p.get("status") == "over"),
        "under": sum(1 for p in points if p.get("status") == "under"),
        "normal": sum(1 for p in points if p.get("status") == "normal"),
    }
    return (
        {
            "batchId": batch_id,
            "tunnelId": tunnel_id,
            "mode": mode,
            "meshPoints": mesh_points,
            "points": points[:10000],
            "stats": {
                "records": len(records),
                "usableRecords": len(normalized),
                "spacePoints": len(point_records),
                "summaryRows": len(summary_records),
                "meshSections": len(mesh_points),
                "overPoints": status_counts["over"],
                "underPoints": status_counts["under"],
                "normalPoints": status_counts["normal"],
            },
            "bbox": {"min": mins, "max": maxs},
            "center": [(mins[i] + maxs[i]) / 2 for i in range(3)],
            "ranges": [maxs[i] - mins[i] or 1 for i in range(3)],
            "warnings": warnings,
        },
        warnings,
    )


def write_obj(path: Path, model: dict) -> None:
    lines = ["# Uploaded tunnel model generated by tunnel control platform", "# x=chainage offset, y=lateral, z=vertical"]
    mesh = model.get("meshPoints") or []
    if mesh:
        for curve in mesh:
            for x, y, z in curve:
                lines.append(f"v {x:.5f} {y:.5f} {z:.5f}")
        n = len(mesh[0])
        for s in range(len(mesh) - 1):
            for j in range(n):
                a = s * n + j + 1
                b = s * n + ((j + 1) % n) + 1
                c = (s + 1) * n + ((j + 1) % n) + 1
                d = (s + 1) * n + j + 1
                lines.append(f"f {a} {b} {c} {d}")
    else:
        for p in model.get("points") or []:
            lines.append(f"v {float(p['x']):.5f} {float(p['y']):.5f} {float(p['z']):.5f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


UPLOAD_VIEWER_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>上传数据自动 3D 建模</title>
<style>
body{margin:0;font-family:Arial,"Microsoft YaHei",sans-serif;background:#eef2f7;color:#172033}
header{background:#0d3768;color:#fff;padding:14px 22px}h1{margin:0;font-size:21px}header p{margin:6px 0 0;color:#d8e8ff;font-size:13px}
main{display:grid;grid-template-columns:330px 1fr;height:calc(100vh - 66px)}aside{background:#fff;border-right:1px solid #dce3ed;padding:16px;overflow:auto}
canvas{display:block;width:100%;height:100%;background:linear-gradient(#fbfdff,#e6edf6)}button{border:1px solid #cbd6e5;background:#f7faff;border-radius:8px;padding:8px 10px;cursor:pointer;margin:6px 6px 6px 0}
.card{border:1px solid #dce3ed;border-radius:10px;padding:10px;margin:10px 0;background:#fbfdff}.muted{color:#65748b;font-size:12px;line-height:1.6}.stage{position:relative;overflow:hidden}
.tip{position:absolute;left:14px;bottom:14px;background:#ffffffd9;border:1px solid #d8e1ec;border-radius:6px;padding:8px 10px;font-size:12px;color:#617088}
.hoverTip{position:absolute;display:none;pointer-events:none;background:#172033;color:#fff;border-radius:8px;padding:8px 10px;font-size:12px;line-height:1.55;box-shadow:0 10px 24px rgba(0,0,0,.22);max-width:280px;z-index:4}
.legend span{display:inline-block;width:12px;height:12px;margin-right:6px;border-radius:50%}.filters label{display:block;margin:8px 0;color:#24344d}.filters input{margin-right:7px}.count{color:#65748b;font-size:12px}a{color:#0d5fb3;text-decoration:none}a:hover{text-decoration:underline}
@media(max-width:900px){main{grid-template-columns:1fr;height:auto}aside{max-height:360px}.stage{height:680px}}
</style></head><body>
<header><h1>上传数据自动 3D 隧道模型</h1><p>拖动旋转，滚轮缩放；橙色为超挖，红色为欠挖，绿色为正常/未分类。</p></header>
<main><aside>
<div class="card"><b>模型统计</b><div id="stats" class="muted"></div></div>
<button id="reset">重置视图</button><button id="top">俯视</button><button id="front">断面视角</button>
<div class="card filters"><b>点位筛选</b><p class="muted">默认只显示隧道曲面。勾选后才显示对应点位；坐标只在鼠标悬停时出现。</p><label><input id="filterNormal" type="checkbox">正常点位 <span class="count" id="countNormal"></span></label><label><input id="filterOver" type="checkbox">超挖点位 <span class="count" id="countOver"></span></label><label><input id="filterUnder" type="checkbox">欠挖点位 <span class="count" id="countUnder"></span></label></div>
<div class="card legend"><b>图例</b><p><span style="background:#ff9f1c"></span>超挖点位/断面</p><p><span style="background:#d62828"></span>欠挖点位/断面</p><p><span style="background:#2a9d55"></span>正常或未分类</p><p><span style="background:#2673c9"></span>自动生成断面曲面</p></div>
<div class="card muted"><b>输出文件</b><p><a href="uploaded_model.obj" target="_blank">下载 OBJ 模型</a></p><p><a href="manifest.json" target="_blank">查看 manifest.json</a></p></div>
<div class="card muted"><b>质量提示</b><div id="warnings"></div></div>
</aside><section class="stage"><canvas id="view"></canvas><div class="tip">鼠标拖动：旋转　滚轮：缩放；勾选左侧点位后，悬停查看坐标</div><div class="hoverTip" id="hoverTip"></div></section></main>
<script>
const DATA=__DATA__;
const canvas=document.getElementById("view"),ctx=canvas.getContext("2d");
const hoverTip=document.getElementById("hoverTip");
let yaw=-0.9,pitch=0.42,zoom=1,drag=false,last=[0,0],needs=false,drawnPoints=[];
const center=DATA.center, maxRange=Math.max(...DATA.ranges);
function color(s){return s==="under"?"#d62828":s==="over"?"#ff9f1c":s==="normal"?"#2a9d55":"#888"}
function resize(){const r=canvas.parentElement.getBoundingClientRect();canvas.width=r.width*devicePixelRatio;canvas.height=r.height*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);zoom=Math.max(2,Math.min(26,Math.min(canvas.clientWidth/(maxRange*1.5),canvas.clientHeight/(maxRange*1.15))));draw()}
function project(p){let x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2];const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);let xx=x*cy-y*sy,yy=x*sy+y*cy,yz=yy*cp-z*sp,zz=yy*sp+z*cp;return [canvas.clientWidth/2+xx*zoom,canvas.clientHeight/2-yz*zoom,zz]}
function face(points,alpha){ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1])});ctx.closePath();ctx.fillStyle="#2673c9";ctx.globalAlpha=alpha;ctx.fill();ctx.globalAlpha=1}
function line(points){ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1])});ctx.strokeStyle="#174d87";ctx.globalAlpha=.7;ctx.lineWidth=1;ctx.stroke();ctx.globalAlpha=1}
function drawMesh(){const rows=DATA.meshPoints||[];if(rows.length<2)return;const n=rows[0].length,faces=[];for(let s=0;s<rows.length-1;s++){for(let j=0;j<n;j+=2){const p=[rows[s][j],rows[s][(j+1)%n],rows[s+1][(j+1)%n],rows[s+1][j]];faces.push([p.reduce((a,v)=>a+project(v)[2],0)/4,p])}}faces.sort((a,b)=>a[0]-b[0]);faces.forEach(f=>face(f[1],.18));rows.forEach((r,i)=>{if(i%Math.ceil(rows.length/26||1)===0)line(r)})}
function statusLabel(s){return s==="under"?"欠挖":s==="over"?"超挖":"正常"}
function visibleStatus(s){if(s==="under")return document.getElementById("filterUnder").checked;if(s==="over")return document.getElementById("filterOver").checked;return document.getElementById("filterNormal").checked}
function drawPoints(){drawnPoints=[];const pts=(DATA.points||[]).filter(p=>visibleStatus(p.status)).map(p=>[project([p.x,p.y,p.z]),p]).sort((a,b)=>a[0][2]-b[0][2]);for(const [q,p] of pts){const r=p.status==="normal"?3.2:4.8;ctx.beginPath();ctx.arc(q[0],q[1],r,0,Math.PI*2);ctx.fillStyle=color(p.status);ctx.globalAlpha=.92;ctx.fill();ctx.globalAlpha=1;drawnPoints.push({x:q[0],y:q[1],z:q[2],r,p})}}
function draw(){ctx.clearRect(0,0,canvas.clientWidth,canvas.clientHeight);drawMesh();drawPoints()}
function fmt(v){return Number(v).toFixed(3)}
function hideHover(){hoverTip.style.display="none"}
function showHover(e,item){const p=item.p;hoverTip.innerHTML=`<b>${statusLabel(p.status)}</b><br>断面/测点：${p.label||"-"}<br>x：${fmt(p.x)}<br>y：${fmt(p.y)}<br>z：${fmt(p.z)}${p.deviation!=null?`<br>偏差：${fmt(p.deviation)}`:""}`;const rect=canvas.getBoundingClientRect(),maxLeft=Math.max(8,rect.width-300);hoverTip.style.left=Math.min(maxLeft,Math.max(8,e.clientX-rect.left+14))+"px";hoverTip.style.top=Math.max(8,e.clientY-rect.top-12)+"px";hoverTip.style.display="block"}
function updateHover(e){if(drag||!drawnPoints.length){hideHover();return}const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;let hit=null,best=1e9;for(const item of drawnPoints){const d=Math.hypot(item.x-x,item.y-y),limit=Math.max(9,item.r+5);if(d<=limit&&d<best){hit=item;best=d}}if(hit)showHover(e,hit);else hideHover()}
canvas.addEventListener("mousedown",e=>{drag=true;last=[e.clientX,e.clientY];hideHover()});addEventListener("mouseup",()=>drag=false);addEventListener("mousemove",e=>{if(!drag)return;yaw+=(e.clientX-last[0])*0.008;pitch=Math.max(-1.2,Math.min(1.2,pitch+(e.clientY-last[1])*0.008));last=[e.clientX,e.clientY];draw();hideHover()});canvas.addEventListener("mousemove",updateHover);canvas.addEventListener("mouseleave",hideHover);canvas.addEventListener("wheel",e=>{e.preventDefault();zoom*=e.deltaY>0?.9:1.1;draw();hideHover()},{passive:false});
document.getElementById("reset").onclick=()=>{yaw=-.9;pitch=.42;resize()};document.getElementById("top").onclick=()=>{yaw=0;pitch=1.15;draw()};document.getElementById("front").onclick=()=>{yaw=-Math.PI/2;pitch=0;draw()};
document.getElementById("stats").innerHTML=Object.entries(DATA.stats).map(([k,v])=>`<p><b>${k}</b>：${v}</p>`).join("");
document.getElementById("countNormal").textContent=`(${DATA.stats.normalPoints||0})`;document.getElementById("countOver").textContent=`(${DATA.stats.overPoints||0})`;document.getElementById("countUnder").textContent=`(${DATA.stats.underPoints||0})`;
["filterNormal","filterOver","filterUnder"].forEach(id=>document.getElementById(id).addEventListener("change",()=>{hideHover();draw()}));
document.getElementById("warnings").innerHTML=(DATA.warnings||[]).length?DATA.warnings.map(x=>`<p>${x}</p>`).join(""):"<p>未发现阻断性问题。</p>";
addEventListener("resize",resize);resize();
</script></body></html>"""


def write_model_html(path: Path, model: dict) -> None:
    html_text = UPLOAD_VIEWER_TEMPLATE.replace("__DATA__", json.dumps(model, ensure_ascii=False, separators=(",", ":")))
    path.write_text(html_text, encoding="utf-8")


def uploaded_entry_from_manifest(manifest_path: Path) -> dict | None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    batch_id = manifest.get("batch_id") or manifest_path.parent.name
    if not batch_id:
        return None
    model_url = f"/models/uploaded/{batch_id}/uploaded_model.html"
    obj_url = f"/models/uploaded/{batch_id}/uploaded_model.obj"
    manifest_url = f"/models/uploaded/{batch_id}/manifest.json"
    if not (UPLOADED_MODEL_DIR / batch_id / "uploaded_model.html").is_file():
        return None
    stats = manifest.get("model_stats") or {}
    saved_files = manifest.get("saved_files") or []
    first_file = saved_files[0].get("name") if saved_files and isinstance(saved_files[0], dict) else ""
    name = manifest.get("display_name") or manifest.get("tunnel_name") or f"上传模型 {first_file or batch_id}"
    return {
        "id": f"uploaded:{batch_id}",
        "batch_id": batch_id,
        "name": name,
        "source_tunnel_id": manifest.get("tunnel_id") or "uploaded",
        "created_at": manifest.get("created_at") or int(time.time()),
        "model_url": model_url,
        "obj_url": obj_url,
        "manifest_url": manifest_url,
        "recognized_records": manifest.get("recognized_records", 0),
        "model_stats": stats,
        "warnings": manifest.get("warnings") or [],
        "saved_files": saved_files,
    }


def load_upload_registry() -> list[dict]:
    entries: list[dict] = []
    if UPLOAD_REGISTRY.exists():
        try:
            loaded = json.loads(UPLOAD_REGISTRY.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                entries = [item for item in loaded if isinstance(item, dict) and item.get("batch_id")]
        except Exception:
            entries = []
    by_batch = {item["batch_id"]: item for item in entries if item.get("batch_id")}
    for manifest_path in sorted(UPLOADED_MODEL_DIR.glob("*/manifest.json")):
        entry = uploaded_entry_from_manifest(manifest_path)
        if entry and entry["batch_id"] not in by_batch:
            by_batch[entry["batch_id"]] = entry
    result = list(by_batch.values())
    result.sort(key=lambda item: int(item.get("created_at") or 0), reverse=True)
    return result


def save_upload_registry(entries: list[dict]) -> None:
    PLATFORM_DIR.mkdir(parents=True, exist_ok=True)
    tmp = UPLOAD_REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(UPLOAD_REGISTRY)


def register_uploaded_tunnel(entry: dict) -> None:
    entries = load_upload_registry()
    entries = [item for item in entries if item.get("batch_id") != entry.get("batch_id")]
    entries.insert(0, entry)
    save_upload_registry(entries)


def rename_uploaded_tunnel(batch_id: str, name: str) -> tuple[dict, int]:
    batch_id = safe_filename(batch_id)
    name = str(name or "").strip()
    if not batch_id or not name:
        return {"error": "bad_request", "message": "缺少批次号或新名称。"}, 400
    entries = load_upload_registry()
    found = None
    for item in entries:
        if item.get("batch_id") == batch_id:
            item["name"] = name[:80]
            found = item
            break
    if not found:
        return {"error": "not_found", "message": "没有找到对应上传批次。"}, 404
    manifest_path = UPLOADED_MODEL_DIR / batch_id / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["display_name"] = name[:80]
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    save_upload_registry(entries)
    return {"status": "ok", "message": "隧道名称已更新。", "entry": found}, 200


def delete_uploaded_tunnel(batch_id: str) -> tuple[dict, int]:
    batch_id = safe_filename(batch_id)
    if not batch_id:
        return {"error": "bad_request", "message": "缺少批次号。"}, 400
    entries = load_upload_registry()
    matched = [item for item in entries if item.get("batch_id") == batch_id]
    if not matched:
        return {"error": "not_found", "message": "没有找到对应上传批次。"}, 404
    model_dir = (UPLOADED_MODEL_DIR / batch_id).resolve()
    upload_dir = (UPLOAD_DIR / batch_id).resolve()
    allowed_model_root = UPLOADED_MODEL_DIR.resolve()
    allowed_upload_root = UPLOAD_DIR.resolve()
    removed = []
    for target, allowed in ((model_dir, allowed_model_root), (upload_dir, allowed_upload_root)):
        try:
            target.relative_to(allowed)
        except ValueError:
            return {"error": "unsafe_path", "message": "删除路径校验失败。"}, 500
        if target.exists():
            shutil.rmtree(target)
            removed.append(str(target))
    entries = [item for item in entries if item.get("batch_id") != batch_id]
    save_upload_registry(entries)
    return {"status": "ok", "message": "上传隧道已删除。", "batch_id": batch_id, "removed": removed}, 200


def handle_upload_package(content_type: str, body: bytes) -> tuple[dict, int]:
    if "multipart/form-data" not in content_type:
        return {"error": "bad_content_type", "message": "请使用 multipart/form-data 上传文件。"}, 400
    fields, files = parse_multipart_form(content_type, body)
    if not files:
        return {"error": "no_files", "message": "没有收到文件。请拖拽或选择 CSV/JSON/XYZ/TXT/ZIP 数据包。"}, 400
    batch_id = time.strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    tunnel_id = fields.get("tunnel_id") or "uploaded"
    requested_name = fields.get("tunnel_name") or "上传隧道"
    display_name = f"{requested_name}（上传 {batch_id[-8:]}）"
    batch_dir = UPLOAD_DIR / batch_id
    raw_dir = batch_dir / "raw"
    model_dir = UPLOADED_MODEL_DIR / batch_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []
    records: list[dict] = []
    warnings: list[str] = []
    for file_info in files:
        filename = file_info["filename"]
        data = file_info["data"]
        if len(data) > MAX_UPLOAD_FILE_BYTES:
            warnings.append(f"{filename}: 文件超过单文件限制，已跳过解析。")
            continue
        path = raw_dir / filename
        path.write_bytes(data)
        saved_files.append({"name": filename, "bytes": len(data), "content_type": file_info.get("content_type")})
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    members = [m for m in zf.infolist() if not m.is_dir()][:MAX_ZIP_MEMBERS]
                    for member in members:
                        member_name = safe_filename(member.filename)
                        member_data = zf.read(member)
                        extracted = raw_dir / "unzipped" / member_name
                        extracted.parent.mkdir(parents=True, exist_ok=True)
                        extracted.write_bytes(member_data)
                        parsed, parse_warnings = parse_supported_file(extracted, member_data)
                        records.extend(parsed)
                        warnings.extend(parse_warnings)
            except Exception as exc:
                warnings.append(f"{filename}: ZIP 解压失败 - {exc}")
        else:
            parsed, parse_warnings = parse_supported_file(path, data)
            records.extend(parsed)
            warnings.extend(parse_warnings)
    model, model_warnings = build_model_payload(records, tunnel_id, batch_id)
    warnings.extend(model_warnings)
    manifest = {
        "batch_id": batch_id,
        "tunnel_id": tunnel_id,
        "tunnel_name": requested_name,
        "display_name": display_name,
        "created_at": int(time.time()),
        "saved_files": saved_files,
        "recognized_records": len(records),
        "model_stats": model["stats"],
        "warnings": warnings,
        "required_columns": {
            "precise_3d": "station/x + y + z + status/deviation",
            "concept_model": "station + over_area/under_area + max_over/max_under",
        },
    }
    (model_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_obj(model_dir / "uploaded_model.obj", model)
    write_model_html(model_dir / "uploaded_model.html", model)
    entry = uploaded_entry_from_manifest(model_dir / "manifest.json") or {
        "id": f"uploaded:{batch_id}",
        "batch_id": batch_id,
        "name": display_name,
        "source_tunnel_id": tunnel_id,
        "created_at": manifest["created_at"],
        "model_url": f"/models/uploaded/{batch_id}/uploaded_model.html",
        "obj_url": f"/models/uploaded/{batch_id}/uploaded_model.obj",
        "manifest_url": f"/models/uploaded/{batch_id}/manifest.json",
        "recognized_records": len(records),
        "model_stats": model["stats"],
        "warnings": warnings,
        "saved_files": saved_files,
    }
    register_uploaded_tunnel(entry)
    message = "上传成功，已生成 3D 模型和超欠挖标注。"
    if warnings:
        message += " 部分数据存在质量提示，请查看 manifest。"
    return (
        {
            "status": "ok",
            "message": message,
            "batch_id": batch_id,
            "tunnel_id": tunnel_id,
            "recognized_records": len(records),
            "model_stats": model["stats"],
            "warnings": warnings[:20],
            "model_url": f"/models/uploaded/{batch_id}/uploaded_model.html",
            "obj_url": f"/models/uploaded/{batch_id}/uploaded_model.obj",
            "manifest_url": f"/models/uploaded/{batch_id}/manifest.json",
            "entry": entry,
        },
        200,
    )


def compact_tunnel_context(tunnel_id: str | None = None) -> str:
    try:
        data = load_json_file(PLATFORM_DIR / "control_data.json")
    except Exception as exc:
        return f"平台数据暂不可用：{exc}"
    tunnels = data.get("tunnels", {}) if isinstance(data, dict) else {}
    selected = tunnels.get(tunnel_id or "") or tunnels.get("east") or next(iter(tunnels.values()), {})
    parts: list[str] = []
    parts.append(f"当前隧道：{selected.get('name', '未知')}")
    if selected.get("description"):
        parts.append(f"说明：{selected['description']}")
    overview = selected.get("overview") or {}
    if overview:
        parts.append("概况：" + "；".join(f"{k}={v}" for k, v in list(overview.items())[:10]))
    cards = selected.get("cards") or {}
    if cards:
        parts.append("指标：" + "；".join(f"{k}={v}" for k, v in list(cards.items())[:12]))
    overbreak = selected.get("overbreak") or {}
    audit = overbreak.get("underbreakAudit")
    if audit:
        parts.append(
            "欠挖核对："
            f"{audit.get('message', '')} "
            f"欠挖断面数={audit.get('underbreakCount')}, "
            f"最大欠挖面积={audit.get('maxUnderbreakArea')}㎡, "
            f"最大欠挖深度={audit.get('maxUnderbreakDepth')}m。"
        )
    top_area = overbreak.get("topArea") or []
    if top_area:
        parts.append(
            "超挖面积较大断面："
            + "；".join(f"{r.get('桩号')} {r.get('超挖面积_㎡')}㎡" for r in top_area[:6])
        )
    top_depth = overbreak.get("topDepth") or []
    if top_depth:
        parts.append(
            "最大超挖深度较大断面："
            + "；".join(f"{r.get('桩号')} {r.get('最大超挖_m')}m" for r in top_depth[:6])
        )
    alerts = selected.get("alerts") or []
    if alerts:
        parts.append(
            "风险预警摘要："
            + "；".join(
                f"{a.get('level')} {a.get('category')} {a.get('item')} {a.get('value')} {a.get('threshold')}"
                for a in alerts[:10]
            )
        )
    monitoring = selected.get("monitoring") or {}
    tops = monitoring.get("tops") or {}
    monitor_bits = []
    for name, rows in tops.items():
        if rows:
            row = rows[0]
            value = row.get("本期收敛(mm)", row.get("本期沉降(mm)", ""))
            monitor_bits.append(f"{name}: {row.get('测点')} {value}mm")
    if monitor_bits:
        parts.append("监控量测最大值：" + "；".join(monitor_bits))
    notes = selected.get("notes") or []
    if notes:
        parts.append("平台说明：" + "；".join(notes[:4]))
    return "\n".join(parts)[:12000]


def normalize_chat_history(raw_history) -> list[dict]:
    if not isinstance(raw_history, list):
        return []
    normalized = []
    total_chars = 0
    for item in reversed(raw_history[-BRAIN_HISTORY_LIMIT:]):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if total_chars >= BRAIN_HISTORY_TOTAL_LIMIT:
            break
        content = content[: min(BRAIN_HISTORY_CONTENT_LIMIT, BRAIN_HISTORY_TOTAL_LIMIT - total_chars)]
        total_chars += len(content)
        tunnel_name = str(item.get("tunnel_name") or item.get("tunnel_id") or "当前隧道").strip()
        normalized.append(
            {
                "role": role,
                "content": content,
                "tunnel_name": tunnel_name[:80],
            }
        )
    return list(reversed(normalized))


def retrieve_rag_context(question: str) -> dict:
    if not BRAIN_RAG_ENABLED:
        return {"available": False, "context": "", "sources": [], "status": "disabled"}
    try:
        from rag.rag_core import retrieve_for_prompt

        payload = retrieve_for_prompt(question, top_k=BRAIN_RAG_TOP_K, max_context_chars=BRAIN_RAG_CONTEXT_CHARS)
        payload["status"] = "ok" if payload.get("context") else "empty"
        return payload
    except Exception as exc:
        return {"available": False, "context": "", "sources": [], "status": "error", "error": str(exc)[:500]}


def append_rag_sources(answer: str, sources: list[dict]) -> str:
    if not answer or not sources:
        return answer
    if any(str(source.get("source_file") or "") in answer for source in sources):
        return answer
    lines = []
    for source in sources[:3]:
        label = source.get("source") or source.get("source_file") or ""
        if label:
            lines.append(f"- {label}")
    if not lines:
        return answer
    return answer.rstrip() + "\n\n资料来源：\n" + "\n".join(lines)


def call_local_qwen(question: str, tunnel_id: str | None = None, history=None) -> dict:
    context = compact_tunnel_context(tunnel_id)
    rag_payload = retrieve_rag_context(question)
    rag_context = rag_payload.get("context", "")
    chat_history = normalize_chat_history(history)
    system_prompt = (
        "你是隧道智慧管控平台的工程助手。请基于给定平台数据回答，"
        "如果数据中没有依据，要明确说明缺少数据，不能编造。"
        "回答要简洁、工程化，优先给出断面、测点、风险和建议。"
        "你可以参考最近对话上下文理解追问，但平台数据优先级高于对话历史。"
        "若提供了RAG知识库检索结果，可以用它解释工程原理和施工建议，但其优先级低于平台实时数据、项目文件和现行规范。"
        "当答案使用RAG资料时，末尾请给出“资料来源”。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"平台数据上下文：\n{context}"},
    ]
    if rag_context:
        messages.append({"role": "system", "content": rag_context})
    for item in chat_history:
        messages.append(
            {
                "role": item["role"],
                "content": f"[{item['tunnel_name']}] {item['content']}",
            }
        )
    messages.append({"role": "user", "content": question})
    payload = {
        "model": BRAIN_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": BRAIN_MAX_TOKENS,
    }
    req = urllib.request.Request(
        f"{BRAIN_API_BASE}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=brain_headers(content_type=True),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=BRAIN_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        answer = append_rag_sources(answer, rag_payload.get("sources", []))
        return {
            "ok": True,
            "provider": BRAIN_PROVIDER,
            "api_base": BRAIN_API_BASE,
            "model": BRAIN_MODEL,
            "answer": answer or "本地 Qwen 已返回，但内容为空。",
            "history_window": len(chat_history),
            "rag_status": rag_payload.get("status"),
            "rag_sources": rag_payload.get("sources", []),
        }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        return {"ok": False, "error": f"HTTP {exc.code}: {detail}", "api_base": BRAIN_API_BASE, "model": BRAIN_MODEL}
    except Exception as exc:
        return {"ok": False, "error": friendly_qwen_error(exc), "api_base": BRAIN_API_BASE, "model": BRAIN_MODEL}


def friendly_qwen_error(exc: Exception) -> str:
    raw = str(exc)
    if "Connection refused" in raw or "Errno 111" in raw:
        return f"本地 Qwen 推理服务未启动或不可达：{BRAIN_API_BASE}"
    if "timed out" in raw.lower() or "timeout" in raw.lower():
        return f"本地 Qwen 响应超时：{BRAIN_API_BASE}"
    return raw


def local_qwen_status() -> dict:
    req = urllib.request.Request(f"{BRAIN_API_BASE}/models", headers=brain_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        models = [item.get("id") for item in data.get("data", []) if item.get("id")]
        return {"ok": True, "provider": BRAIN_PROVIDER, "api_base": BRAIN_API_BASE, "model": BRAIN_MODEL, "available_models": models}
    except Exception as exc:
        return {"ok": False, "provider": BRAIN_PROVIDER, "api_base": BRAIN_API_BASE, "model": BRAIN_MODEL, "error": friendly_qwen_error(exc)}


class TunnelHandler(BaseHTTPRequestHandler):
    server_version = "TunnelControl/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def session_token(self) -> str | None:
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_user(self) -> sqlite3.Row | None:
        return get_user_by_session(self.session_token())

    def send_bytes(self, body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8", headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        origin = self.headers.get("Origin", "").rstrip("/")
        if origin and origin in TUNNEL_CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        origin = self.headers.get("Origin", "").rstrip("/")
        if not parsed.path.startswith("/api/") or origin not in TUNNEL_CORS_ORIGINS:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def redirect(self, location: str, headers: dict | None = None) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def require_login(self) -> sqlite3.Row | None:
        user = self.current_user()
        if user:
            return user
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.json_response({"error": "not_authenticated"}, status=401)
        else:
            self.redirect("/login")
        return None

    def render_login(self, error: str = "") -> None:
        message = f"<div class='err'>{html.escape(error)}</div>" if error else ""
        self.send_bytes(LOGIN_HTML.replace("{error}", message).encode("utf-8"))

    def json_response(self, payload: object, status: int = 200) -> None:
        self.send_bytes(
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.json_response({"ok": True, "time": now()})
            return
        if parsed.path == "/login":
            if self.current_user():
                self.redirect("/")
            else:
                self.render_login()
            return
        if parsed.path == "/logout":
            clear_session(self.session_token())
            self.redirect("/login", {"Set-Cookie": cookie_header("", max_age=0)})
            return
        if parsed.path.startswith("/api/"):
            self.handle_api(parsed.path)
            return
        user = self.require_login()
        if not user:
            return
        if parsed.path == "/":
            self.redirect("/platform/index.html")
            return
        path = safe_file_path(self.path)
        if not path:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix.lower() in {".html", ".json", ".csv", ".txt"}:
            content_type += "; charset=utf-8"
        self.send_bytes(path.read_bytes(), content_type=content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_post_api(parsed.path)
            return
        if parsed.path != "/login":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 4096:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        fields = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        username = fields.get("username", [""])[0].strip()
        password = fields.get("password", [""])[0]
        user = authenticate(username, password)
        if not user:
            self.render_login("账号或密码错误")
            return
        token = create_session(user["id"])
        self.redirect("/", {"Set-Cookie": cookie_header(token)})

    def handle_post_api(self, path: str) -> None:
        user = self.require_login()
        if not user:
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_UPLOAD_BYTES:
            self.json_response({"error": "request_too_large", "message": "数据包超过当前原型接口限制。"}, status=413)
            return
        body = self.rfile.read(length) if length else b""
        if path == "/api/brain/chat":
            question = ""
            tunnel_id = None
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
                question = str(payload.get("question", "")).strip()
                tunnel_id = payload.get("tunnel_id")
                history = payload.get("history") or []
            except Exception:
                history = []
            if not question:
                self.json_response({"error": "empty_question", "message": "请输入问题。"}, status=400)
                return
            result = call_local_qwen(question, tunnel_id=tunnel_id, history=history)
            if result.get("ok"):
                self.json_response(
                    {
                        "status": "ok",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "answer": result.get("answer"),
                        "message": result.get("answer"),
                        "history_window": result.get("history_window", 0),
                        "rag_status": result.get("rag_status"),
                        "rag_sources": result.get("rag_sources", []),
                    }
                )
            else:
                self.json_response(
                    {
                        "status": "error",
                        "message": "本地 Qwen 调用失败，平台已收到问题但暂时无法生成回答。",
                        "error": result.get("error"),
                        "api_base": result.get("api_base"),
                        "model": result.get("model"),
                    },
                    status=502,
                )
            return
        if path == "/api/packages/upload":
            result, status = handle_upload_package(self.headers.get("Content-Type", ""), body)
            self.json_response(result, status=status)
            return
        if path == "/api/uploaded-tunnels/rename":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            result, status = rename_uploaded_tunnel(str(payload.get("batch_id", "")), str(payload.get("name", "")))
            self.json_response(result, status=status)
            return
        if path == "/api/uploaded-tunnels/delete":
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except Exception:
                payload = {}
            result, status = delete_uploaded_tunnel(str(payload.get("batch_id", "")))
            self.json_response(result, status=status)
            return
        if path.startswith("/api/tunnels/") and path.endswith("/build-model"):
            self.json_response(
                {
                    "status": "reserved",
                    "message": "自动建模已在 POST /api/packages/upload 中同步触发。后续版本会把该接口升级为异步重建指定批次。",
                    "job_id": None,
                }
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_api(self, path: str) -> None:
        user = self.require_login()
        if not user:
            return
        if path == "/api/me":
            self.json_response({"username": user["username"], "role": user["role"], "last_login": user["last_login"]})
            return
        if path == "/api/brain/status":
            self.json_response(local_qwen_status())
            return
        if path == "/api/control-data":
            self.json_response(load_json_file(PLATFORM_DIR / "control_data.json"))
            return
        if path == "/api/uploaded-tunnels":
            self.json_response({"status": "ok", "items": load_upload_registry()})
            return
        if path == "/api/summary":
            self.json_response(load_json_file(ROOT / "structured" / "summary.json"))
            return
        if path == "/api/alerts":
            data = load_json_file(PLATFORM_DIR / "control_data.json")
            self.json_response(data.get("alerts", []))
            return
        if path == "/api/resources":
            data = load_json_file(PLATFORM_DIR / "control_data.json")
            self.json_response(data.get("resources", []))
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tunnel control platform login server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()
    init_db()
    if args.init_only:
        print(f"database initialized: {DB_PATH}")
        if INITIAL_ADMIN.exists():
            print(f"initial admin file: {INITIAL_ADMIN}")
        return
    server = ThreadingHTTPServer((args.host, args.port), TunnelHandler)
    print(f"Tunnel control platform running on http://{args.host}:{args.port}")
    print(f"Root: {ROOT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
