# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "structured"
OUT = ROOT / "platform"
ASSETS = OUT / "assets"
EAST_SECTION_MODEL = ROOT / "models" / "east_pdf_section_model" / "east_pdf_section_model.json"


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def top_rows(rows: list[dict], key: str, n: int = 10, absolute: bool = False) -> list[dict]:
    return sorted(rows, key=lambda r: abs(number(r.get(key))) if absolute else number(r.get(key)), reverse=True)[:n]


def sample_evenly(items: list, limit: int) -> list:
    if not items or len(items) <= limit:
        return items or []
    if limit <= 1:
        return [items[0]]
    step = (len(items) - 1) / (limit - 1)
    return [items[round(i * step)] for i in range(limit)]


def load_section_model() -> dict | None:
    if not EAST_SECTION_MODEL.exists():
        return None
    return json.loads(EAST_SECTION_MODEL.read_text(encoding="utf-8"))


def section_profiles(rows: list[dict], model: dict | None = None) -> list[dict]:
    model_by_station: dict[str, dict] = {}
    if model:
        curves = model.get("curves", [])
        for idx, sec in enumerate(model.get("sections", [])):
            station = sec.get("station")
            if not station:
                continue
            test_points = [
                {
                    "y": number(p[0]),
                    "z": number(p[1]),
                    "size": int(number(p[2])) if len(p) > 2 else 1,
                    "status": "PDF测试位点",
                }
                for p in sample_evenly(sec.get("test_points") or [], 90)
            ]
            model_by_station[station] = {
                "page": sec.get("page"),
                "index": sec.get("index"),
                "chainageOffsetM": number(sec.get("chainage_offset_m")),
                "valid": bool(sec.get("valid")),
                "extracted": bool(sec.get("extracted")),
                "curve": sample_evenly(curves[idx], 120) if idx < len(curves) else [],
                "testPoints": test_points,
                "testPointCount": len(sec.get("test_points") or []),
                "quality": sec.get("quality") or {},
            }
    profiles = []
    for idx, row in enumerate(rows):
        station = row["桩号"]
        model_info = model_by_station.get(station, {})
        under_area = number(row["欠挖面积_㎡"])
        max_under = number(row["最大欠挖_m"])
        test_count = int(model_info.get("testPointCount") or 0)
        profiles.append(
            {
                "station": station,
                "index": model_info.get("index", idx),
                "page": model_info.get("page"),
                "chainageOffsetM": model_info.get("chainageOffsetM", idx),
                "overArea": number(row["超挖面积_㎡"]),
                "underArea": under_area,
                "maxOver": number(row["最大超挖_m"]),
                "maxUnder": max_under,
                "avgLinearOver": number(row["平均线性超挖_m"]),
                "designArea": number(row["设计断面面积_㎡"]),
                "analysisArea": number(row["分析区域面积_㎡"]),
                "measuredArea": number(row["测量面积_㎡"]),
                "curve": model_info.get("curve", []),
                "testPoints": model_info.get("testPoints", []),
                "testPointCount": test_count,
                "statusCounts": {
                    "欠挖": 1 if (under_area > 0 or max_under > 0) else 0,
                    "超挖识别点": test_count,
                    "正常": 0,
                },
                "valid": bool(model_info.get("valid")),
                "extracted": bool(model_info.get("extracted")),
                "quality": model_info.get("quality", {}),
                "sourceNote": (
                    "该断面源表欠挖面积与最大欠挖均为 0，当前没有可绘制的欠挖点位。"
                    if under_area == 0 and max_under == 0
                    else "该断面存在欠挖统计值；需要原始测点分类数据后才能精确定位欠挖点。"
                ),
            }
        )
    return profiles


def severity(score: int) -> str:
    return {3: "红色", 2: "橙色", 1: "黄色", 0: "正常"}[score]


def add_alert(alerts: list[dict], score: int, category: str, item: str, value: str, threshold: str, advice: str) -> None:
    alerts.append(
        {
            "level": severity(score),
            "score": score,
            "category": category,
            "item": item,
            "value": value,
            "threshold": threshold,
            "advice": advice,
        }
    )


def overbreak_alerts(rows: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for row in rows:
        station = row["桩号"]
        area = number(row["超挖面积_㎡"])
        under = number(row["欠挖面积_㎡"])
        max_over = number(row["最大超挖_m"])
        max_under = number(row["最大欠挖_m"])
        if area >= 6.0:
            add_alert(alerts, 2, "超欠挖", station, f"{area:.3f} ㎡", "超挖面积 >= 6.0 ㎡", "复核该断面开挖轮廓，检查钻爆参数和初支喷混凝土消耗。")
        elif area >= 5.0:
            add_alert(alerts, 1, "超欠挖", station, f"{area:.3f} ㎡", "超挖面积 >= 5.0 ㎡", "纳入连续区段跟踪，观察相邻断面是否同步偏大。")
        if under > 0:
            add_alert(alerts, 2, "欠挖", station, f"{under:.3f} ㎡", "欠挖面积 > 0 ㎡", "欠挖需要重点复核，必要时安排处理。")
        if max_over >= 0.60:
            add_alert(alerts, 2, "超欠挖", station, f"{max_over:.3f} m", "最大超挖 >= 0.60 m", "核查局部超挖位置，必要时结合断面图复测。")
        elif max_over >= 0.50:
            add_alert(alerts, 1, "超欠挖", station, f"{max_over:.3f} m", "最大超挖 >= 0.50 m", "关注该断面局部轮廓控制。")
        if max_under > 0:
            add_alert(alerts, 2, "欠挖", station, f"{max_under:.3f} m", "最大欠挖 > 0 m", "核对该断面的欠挖位置与断面图。")
    alerts.sort(key=lambda x: (-x["score"], x["category"], x["item"]))
    return alerts


def monitoring_alerts(surface: list[dict], crown: list[dict], convergence: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for row in surface:
        current = number(row["本期沉降(mm)"])
        rate = number(row["平均变化量(mm/d)"])
        if current >= 3.0:
            add_alert(alerts, 1, "地表下沉", row["测点"], f"{current:.2f} mm", "本期沉降 >= 3.0 mm", "关注地表沉降测线，结合降雨、施工步距和掌子面位置复核。")
        if rate >= 0.45:
            add_alert(alerts, 1, "地表下沉", row["测点"], f"{rate:.2f} mm/d", "平均变化量 >= 0.45 mm/d", "提高该测点短期复测频率。")
    for row in crown:
        current = number(row["本期沉降(mm)"])
        rate = number(row["平均变化量(mm/d)"])
        if current >= 15.0:
            add_alert(alerts, 3, "拱顶下沉", row["测点"], f"{current:.2f} mm", "本期沉降 >= 15.0 mm", "立即复核测点和初支状态，必要时组织现场会商。")
        elif current >= 10.0:
            add_alert(alerts, 2, "拱顶下沉", row["测点"], f"{current:.2f} mm", "本期沉降 >= 10.0 mm", "重点跟踪该断面拱顶变形，核查支护闭合情况。")
        if rate >= 2.0:
            add_alert(alerts, 2, "拱顶下沉", row["测点"], f"{rate:.2f} mm/d", "平均变化量 >= 2.0 mm/d", "关注变形速率，建议缩短观测间隔。")
    for row in convergence:
        current = number(row["本期收敛(mm)"])
        rate = abs(number(row["平均变化量(mm/d)"]))
        if abs(current) >= 10.0:
            add_alert(alerts, 3, "周边收敛", row["测点"], f"{current:.2f} mm", "|本期收敛| >= 10.0 mm", "复核该收敛线两端测点，检查断面支护变形。")
        elif abs(current) >= 8.0:
            add_alert(alerts, 2, "周边收敛", row["测点"], f"{current:.2f} mm", "|本期收敛| >= 8.0 mm", "重点跟踪该收敛线后续变化。")
        if rate >= 1.5:
            add_alert(alerts, 2, "周边收敛", row["测点"], f"{rate:.2f} mm/d", "|平均变化量| >= 1.5 mm/d", "关注变形速率异常，检查是否存在测量或施工扰动。")
    alerts.sort(key=lambda x: (-x["score"], x["category"], x["item"]))
    return alerts


def alert_stats(alerts: list[dict]) -> dict:
    return {
        "byCategory": dict(Counter(a["category"] for a in alerts)),
        "byLevel": dict(Counter(a["level"] for a in alerts)),
    }


def overbreak_block(rows: list[dict], profiles: list[dict] | None = None) -> dict:
    if not rows:
        return {
            "rows": [],
            "series": [],
            "underbreakSeries": [],
            "maxDepthSeries": [],
            "maxUnderDepthSeries": [],
            "sectionProfiles": [],
            "topArea": [],
            "topDepth": [],
            "underbreakAudit": {
                "checked": True,
                "message": "当前隧道暂未接入超欠挖成果。",
                "underbreakCount": 0,
                "maxUnderbreakArea": 0,
                "maxUnderbreakDepth": 0,
            },
        }
    under_values = [number(r["欠挖面积_㎡"]) for r in rows]
    under_depths = [number(r["最大欠挖_m"]) for r in rows]
    under_count = sum(1 for v in under_values if v > 0)
    if under_count == 0:
        message = "已核对 PDF 汇总表和逐断面数据：所有断面的欠挖面积与最大欠挖均为 0。当前不是漏提取，而是源数据记录为无欠挖。"
    else:
        message = f"已核对：存在 {under_count} 个欠挖断面，请重点查看欠挖趋势和明细表。"
    return {
        "rows": rows,
        "series": [{"x": r["桩号"], "y": number(r["超挖面积_㎡"])} for r in rows],
        "underbreakSeries": [{"x": r["桩号"], "y": number(r["欠挖面积_㎡"])} for r in rows],
        "maxDepthSeries": [{"x": r["桩号"], "y": number(r["最大超挖_m"])} for r in rows],
        "maxUnderDepthSeries": [{"x": r["桩号"], "y": number(r["最大欠挖_m"])} for r in rows],
        "sectionProfiles": profiles or section_profiles(rows),
        "topArea": top_rows(rows, "超挖面积_㎡"),
        "topDepth": top_rows(rows, "最大超挖_m"),
        "underbreakAudit": {
            "checked": True,
            "message": message,
            "underbreakCount": under_count,
            "maxUnderbreakArea": max(under_values) if under_values else 0,
            "maxUnderbreakDepth": max(under_depths) if under_depths else 0,
        },
    }


def monitoring_block(surface: list[dict], crown: list[dict], convergence: list[dict]) -> dict:
    return {
        "surface": surface,
        "crown": crown,
        "convergence": convergence,
        "series": {
            "地表下沉": [{"x": r["测点"], "y": number(r["本期沉降(mm)"])} for r in surface],
            "拱顶下沉": [{"x": r["测点"], "y": number(r["本期沉降(mm)"])} for r in crown],
            "周边收敛": [{"x": r["测点"], "y": number(r["本期收敛(mm)"])} for r in convergence],
        },
        "tops": {
            "地表下沉": top_rows(surface, "本期沉降(mm)"),
            "拱顶下沉": top_rows(crown, "本期沉降(mm)"),
            "周边收敛": top_rows(convergence, "本期收敛(mm)", absolute=True),
        },
    }


def max_deformation_label(surface: list[dict], crown: list[dict], convergence: list[dict]) -> str:
    values: list[tuple[float, str]] = []
    for row in surface:
        values.append((abs(number(row["本期沉降(mm)"])), f"{row['测点']} {number(row['本期沉降(mm)']):.2f} mm"))
    for row in crown:
        values.append((abs(number(row["本期沉降(mm)"])), f"{row['测点']} {number(row['本期沉降(mm)']):.2f} mm"))
    for row in convergence:
        values.append((abs(number(row["本期收敛(mm)"])), f"{row['测点']} {number(row['本期收敛(mm)']):.2f} mm"))
    return max(values, key=lambda x: x[0])[1] if values else "暂无"


def build_tunnel_notes(overbreak: list[dict], surface: list[dict], crown: list[dict], convergence: list[dict]) -> list[str]:
    notes = []
    notes.append("已按隧道名称分组管理，可通过顶部下拉框切换。")
    if overbreak:
        notes.append("已接入超欠挖断面成果，可查看超挖面积、欠挖核对、最大超挖深度和明细表。")
    else:
        notes.append("暂未接入该隧道的超欠挖断面成果。")
    if surface or crown or convergence:
        notes.append("已接入监控量测周报，可查看地表下沉、拱顶下沉、周边收敛和预警。")
    else:
        notes.append("暂未接入该隧道的监控量测周报。")
    notes.append("当前阈值为第一版原型规则，正式使用前应按项目监控量测方案和规范要求调整。")
    return notes


def make_tunnel(
    *,
    tunnel_id: str,
    name: str,
    description: str,
    overview: dict,
    overbreak: list[dict] | None = None,
    surface: list[dict] | None = None,
    crown: list[dict] | None = None,
    convergence: list[dict] | None = None,
    section_profile_data: list[dict] | None = None,
    resources: list[dict] | None = None,
    model_url: str = "../models/plotly_tunnel_3d.html",
) -> dict:
    overbreak = overbreak or []
    surface = surface or []
    crown = crown or []
    convergence = convergence or []
    alerts = overbreak_alerts(overbreak) + monitoring_alerts(surface, crown, convergence)
    alerts.sort(key=lambda x: (-x["score"], x["category"], x["item"]))
    over_values = [number(r["超挖面积_㎡"]) for r in overbreak]
    under_values = [number(r["欠挖面积_㎡"]) for r in overbreak]
    monitor_count = len(surface) + len(crown) + len(convergence)
    cards = {
        "超欠挖断面": len(overbreak),
        "监控量测记录": monitor_count,
        "预警条目": len(alerts),
        "最高预警等级": alerts[0]["level"] if alerts else "正常",
        "最大超挖面积": f"{max(over_values):.3f} ㎡" if over_values else "暂无",
        "最大欠挖面积": f"{max(under_values):.3f} ㎡" if under_values else "暂无",
        "欠挖断面数": sum(1 for v in under_values if v > 0),
        "最大变形值": max_deformation_label(surface, crown, convergence),
    }
    return {
        "id": tunnel_id,
        "name": name,
        "description": description,
        "overview": overview,
        "cards": cards,
        "alerts": alerts,
        "alertStats": alert_stats(alerts),
        "overbreak": overbreak_block(overbreak, section_profile_data),
        "monitoring": monitoring_block(surface, crown, convergence),
        "resources": resources or [],
        "modelUrl": model_url,
        "notes": build_tunnel_notes(overbreak, surface, crown, convergence),
    }


def build_all_tunnel(east: dict, douli: dict) -> dict:
    return make_tunnel(
        tunnel_id="all",
        name="全部隧道",
        description="汇总展示当前已接入的所有隧道数据。不同隧道的数据会在各自页面中分开管理。",
        overview={"数据对象": "东安隧道超欠挖 + 豆里冲隧道监控量测", "说明": "不同来源数据已按隧道拆分，可在顶部切换。"},
        overbreak=east["overbreak"]["rows"],
        surface=douli["monitoring"]["surface"],
        crown=douli["monitoring"]["crown"],
        convergence=douli["monitoring"]["convergence"],
        section_profile_data=east["overbreak"].get("sectionProfiles", []),
        resources=[
            {"name": "平台数据 JSON", "path": "control_data.json"},
            {"name": "Plotly 3D 综合模型", "path": "../models/plotly_tunnel_3d.html"},
        ],
    )


def build_payload() -> dict:
    overbreak = read_csv("overbreak_underbreak_sections.csv")
    surface = read_csv("weekly_surface_settlement.csv")
    crown = read_csv("weekly_crown_settlement.csv")
    convergence = read_csv("weekly_peripheral_convergence.csv")
    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    east_section_profiles = section_profiles(overbreak, load_section_model())

    east_summary = summary["超欠挖成果表"]
    weekly_summary = summary["周报"]
    east = make_tunnel(
        tunnel_id="east",
        name="东安隧道斜井大里程方向",
        description="超欠挖成果表对象，当前接入逐米断面检测统计和 PDF 切面 3D 模型。",
        overview={
            "来源": "20260518XJDA.pdf",
            "测量时间": east_summary["测量时间"],
            "里程范围": f"{east_summary['起始桩号']} 至 {east_summary['终止桩号']}",
            "断面数量": east_summary["断面数量"],
            "平均超挖面积": f"{east_summary['平均超挖面积_㎡']} ㎡",
            "平均欠挖面积": f"{east_summary['平均欠挖面积_㎡']} ㎡",
            "欠挖核对": "PDF 汇总表显示最大欠挖面积 0.000 ㎡，逐断面欠挖面积均为 0。",
        },
        overbreak=overbreak,
        section_profile_data=east_section_profiles,
        resources=[
            {"name": "东安 PDF 切面 3D 模型", "path": "../models/east_pdf_section_model/east_pdf_section_3d.html"},
            {"name": "东安 PDF 切面 OBJ", "path": "../models/east_pdf_section_model/east_pdf_section_surface.obj"},
            {"name": "东安 PDF 切面 PLY", "path": "../models/east_pdf_section_model/east_pdf_section_surface.ply"},
            {"name": "东安测试位点 PLY", "path": "../models/east_pdf_section_model/east_pdf_test_points.ply"},
            {"name": "超欠挖 CSV", "path": "../structured/overbreak_underbreak_sections.csv"},
            {"name": "原始超欠挖成果表 PDF", "path": "../raw/20260518XJDA.pdf"},
        ],
        model_url="../models/east_pdf_section_model/east_pdf_section_3d.html",
    )

    douli_overview = weekly_summary["隧道概况"]
    douli = make_tunnel(
        tunnel_id="douli",
        name="豆里冲隧道出口",
        description="监控量测周报对象，当前接入地表下沉、拱顶下沉和周边收敛。",
        overview={
            "来源": "豆里冲隧道周报 DOCX",
            "报告周期": weekly_summary["报告周期"],
            "隧道名称": douli_overview["隧道名称"],
            "起点里程": douli_overview["起点里程"],
            "终点里程": douli_overview["终点里程"],
            "长度": f"{douli_overview['长度(m)']} m",
            "周报结论": weekly_summary["报告原文结论"],
        },
        surface=surface,
        crown=crown,
        convergence=convergence,
        resources=[
            {"name": "地表下沉 CSV", "path": "../structured/weekly_surface_settlement.csv"},
            {"name": "拱顶下沉 CSV", "path": "../structured/weekly_crown_settlement.csv"},
            {"name": "周边收敛 CSV", "path": "../structured/weekly_peripheral_convergence.csv"},
            {"name": "豆里冲隧道 OBJ", "path": "../models/doulichong_tunnel_schematic.obj"},
            {"name": "原始周报 DOCX", "path": "../raw/doulichong_weekly_2026-05-15_to_2026-05-21.docx"},
        ],
    )

    all_tunnel = build_all_tunnel(east, douli)
    tunnels = {t["id"]: t for t in [all_tunnel, east, douli]}
    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tunnelOrder": ["all", "east", "douli"],
        "tunnels": tunnels,
        "brain": {
            "enabled": True,
            "status": "动态对话已启用",
            "endpoint": "/api/brain/chat",
            "statusEndpoint": "/api/brain/status",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "description": "用于连续问答、风险解释、报表摘要和施工建议。后续可切换到多模态图片理解服务。",
            "examples": ["东安隧道超挖最严重的断面在哪里？", "豆里冲本周最大变形测点是什么？", "帮我生成本周风险简报。"],
        },
        "ingestion": {
            "enabled": False,
            "status": "接口预留",
            "uploadEndpoint": "/api/packages/upload",
            "buildEndpoint": "/api/tunnels/{tunnel_id}/build-model",
            "jobEndpoint": "/api/tunnels/{tunnel_id}/jobs/{job_id}",
            "supportedFiles": ["csv", "json", "txt", "xyz", "pts", "zip（包含前述结构化文件）", "pdf/docx/xlsx/las/e57/ply/obj（当前保存登记，后续接专用解析器）"],
            "pipeline": ["上传数据包", "识别文件类型", "解析成果表/周报/点云/断面坐标", "统一坐标与里程体系", "抽取断面并计算超欠挖", "生成网格/点云轻量化成果", "刷新 3D 模型、看板和预警"],
        },
        "modelingGuide": {
            "requiredData": [
                {
                    "name": "原始点云或断面坐标",
                    "level": "必须",
                    "formats": "LAS/LAZ、E57、PLY、XYZ/CSV、TXT",
                    "fields": "X、Y、Z，建议包含 intensity、RGB、scan_id、timestamp、点分类。",
                    "why": "这是重建隧道实际开挖轮廓的核心数据；只有 PDF 截图无法形成可靠的工程级内部 3D 模型。",
                },
                {
                    "name": "设计中线与设计断面",
                    "level": "必须",
                    "formats": "DXF/DWG、IFC、LandXML、CSV/JSON",
                    "fields": "里程、中心线坐标、断面轮廓点、拱墙/仰拱分区、坐标系。",
                    "why": "用于把实测点云切成逐里程断面，并与设计轮廓比较得到超挖和欠挖。",
                },
                {
                    "name": "坐标基准与控制点",
                    "level": "必须",
                    "formats": "CSV/JSON、测量控制网报告、EPSG/地方坐标说明",
                    "fields": "控制点编号、X/Y/Z、坐标系、单位、里程转换关系。",
                    "why": "避免不同仪器、不同批次点云错位；没有统一基准，自动计算会出现整体偏移。",
                },
                {
                    "name": "超欠挖成果表",
                    "level": "推荐",
                    "formats": "XLSX/CSV、PDF、JSON",
                    "fields": "桩号、设计面积、测量面积、超挖面积、欠挖面积、最大超挖、最大欠挖。",
                    "why": "可作为平台看板和自动识别结果的复核依据。",
                },
                {
                    "name": "施工与监控量测数据",
                    "level": "推荐",
                    "formats": "DOCX/PDF、XLSX/CSV、数据库接口",
                    "fields": "掌子面里程、施工工法、围岩级别、沉降/收敛测点、时间序列。",
                    "why": "用于把 3D 模型、风险预警和施工过程关联起来。",
                },
            ],
            "formats": [
                {"stage": "上传原始数据", "format": "ZIP + LAS/LAZ/E57/PLY/XYZ/CSV", "note": "适合批量上传点云、断面表、设计文件和报告。"},
                {"stage": "平台内部标准化", "format": "Parquet/SQLite/PostgreSQL + JSON metadata", "note": "保存点、断面、里程、坐标系和质量报告，便于查询和增量更新。"},
                {"stage": "三维网页展示", "format": "GLB/glTF、OBJ/PLY、Potree 点云目录", "note": "GLB 适合网格模型；Potree 适合大规模点云分层加载。"},
                {"stage": "工程交换", "format": "DXF/DWG、IFC、OBJ、PLY、CSV", "note": "用于与 Rhino、3DReshaper、CAD/BIM 或第三方审查软件交换。"},
            ],
            "toolchain": [
                {"part": "文件解析与点云转换", "tools": "PDAL、laspy、pye57、numpy/pandas", "role": "读取 LAS/LAZ/E57/XYZ，统一字段、坐标、单位和批次元数据。"},
                {"part": "点云处理与建模", "tools": "Open3D、scipy、shapely、trimesh", "role": "降噪、抽稀、法向估计、断面切片、曲线拟合、网格重建。"},
                {"part": "网页端 3D 展示", "tools": "Three.js、Potree、Plotly", "role": "Three.js 展示 GLB/OBJ/PLY；Potree 展示大点云；Plotly 适合轻量交互验证。"},
                {"part": "异步任务与存储", "tools": "FastAPI/Flask、Celery/RQ、Redis、PostgreSQL/PostGIS、对象存储", "role": "上传后排队建模、查询进度、保存模型资产和质量报告。"},
            ],
            "automationFlow": [
                "POST /api/packages/upload 接收数据包，记录 tunnel_id、批次号和原始文件清单。",
                "后台任务解压并识别文件类型，生成 manifest.json。",
                "点云转换为统一坐标和内部标准字段，写入点云索引或数据库。",
                "读取设计中线与断面，按固定里程间距或测点桩号切片。",
                "将每个实测断面与设计断面配准，计算超挖/欠挖面积、最大深度和位置。",
                "生成断面曲线、隧道内壁网格、点云轻量化结果和质量报告。",
                "导出 GLB/OBJ/PLY/Potree 目录，登记到模型资源表。",
                "前端调用 GET /api/tunnels/{tunnel_id}/jobs/{job_id} 查看进度，完成后刷新三维模型和看板。",
            ],
            "qualityChecks": [
                "坐标系、单位、里程方向必须一致。",
                "每个断面需要记录采样点数、缺失率、是否插值补齐。",
                "超欠挖计算必须保留设计轮廓、实测轮廓、差值曲线和阈值。",
                "大模型/智慧大脑只能解释和总结，不应替代原始计算结果。",
            ],
            "references": [
                {"name": "PDAL Pipeline 与 LAS/E57 读写文档", "url": "https://pdal.io/en/stable/pipeline.html"},
                {"name": "Open3D Surface Reconstruction", "url": "https://www.open3d.org/docs/release/tutorial/geometry/surface_reconstruction.html"},
                {"name": "Potree Web Point Cloud Renderer", "url": "https://github.com/potree/potree"},
                {"name": "Khronos glTF", "url": "https://www.khronos.org/gltf/"},
                {"name": "three.js Documentation", "url": "https://threejs.org/docs/"},
            ],
        },
        "notes": [
            "平台已按隧道名称分组管理，可通过顶部下拉框切换。",
            "没有接入的数据板块会显示待接入提示。",
            "智慧大脑已接入 L20 本地 Qwen 文本模型；图片理解将在 Qwen2.5-VL 服务化后接入。",
        ],
    }


HERO_SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 520" preserveAspectRatio="xMidYMid slice">
<defs>
  <radialGradient id="lamp" cx="62%" cy="45%" r="42%">
    <stop offset="0%" stop-color="#ffd98a" stop-opacity=".92"/>
    <stop offset="40%" stop-color="#d79a42" stop-opacity=".36"/>
    <stop offset="100%" stop-color="#07131f" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="rock" x1="0" x2="1">
    <stop offset="0%" stop-color="#18283a"/>
    <stop offset="48%" stop-color="#3d4a51"/>
    <stop offset="100%" stop-color="#161f2a"/>
  </linearGradient>
  <linearGradient id="floor" x1="0" x2="1">
    <stop offset="0%" stop-color="#39424b"/>
    <stop offset="100%" stop-color="#171d24"/>
  </linearGradient>
</defs>
<rect width="1600" height="520" fill="#08111b"/>
<path d="M0 128 C180 48 322 35 470 81 C590 118 673 182 792 186 C952 191 1052 88 1206 80 C1378 71 1515 144 1600 211 L1600 520 L0 520 Z" fill="url(#rock)" opacity=".96"/>
<path d="M392 520 C395 349 472 226 603 164 C718 110 849 120 958 181 C1081 250 1142 366 1145 520 Z" fill="#0b121b" opacity=".98"/>
<path d="M468 520 C474 382 535 282 637 232 C729 187 833 195 919 243 C1014 296 1062 394 1064 520 Z" fill="#202a33"/>
<path d="M545 520 C551 428 592 356 662 319 C730 283 810 287 875 326 C944 368 981 440 986 520 Z" fill="#0c151e"/>
<path d="M0 410 C210 382 396 389 548 420 C726 456 914 454 1111 420 C1324 383 1487 383 1600 402 L1600 520 L0 520 Z" fill="url(#floor)" opacity=".88"/>
<path d="M330 498 L1260 498" stroke="#f6b95e" stroke-width="4" stroke-opacity=".45"/>
<path d="M537 520 L685 360 M860 520 L770 360 M640 520 L720 354 M966 520 L814 354" stroke="#f8c06b" stroke-width="2" stroke-opacity=".22"/>
<circle cx="1010" cy="170" r="12" fill="#ffd98a"/>
<circle cx="1010" cy="170" r="160" fill="url(#lamp)"/>
<path d="M1126 403 h86 l30 42 h-142 z" fill="#d37b2c"/>
<path d="M1190 365 l78 38 -23 18 -84 -33 z" fill="#f0a340"/>
<path d="M1138 394 l-37 37" stroke="#ffd28a" stroke-width="10" stroke-linecap="round"/>
<circle cx="1132" cy="450" r="21" fill="#1d252e"/><circle cx="1212" cy="450" r="21" fill="#1d252e"/>
<path d="M230 270 C300 230 365 223 438 249" stroke="#97b4c8" stroke-width="3" stroke-opacity=".35" fill="none"/>
<path d="M1260 258 C1340 236 1420 245 1495 295" stroke="#97b4c8" stroke-width="3" stroke-opacity=".24" fill="none"/>
<g opacity=".18" stroke="#dbe9f5" stroke-width="1">
  <path d="M80 110 L480 440"/>
  <path d="M1520 120 L1090 452"/>
  <path d="M20 346 L1580 346"/>
</g>
</svg>"""


def write_assets() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "tunnel_excavation_hero.svg").write_text(HERO_SVG, encoding="utf-8")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>隧道智慧管控平台 V1</title>
<style>
:root{--bg:#f3f6fb;--panel:#fff;--ink:#182338;--muted:#65748b;--blue:#1767c2;--red:#cf2e2e;--orange:#e57722;--yellow:#d7a300;--green:#23854b;--line:#dfe6f0}
*{box-sizing:border-box}body{margin:0;font-family:Arial,"Microsoft YaHei",sans-serif;background:linear-gradient(180deg,#eef3f9,#f7f9fc);color:var(--ink)}
header.hero{min-height:210px;color:#fff;padding:28px 28px 30px;background-image:linear-gradient(105deg,rgba(5,18,34,.92),rgba(11,42,63,.68),rgba(22,68,83,.24)),url("assets/tunnel_excavation_hero.svg");background-size:cover;background-position:center;position:relative;overflow:hidden}
header.hero:after{content:"";position:absolute;inset:auto 0 0;height:56px;background:linear-gradient(180deg,rgba(243,246,251,0),#f3f6fb)}
.hero-inner{position:relative;z-index:1;max-width:1480px;margin:0 auto}.eyebrow{display:inline-flex;align-items:center;gap:8px;padding:6px 11px;border:1px solid rgba(255,255,255,.28);border-radius:999px;background:rgba(255,255,255,.12);backdrop-filter:blur(8px);font-size:13px;letter-spacing:.08em}
header h1{margin:18px 0 0;font-size:38px;line-height:1.15;letter-spacing:.02em;text-shadow:0 8px 24px rgba(0,0,0,.34)}header p{max-width:860px;margin:12px 0 0;color:#e7f3ff;font-size:15px;line-height:1.7}.hero-badges{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.hero-badges span{padding:8px 11px;border-radius:10px;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.22);box-shadow:0 12px 30px rgba(0,0,0,.14)}
.brain{--brain-chat-min:132px;--brain-chat-max:420px;display:grid;grid-template-columns:230px 1fr;gap:12px 16px;align-items:stretch;background:linear-gradient(135deg,#071d37,#0d3b63 58%,#125a78);color:#fff;padding:14px 24px;border-top:1px solid rgba(255,255,255,.12);box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
.brainIntro{grid-row:1/3;display:flex;flex-direction:column;justify-content:space-between;gap:10px;padding:2px 0}.brain .title{font-weight:800;font-size:17px;letter-spacing:.03em}.brain-sub{color:#b9d7f5;font-size:12px;line-height:1.6}.brainTools{display:flex;gap:8px;flex-wrap:wrap}.brainMessages{min-height:var(--brain-chat-min);max-height:min(42vh,var(--brain-chat-max));overflow-y:auto;border:1px solid rgba(255,255,255,.16);border-radius:13px;background:rgba(3,18,35,.32);padding:10px;scroll-behavior:smooth;transition:max-height .2s ease,box-shadow .2s ease}.brainMessages:hover{box-shadow:0 12px 28px rgba(0,0,0,.16)}.brainMessages::-webkit-scrollbar{width:8px}.brainMessages::-webkit-scrollbar-thumb{background:rgba(255,255,255,.28);border-radius:999px}.brainMsg{display:flex;margin:0 0 8px}.brainMsg.user{justify-content:flex-end}.brainBubble{max-width:78%;padding:8px 10px;border-radius:12px;background:rgba(255,255,255,.12);line-height:1.55;font-size:13px;white-space:pre-wrap;box-shadow:0 6px 18px rgba(0,0,0,.10)}.brainMsg.user .brainBubble{background:#eaf5ff;color:#12314f;border-bottom-right-radius:4px}.brainMsg.assistant .brainBubble{border-bottom-left-radius:4px}.brainMeta{display:block;margin-bottom:3px;color:#87bee9;font-size:11px}.brainMsg.user .brainMeta{color:#4f789d}.brainEmpty{color:#c9dcf0;font-size:13px;line-height:1.7}.brainLimit{font-size:11px;color:#95c7ef}.brainComposer{display:grid;grid-template-columns:1fr auto;gap:10px}.brain input{width:100%;border:1px solid #6aa9d8;background:#fff;border-radius:10px;padding:10px 12px}.brain button{border:0;border-radius:10px;background:#39a7ff;color:#fff;padding:9px 14px;cursor:pointer;font-weight:700;transition:transform .18s ease,box-shadow .18s ease,background .18s ease}.brain button:hover{transform:translateY(-1px) scale(1.03);box-shadow:0 10px 20px rgba(57,167,255,.24)}.brain button.secondary{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.18);color:#e7f3ff;box-shadow:none}.brain button.secondary:hover{background:rgba(255,255,255,.22)}
.topbar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;background:rgba(255,255,255,.88);backdrop-filter:blur(12px);padding:13px 24px;border-bottom:1px solid rgba(205,216,231,.85);position:sticky;top:0;z-index:6;box-shadow:0 10px 26px rgba(20,45,78,.08)}.selector{display:flex;gap:8px;align-items:center;padding-right:14px;border-right:1px solid var(--line);transition:transform .18s ease}.selector:hover{transform:translateY(-1px) scale(1.015)}
select,input{border:1px solid #cbd6e5;border-radius:8px;padding:8px 10px;background:#fff;transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease}select:hover,input:hover{border-color:#8bb6df;box-shadow:0 8px 18px rgba(23,103,194,.10)}nav{display:flex;gap:9px;flex-wrap:wrap}nav button{border:1px solid #cbd6e5;background:linear-gradient(180deg,#fff,#f3f7fc);color:#24344d;padding:9px 14px;border-radius:10px;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,background .18s ease,color .18s ease,border-color .18s ease}nav button:hover{transform:translateY(-2px) scale(1.06);box-shadow:0 12px 24px rgba(23,103,194,.18);border-color:#8ebbe8}nav button.active{background:linear-gradient(135deg,#1767c2,#22a6d5);color:#fff;border-color:#1767c2;box-shadow:0 12px 24px rgba(23,103,194,.24)}
main{max-width:1480px;margin:0 auto;padding:20px 24px 40px}section{display:none}section.active{display:block}.grid{display:grid;gap:14px}.cards{grid-template-columns:repeat(8,minmax(120px,1fr))}.two{grid-template-columns:1.1fr .9fr}.three{grid-template-columns:repeat(3,1fr)}
.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:13px;box-shadow:0 6px 18px rgba(25,51,84,.06)}.card{padding:14px 16px;transition:transform .18s ease,box-shadow .18s ease}.card:hover{transform:translateY(-2px);box-shadow:0 12px 26px rgba(25,51,84,.10)}.label{color:var(--muted);font-size:13px}.value{margin-top:8px;font-weight:700;font-size:21px;color:#0d3768}
.panel{padding:18px;margin-bottom:14px}h2{margin:0 0 14px;font-size:22px}h3{margin:0 0 12px;font-size:17px}.muted{color:var(--muted);font-size:13px;line-height:1.6}.pill{display:inline-block;padding:4px 9px;border-radius:999px;font-size:12px;color:#fff}.红色{background:var(--red)}.橙色{background:var(--orange)}.黄色{background:var(--yellow);color:#352900}.正常{background:var(--green)}
.table-wrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{padding:9px 10px;border-bottom:1px solid #edf1f6;text-align:left;white-space:nowrap}th{position:sticky;top:0;background:#eaf2fb;z-index:1}tr:hover td{background:#f7fbff}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}.svgbox{height:310px;width:100%;background:#fbfdff;border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative}svg{width:100%;height:100%;display:block}.axis{stroke:#9aa9bd;stroke-width:1}.gridline{stroke:#e8eef6;stroke-width:1}.plot{fill:none;stroke:#1767c2;stroke-width:2.4}.plot2{fill:none;stroke:#cf2e2e;stroke-width:2.2}.area{fill:rgba(23,103,194,.10);stroke:none}.dot{fill:#1767c2}.cross{stroke:#333;stroke-width:1;stroke-dasharray:4 3;pointer-events:none}.chartTip{position:absolute;display:none;pointer-events:none;background:#172033;color:#fff;border-radius:6px;padding:7px 9px;font-size:12px;box-shadow:0 8px 18px rgba(0,0,0,.18);z-index:4}
.metric-grid{display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:10px}.metric{border:1px solid var(--line);border-radius:10px;background:#fbfdff;padding:10px}.metric b{display:block;color:#0d3768;font-size:18px;margin-top:4px}.sectionbox{height:390px}.sectionbar{height:230px}.legend-line{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px}.legend-item{display:inline-flex;align-items:center;gap:6px}.legend-dot{width:11px;height:11px;border-radius:50%;display:inline-block}
.resource a{display:block;padding:10px 12px;border:1px solid var(--line);border-radius:9px;margin:8px 0;color:#0d5fb3;text-decoration:none;background:#fbfdff}.resource a:hover{background:#eef6ff}.iframe{width:100%;height:720px;border:1px solid var(--line);border-radius:12px;background:#fff}.alert-summary{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.tag{padding:6px 9px;border-radius:8px;background:#eef3fa;color:#43536a;font-size:12px}.empty{padding:22px;border:1px dashed #bdc9d8;border-radius:10px;background:#fbfdff;color:#65748b}.drop{border:2px dashed #9db7d4;border-radius:14px;background:#f7fbff;padding:22px;text-align:center;transition:transform .18s ease,border-color .18s ease,background .18s ease,box-shadow .18s ease}.drop.drag{transform:scale(1.015);border-color:#1767c2;background:#eef7ff;box-shadow:0 16px 32px rgba(23,103,194,.14)}.upload-files{margin:10px 0;color:#43536a;font-size:13px}.uploadResult{text-align:left;margin-top:12px}.uploadResult a{color:#0d5fb3;text-decoration:none}.uploadResult a:hover{text-decoration:underline}.upload-ok{border:1px solid #b7dfc8;background:#f2fbf5;border-radius:10px;padding:10px}.upload-warn{border:1px solid #f1d28a;background:#fff9e8;border-radius:10px;padding:10px;margin-top:8px}
.api{font-family:Consolas,monospace;background:#eef3fa;border-radius:6px;padding:3px 6px;color:#174d87}.guide-list{display:grid;gap:10px}.guide-card{border:1px solid var(--line);border-radius:11px;background:#fbfdff;padding:12px}.guide-card h4{margin:0 0 6px;font-size:15px}.guide-card p{margin:5px 0}.level{display:inline-block;margin-left:6px;padding:2px 7px;border-radius:999px;background:#eaf2fb;color:#1767c2;font-size:12px}.toolchain{display:grid;gap:10px}.source-list a{display:block;margin:6px 0;color:#0d5fb3;text-decoration:none}.source-list a:hover{text-decoration:underline}.manage-list{display:grid;gap:10px}.manage-item{border:1px solid var(--line);border-radius:11px;background:#fbfdff;padding:12px}.manage-head{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}.manage-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.manage-actions input{min-width:240px}.small-btn{border:1px solid #cbd6e5;background:#f7faff;color:#174d87;border-radius:8px;padding:8px 10px;cursor:pointer}.small-btn:hover{background:#eef6ff}.danger{border-color:#efb6b6;background:#fff4f4;color:#b61e1e}.danger:hover{background:#ffecec}.model-note{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 12px;align-items:start;margin:4px 0 12px;padding:10px 12px;border:1px solid #dbe8f5;border-radius:8px;background:#f7fbff;line-height:1.65}.model-note .tag{display:inline-flex;align-items:center;justify-content:center;white-space:nowrap}.model-note .muted{display:block;min-width:0;margin:0;line-height:1.7;white-space:normal;overflow-wrap:anywhere}.model-desc{display:block;clear:both;margin:0 0 14px!important;max-width:1180px;line-height:1.8;overflow-wrap:anywhere}#model3d .iframe{display:block;margin-top:12px}
/* Digital-twin cockpit skin, borrowing the one-screen status + 3D-twin dashboard language used by GIS/BIM platforms. */
body{background:radial-gradient(circle at 78% 10%,rgba(37,174,255,.20),transparent 30%),radial-gradient(circle at 12% 24%,rgba(255,184,77,.12),transparent 28%),linear-gradient(180deg,#07111e 0,#0b1725 260px,#eef3f8 760px,#f7f9fc 100%);color:var(--ink)}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(180deg,#000 0,transparent 62%);opacity:.55;z-index:-1}
header.hero{min-height:260px;padding:30px 28px 38px;background-image:linear-gradient(105deg,rgba(3,12,22,.96),rgba(6,34,58,.78),rgba(14,74,91,.28)),url("assets/tunnel_excavation_hero.svg");box-shadow:inset 0 -1px 0 rgba(255,255,255,.10)}
header.hero:before{content:"";position:absolute;inset:0;background:linear-gradient(120deg,transparent 0,rgba(96,205,255,.12) 48%,transparent 58%);transform:translateX(-70%);animation:scanHero 8s linear infinite}
header.hero:after{height:82px;background:linear-gradient(180deg,rgba(7,17,30,0),#0b1725 78%,rgba(238,243,248,0))}
@keyframes scanHero{to{transform:translateX(75%)}}
.hero-inner{max-width:1560px}.eyebrow{background:rgba(32,180,255,.14);border-color:rgba(115,213,255,.42);box-shadow:0 0 24px rgba(66,185,255,.16)}
header h1{font-size:44px;letter-spacing:.08em}.hero-badges span{background:linear-gradient(135deg,rgba(255,255,255,.18),rgba(255,255,255,.06));border-color:rgba(163,216,255,.32);box-shadow:0 16px 36px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.18);transition:transform .2s ease,box-shadow .2s ease}.hero-badges span:hover{transform:translateY(-2px) scale(1.05);box-shadow:0 18px 40px rgba(49,178,255,.20)}
.cockpit-strip{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px;margin-top:20px;max-width:980px}.cockpit-chip{position:relative;overflow:hidden;padding:12px 14px;border-radius:14px;background:linear-gradient(135deg,rgba(5,26,46,.74),rgba(14,79,112,.36));border:1px solid rgba(122,211,255,.30);box-shadow:0 14px 36px rgba(0,0,0,.22),inset 0 1px 0 rgba(255,255,255,.12)}.cockpit-chip:after{content:"";position:absolute;inset:auto 12px 0;height:2px;background:linear-gradient(90deg,transparent,#48c7ff,transparent);opacity:.8}.cockpit-chip span{display:block;color:#9edcff;font-size:12px}.cockpit-chip b{display:block;margin-top:5px;color:#fff;font-size:18px;letter-spacing:.03em}
.brain{background:linear-gradient(135deg,rgba(2,13,27,.96),rgba(6,42,75,.94) 56%,rgba(9,92,108,.90));border-top:1px solid rgba(109,214,255,.20);border-bottom:1px solid rgba(109,214,255,.16);box-shadow:0 18px 50px rgba(0,0,0,.24),inset 0 1px 0 rgba(255,255,255,.08)}.brainMessages{background:linear-gradient(180deg,rgba(3,18,35,.48),rgba(3,18,35,.28));border-color:rgba(111,203,255,.24)}.brainBubble{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.10)}.brainMsg.user .brainBubble{background:linear-gradient(135deg,#e8f7ff,#cdeeff)}
.topbar{top:0;background:rgba(7,18,31,.78);border-bottom:1px solid rgba(90,179,239,.26);box-shadow:0 14px 34px rgba(2,12,24,.22);color:#eaf6ff}.selector{border-right-color:rgba(135,204,255,.22)}.selector b{color:#fff}
select,input{background:rgba(255,255,255,.94);border-color:rgba(156,188,223,.76)}nav button{position:relative;overflow:hidden;background:rgba(255,255,255,.08);border-color:rgba(124,198,255,.28);color:#dff2ff;box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}nav button:before{content:"";position:absolute;inset:0;background:linear-gradient(120deg,transparent,rgba(112,208,255,.28),transparent);transform:translateX(-120%);transition:transform .38s ease}nav button:hover:before{transform:translateX(120%)}nav button:hover{border-color:rgba(112,208,255,.62);box-shadow:0 14px 28px rgba(22,145,220,.22)}nav button.active{background:linear-gradient(135deg,#1e88ff,#22d0d5);border-color:#6edcff;color:#fff;box-shadow:0 0 0 1px rgba(255,255,255,.12),0 16px 32px rgba(34,168,255,.30)}
main{max-width:1560px;padding-top:24px}.card,.panel{background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(247,251,255,.96));border:1px solid rgba(203,216,231,.92);box-shadow:0 16px 36px rgba(10,35,66,.10)}.panel{position:relative;overflow:hidden;transition:transform .18s ease,box-shadow .18s ease}.panel:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#27b8ff,#ffc25a,#28d7ae);opacity:.78}.card{position:relative;overflow:hidden;border-color:rgba(148,188,228,.60)}.card:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,#25b7ff,#28d7ae)}.card:hover,.panel:hover{transform:translateY(-2px);box-shadow:0 20px 44px rgba(10,35,66,.15)}.value{color:#073b74}.label{letter-spacing:.02em}
.svgbox,.metric,.guide-card,.manage-item,.resource a,.drop{background:linear-gradient(180deg,#ffffff,#f8fbff);border-color:rgba(205,219,235,.92)}.svgbox{box-shadow:inset 0 0 0 1px rgba(255,255,255,.58)}.chartTip{background:#071523;border:1px solid rgba(104,202,255,.28)}.tag{background:#edf6ff;color:#255071}.table-wrap{border-color:rgba(205,219,235,.92);box-shadow:inset 0 1px 0 rgba(255,255,255,.7)}th{background:linear-gradient(180deg,#e5f3ff,#dceafa);color:#193d5d}.iframe{height:760px;border-color:rgba(91,171,231,.34);box-shadow:0 18px 44px rgba(10,35,66,.12)}.drop:hover{transform:translateY(-2px);border-color:#4abfff;box-shadow:0 18px 36px rgba(23,103,194,.13)}
.portal-header{background:#fff;border-bottom:1px solid #d8e2ef;box-shadow:0 4px 16px rgba(16,42,76,.08);position:relative;z-index:20}.portal-inner{max-width:1560px;margin:0 auto;height:70px;padding:0 26px;display:flex;align-items:center;gap:26px}.portal-brand{display:flex;align-items:center;gap:13px;min-width:300px;text-decoration:none;color:#173a66}.brand-logo{width:46px;height:46px;border-radius:10px;background:linear-gradient(135deg,#166cc8,#22afd7);display:grid;place-items:center;color:#fff;font-size:25px;font-weight:800;box-shadow:0 10px 22px rgba(22,108,200,.22)}.brand-title{font-size:22px;font-weight:800;letter-spacing:.04em}.brand-sub{margin-top:2px;color:#7890a8;font-size:12px}.portal-nav{display:flex;align-items:center;gap:4px;flex:1}.portal-nav button{border:0;background:transparent;color:#223955;padding:23px 15px;height:70px;font-size:15px;cursor:pointer;border-bottom:3px solid transparent;transition:background .18s ease,color .18s ease,border-color .18s ease,transform .18s ease}.portal-nav button:hover{background:#eef7ff;color:#1467bd;border-bottom-color:#2b99df;transform:translateY(-1px)}.portal-actions{display:flex;align-items:center;gap:10px;color:#5d7188;font-size:13px;white-space:nowrap}.portal-actions a{color:#1767c2;text-decoration:none}.portal-actions a:hover{text-decoration:underline}
.portal-shell{background:#f3f7fb}.portal-shell header.hero{min-height:386px;padding:0;background-image:linear-gradient(90deg,rgba(8,31,58,.72),rgba(6,69,112,.34),rgba(255,255,255,.04)),url("assets/tunnel_excavation_hero.svg");background-position:center;background-size:cover;box-shadow:none}.portal-shell header.hero:before{display:none}.portal-shell header.hero:after{height:42px;background:linear-gradient(180deg,rgba(243,247,251,0),#f3f7fb)}.portal-shell .hero-inner{max-width:1560px;min-height:386px;padding:46px 26px 64px;display:grid;grid-template-columns:minmax(360px,1fr) 460px;gap:42px;align-items:center}.portal-kicker{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.34);border-radius:999px;color:#e8f7ff;font-size:13px;letter-spacing:.08em}.portal-shell header h1{margin:18px 0 10px;font-size:46px;letter-spacing:.04em}.portal-shell header p{font-size:16px;color:#edf8ff;max-width:780px}.portal-search{margin-top:25px;background:rgba(255,255,255,.95);border-radius:8px;padding:9px;display:grid;grid-template-columns:1fr auto;gap:8px;max-width:760px;box-shadow:0 18px 42px rgba(5,24,49,.25)}.portal-search input{border:0;background:#fff;font-size:15px;padding:14px 16px;box-shadow:none}.portal-search input:hover,.portal-search input:focus{box-shadow:none;border:0}.portal-search button,.portal-hero-actions button{border:0;border-radius:6px;background:#1767c2;color:#fff;font-weight:700;padding:0 22px;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,background .18s ease}.portal-search button:hover,.portal-hero-actions button:hover{transform:translateY(-1px) scale(1.04);box-shadow:0 12px 24px rgba(23,103,194,.24);background:#0f5cad}.portal-hero-actions{display:flex;gap:12px;margin-top:14px}.portal-hero-actions button{height:42px;background:#1f8ed3}.portal-hero-actions button.secondary{background:#f2a53b;color:#fff}.portal-keywords{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.portal-keywords span{padding:7px 11px;border-radius:999px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.22);color:#eef8ff;font-size:12px;transition:transform .18s ease,background .18s ease}.portal-keywords span:hover{transform:translateY(-2px) scale(1.05);background:rgba(255,255,255,.24)}.portal-stat-panel{background:rgba(255,255,255,.96);border-radius:12px;padding:20px;border:1px solid rgba(224,232,242,.88);box-shadow:0 20px 48px rgba(10,35,66,.18)}.portal-stat-title{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.portal-stat-title b{color:#16395f;font-size:18px}.portal-stat-title span{color:#6c7d91;font-size:12px}.portal-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.portal-stat{padding:16px;border-radius:10px;background:linear-gradient(180deg,#f7fbff,#eef6ff);border:1px solid #dbe9f7}.portal-stat span{display:block;color:#637991;font-size:13px}.portal-stat b{display:block;margin-top:8px;font-size:24px;color:#0d4f96}.portal-tags{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.portal-tag{padding:12px;border-radius:8px;text-align:center;background:#fff;border:1px solid #dce8f5;color:#24506f;font-weight:700;cursor:pointer;transition:transform .18s ease,box-shadow .18s ease,color .18s ease}.portal-tag:hover{transform:translateY(-3px) scale(1.04);box-shadow:0 14px 26px rgba(23,103,194,.16);color:#1767c2}
.portal-shell .brain{background:#fff;color:#1c324d;border:1px solid #dbe5f1;border-left:0;border-right:0;box-shadow:0 12px 30px rgba(16,42,76,.08);grid-template-columns:260px 1fr}.portal-shell .brain .title{color:#164274}.portal-shell .brain-sub,.portal-shell .brainLimit{color:#60778f}.portal-shell .brainMessages{background:#f7fbff;border-color:#d7e7f6}.portal-shell .brainBubble{background:#fff;color:#213b57;border-color:#dbe8f5}.portal-shell .brainMsg.user .brainBubble{background:linear-gradient(135deg,#1767c2,#22a6d5);color:#fff}.portal-shell .brainMeta{color:#5f94c4}.portal-shell .brainMsg.user .brainMeta{color:#e4f5ff}.portal-shell .brainEmpty{color:#637991}.portal-shell .brain button.secondary{background:#eef6ff;color:#1767c2;border-color:#cfe2f4}.portal-shell .brain input{border-color:#cbdceb}
.portal-shell .topbar{background:#1767c2;color:#fff;border-bottom:0;box-shadow:0 10px 26px rgba(20,70,132,.22);padding:0 24px}.portal-shell .selector{height:54px;border-right:1px solid rgba(255,255,255,.22)}.portal-shell .selector b{color:#fff}.portal-shell .topbar select{height:36px}.portal-shell nav button{height:54px;border:0;border-radius:0;background:transparent;color:#e8f5ff;box-shadow:none;padding:0 16px}.portal-shell nav button:before{display:none}.portal-shell nav button:hover{background:rgba(255,255,255,.15);transform:scale(1.04);box-shadow:none}.portal-shell nav button.active{background:#0d4f99;box-shadow:inset 0 -3px 0 #f5b74d;color:#fff}.portal-shell main{padding-top:24px}.portal-section-title{display:flex;align-items:center;justify-content:space-between;margin:4px 0 14px}.portal-section-title h2{margin:0}.portal-section-title span{color:#7b8fa6;font-size:13px}.portal-shell .card,.portal-shell .panel{border-radius:8px;border-color:#dbe5f1;background:#fff;box-shadow:0 8px 24px rgba(21,54,91,.08)}.portal-shell .panel:before{height:0}.portal-shell .card:before{background:#1767c2}.portal-shell .card:hover,.portal-shell .panel:hover{transform:translateY(-3px);box-shadow:0 18px 38px rgba(21,54,91,.13)}.portal-shell h2{color:#16395f;border-left:4px solid #1767c2;padding-left:10px}.portal-shell h3{color:#244260}.portal-shell .tag{border-radius:4px;background:#edf5ff;color:#1d5d9e}.portal-shell .small-btn{background:#f4f9ff}.portal-shell .drop{background:#f7fbff}
@media(max-width:1260px){.portal-inner{height:auto;min-height:70px;flex-wrap:wrap;padding:12px 18px}.portal-brand{min-width:240px}.portal-nav{order:3;width:100%;overflow-x:auto}.portal-nav button{height:44px;padding:10px 13px}.portal-shell .hero-inner{grid-template-columns:1fr}.portal-stat-panel{max-width:760px}.portal-search{max-width:none}}
@media(max-width:760px){.portal-brand{min-width:0}.brand-title{font-size:18px}.brand-sub{display:none}.portal-actions{width:100%;justify-content:space-between}.portal-shell header h1{font-size:34px}.portal-shell .hero-inner{padding:32px 16px 54px}.portal-search{grid-template-columns:1fr}.portal-search button{height:42px}.portal-hero-actions{flex-direction:column}.portal-hero-actions button{width:100%}.portal-stat-grid,.portal-tags{grid-template-columns:1fr 1fr}.portal-shell .topbar{padding:8px 12px}.portal-shell .selector{height:auto;width:100%;border-right:0}.portal-shell nav{overflow-x:auto;flex-wrap:nowrap;width:100%}.portal-shell nav button{white-space:nowrap}.model-note{grid-template-columns:1fr}.model-note .tag{justify-content:flex-start;width:max-content}.model-desc{line-height:1.75}}
@media(max-width:1100px){.cards,.two,.three{grid-template-columns:1fr 1fr}.iframe{height:560px}.brain{grid-template-columns:1fr;--brain-chat-min:150px;--brain-chat-max:460px}.brainIntro{grid-row:auto}}@media(max-width:720px){.cards,.two,.three{grid-template-columns:1fr}main{padding:14px}.selector{border-right:0}.brain{--brain-chat-max:55vh}.brainComposer{grid-template-columns:1fr}.brainBubble{max-width:92%}}
</style>
</head>
<body class="portal-shell">
<div class="portal-header"><div class="portal-inner"><a class="portal-brand" href="/platform/index.html"><span class="brand-logo">隧</span><span><span class="brand-title">隧道智慧管控平台</span><span class="brand-sub">Tunnel Data Center & Digital Twin</span></span></a><div class="portal-nav"><button data-jump="overview">首页</button><button data-jump="model3d">空间查询</button><button data-jump="overbreak">资源目录</button><button data-jump="overview">资源统计</button><button data-jump="ingest">数据接入</button><button data-jump="resources">资料中心</button><button data-jump="alerts">风险预警</button></div><div class="portal-actions"><span>演示账号：123</span><a href="/logout">退出</a></div></div></div>
<header class="hero"><div class="hero-inner"><div><div class="portal-kicker">TUNNEL DIGITAL RESOURCE PLATFORM</div><h1>隧道开挖智慧数据中心</h1><p>融合超欠挖成果、监控量测、断面图、三维模型、数据包自动建模和智慧大脑问答，形成可检索、可追踪、可演示的隧道数字孪生门户。</p><div class="portal-search"><input id="portalSearch" placeholder="搜索隧道名称、桩号、测点或资料，例如 DK082+580"><button id="portalSearchBtn" type="button">搜索数据资源</button></div><div class="portal-hero-actions"><button type="button" data-jump="model3d">三维空间查询</button><button class="secondary" type="button" data-jump="ingest">上传数据包建模</button></div><div class="portal-keywords"><span>超欠挖分析</span><span>断面测试位点</span><span>点云/OBJ/PLY</span><span>RAG 知识底座</span><span>本地 Qwen 智慧大脑</span></div></div><div class="portal-stat-panel"><div class="portal-stat-title"><b id="portalActiveTunnel">当前隧道</b><span>资源统计</span></div><div class="portal-stat-grid"><div class="portal-stat"><span>断面/记录</span><b id="portalSections">-</b></div><div class="portal-stat"><span>风险预警</span><b id="portalAlerts">-</b></div><div class="portal-stat"><span>最大超挖</span><b id="portalMaxOver">-</b></div><div class="portal-stat"><span>三维模型</span><b id="portalModel">-</b></div></div><div class="portal-tags"><div class="portal-tag" data-jump="overbreak">超欠挖</div><div class="portal-tag" data-jump="monitoring">监控量测</div><div class="portal-tag" data-jump="model3d">三维展示</div><div class="portal-tag" data-jump="resources">资料成果</div></div></div></div></header>
<div class="brain"><div class="brainIntro"><div><div class="title">智慧大脑</div><div class="brain-sub">支持连续追问，自动携带当前隧道和最近对话上下文。</div><div class="brainLimit" id="brainLimit"></div></div><div class="brainTools"><button class="secondary" id="brainClear" type="button">清空上下文</button></div></div><div class="brainMessages" id="brainMessages"></div><div class="brainComposer"><input id="brainQuestion" placeholder="例如：东安隧道超挖最严重的断面在哪里？"><button id="brainAsk" type="button">发送</button></div></div>
<div class="topbar"><div class="selector"><b>当前隧道</b><select id="tunnelSelect"></select></div><nav id="tabs"></nav></div>
<main>
  <section id="overview" class="active">
    <div class="grid cards" id="cards"></div>
    <div class="grid two" style="margin-top:14px"><div class="panel"><h2 id="tunnelTitle"></h2><p id="tunnelDesc" class="muted"></p><div id="projectSummary"></div></div><div class="panel"><h2>预警概况</h2><div class="alert-summary" id="alertStats"></div><div class="svgbox" id="alertChart"></div></div></div>
    <div class="grid two"><div class="panel"><h3>超挖面积趋势</h3><div class="svgbox" id="overbreakTrend"></div></div><div class="panel"><h3>监控量测最大值</h3><div id="monitorTop"></div></div></div>
  </section>
  <section id="alerts"><div class="panel"><h2>风险预警</h2><div class="toolbar"><input id="alertSearch" placeholder="搜索测点、桩号、类别"><select id="alertLevel"><option value="">全部等级</option><option>红色</option><option>橙色</option><option>黄色</option><option>正常</option></select></div><div class="table-wrap" id="alertTable"></div></div></section>
  <section id="monitoring"><div class="grid three"><div class="panel"><h3>地表下沉</h3><div class="svgbox" id="surfaceChart"></div></div><div class="panel"><h3>拱顶下沉</h3><div class="svgbox" id="crownChart"></div></div><div class="panel"><h3>周边收敛</h3><div class="svgbox" id="convChart"></div></div></div><div class="panel"><h2>监控量测数据表</h2><div class="toolbar"><select id="monitorType"><option value="surface">地表下沉</option><option value="crown">拱顶下沉</option><option value="convergence">周边收敛</option></select><input id="monitorSearch" placeholder="搜索测点"></div><div class="table-wrap" id="monitorTable"></div></div></section>
  <section id="overbreak">
    <div class="grid two"><div class="panel"><h3>超挖面积（横坐标：桩号/测试断面）</h3><div class="svgbox" id="overbreakAreaChart"></div></div><div class="panel"><h3>最大超挖深度（横坐标：桩号/测试断面）</h3><div class="svgbox" id="overbreakDepthChart"></div></div></div>
    <div class="grid two"><div class="panel"><h2>欠挖数据核对</h2><div id="underbreakSummary" class="muted"></div><div class="svgbox" id="underbreakChart"></div></div><div class="panel"><h2>图表交互说明</h2><p class="muted">鼠标移动到图表上，会显示对齐的 X/Y 准星、桩号/测试断面和数值。横坐标标签按断面抽样显示，完整桩号可通过悬停查看。</p></div></div>
    <div class="panel"><h2>测试断面数据图</h2><div class="toolbar"><b>选择测试断面/桩号</b><select id="sectionSelect"></select><span id="sectionQuality" class="tag"></span></div><div class="grid two"><div><div id="sectionMetrics" class="metric-grid"></div><div id="sectionLegend" class="muted"></div><div class="svgbox sectionbar" id="sectionMetricChart"></div></div><div class="svgbox sectionbox" id="sectionProfileChart"></div></div></div>
    <div class="panel"><h2>超欠挖断面明细</h2><div class="toolbar"><input id="overbreakSearch" placeholder="搜索桩号"></div><div class="table-wrap" id="overbreakTable"></div></div>
  </section>
  <section id="model3d"><div class="panel"><h2>三维展示</h2><div class="model-note"><span class="tag" id="modelKind">当前模型</span><span class="muted" id="modelHint">上传生成的模型已内置正常/超挖/欠挖点位筛选。</span></div><p class="muted model-desc">三维模型为当前已接入数据的综合示意、PDF 断面识别模型或上传数据自动建模结果。缺少原始 XYZ 点云时，不作为精确工程结算模型。</p><iframe class="iframe" id="modelFrame"></iframe></div></section>
  <section id="ingest"><div class="grid two"><div class="panel"><h2>数据包上传与自动建模</h2><div class="drop" id="dropZone"><input id="packageInput" type="file" multiple><p><b>把 CSV / JSON / XYZ / TXT / ZIP 数据包拖到这里</b></p><p class="muted">推荐字段：station/桩号、x/里程、y/横向、z/高程、deviation/偏差、status/超欠挖类型、over_area/under_area。上传后会自动保存、解析、生成 3D HTML/OBJ，并标注超挖/欠挖点位。</p><div class="upload-files" id="uploadFiles">尚未选择文件。</div><button id="packageUpload">上传并自动生成 3D 模型</button><div id="packageResult" class="uploadResult muted"></div></div></div><div class="panel"><h2>接口状态</h2><p>上传并建模：<span class="api">POST /api/packages/upload</span></p><p>上传隧道列表：<span class="api">GET /api/uploaded-tunnels</span></p><p>改名/删除：<span class="api">POST /api/uploaded-tunnels/rename</span> / <span class="api">delete</span></p><h3>支持文件</h3><div id="supportedFiles" class="muted"></div></div></div><div class="panel"><h2>上传隧道管理</h2><p class="muted">上传成功的数据会自动加入顶部“当前隧道”列表。你可以在这里改名称，或删除过期测试数据及其模型文件。</p><div id="uploadedTunnelManager" class="manage-list"></div></div><div class="grid two"><div class="panel"><h2>3D 隧道建模需要什么数据</h2><div id="requiredData" class="guide-list"></div></div><div class="panel"><h2>推荐整理格式</h2><div id="formatMatrix" class="guide-list"></div></div></div><div class="grid two"><div class="panel"><h2>网页自动生成模型需要调用什么工具</h2><div id="toolchain" class="toolchain"></div></div><div class="panel"><h2>上传后的自动建模流程</h2><ol id="pipeline" class="muted"></ol><h3>质量检查</h3><ul id="qualityChecks" class="muted"></ul><h3>参考资料</h3><div id="sourceLinks" class="source-list"></div></div></div></section>
  <section id="resources"><div class="grid two"><div class="panel resource"><h2>资料与成果文件</h2><div id="resourcesList"></div></div><div class="panel"><h2>平台说明</h2><ul id="notes" class="muted"></ul></div></div></section>
</main>
<script>
const DATA=__DATA__;
const TABS=[["overview","总览"],["alerts","风险预警"],["monitoring","监控量测"],["overbreak","超欠挖"],["model3d","三维展示"],["ingest","数据接入"],["resources","资料管理"]];
let currentId=DATA.tunnelOrder[0];
const $=id=>document.getElementById(id);
const sectionSelections={};
const BRAIN_STORAGE_KEY="tunnelBrainHistoryV1";
const BRAIN_CONTEXT_MAX_MESSAGES=20;
const BRAIN_CONTEXT_MAX_CHARS=10000;
const BRAIN_STORE_LIMIT=80;
let brainHistory=[];
let selectedUploadFiles=[];
let uploadedEntries=[];
function cur(){return DATA.tunnels[currentId]}
function esc(x){return String(x??"").replace(/[&<>"']/g,s=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[s]))}
function empty(msg){return `<div class="empty">${esc(msg)}</div>`}
function table(rows,cols){if(!rows||!rows.length)return empty("当前隧道暂无该类数据。");cols=cols||Object.keys(rows[0]);return `<table><thead><tr>${cols.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${c==="level"?`<span class="pill ${esc(r[c])}">${esc(r[c])}</span>`:esc(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function formatValue(v,decimals){return Number(v).toFixed(decimals??2)}
function uploadedId(batchId){return `uploaded:${batchId}`}
function uploadTunnelFromEntry(entry){const s=entry.model_stats||{},created=entry.created_at?new Date(entry.created_at*1000).toLocaleString():"";return {id:uploadedId(entry.batch_id),name:entry.name||`上传模型 ${entry.batch_id}`,description:`上传数据自动建模批次：${entry.batch_id}`,overview:{"批次号":entry.batch_id,"上传时间":created,"来源隧道":entry.source_tunnel_id||"uploaded","说明":"该条目由数据接入页面上传生成，可在上传隧道管理区改名或删除。"},cards:{"识别记录":entry.recognized_records||0,"空间点":s.spacePoints||0,"断面数":s.meshSections||0,"超挖点":s.overPoints||0,"欠挖点":s.underPoints||0,"正常点":s.normalPoints||0,"模型":"已生成","来源":"上传"},alerts:[],alertStats:{byLevel:{},byCategory:{}},overbreak:{rows:[],series:[],underbreakSeries:[],maxDepthSeries:[],maxUnderDepthSeries:[],sectionProfiles:[],underbreakAudit:{message:"上传模型的超欠挖点位请在三维展示中通过左侧筛选查看。",underbreakCount:s.underPoints||0,maxUnderbreakArea:0,maxUnderbreakDepth:0}},monitoring:{tops:{},series:{"地表下沉":[],"拱顶下沉":[],"周边收敛":[]},surface:[],crown:[],convergence:[]},resources:[{name:"上传生成 3D HTML 模型",path:entry.model_url},{name:"上传生成 OBJ 模型",path:entry.obj_url},{name:"上传批次 manifest",path:entry.manifest_url}],modelUrl:entry.model_url,notes:[`上传批次 ${entry.batch_id}`,"三维模型内置正常/超挖/欠挖点位筛选，勾选后才显示点位，悬停查看坐标。"]}}
function mergeUploadedEntries(entries){const uploadedIds=DATA.tunnelOrder.filter(id=>id.startsWith("uploaded:"));uploadedIds.forEach(id=>delete DATA.tunnels[id]);DATA.tunnelOrder=DATA.tunnelOrder.filter(id=>!id.startsWith("uploaded:"));uploadedEntries=entries||[];uploadedEntries.forEach(entry=>{const t=uploadTunnelFromEntry(entry);DATA.tunnels[t.id]=t;DATA.tunnelOrder.push(t.id)})}
function renderTunnelSelect(){const select=$("tunnelSelect");if(!DATA.tunnels[currentId])currentId=DATA.tunnelOrder[0];select.innerHTML=DATA.tunnelOrder.map(id=>`<option value="${id}">${esc(DATA.tunnels[id].name)}</option>`).join("");select.value=currentId}
function activateTab(tabId){const btn=document.querySelector(`#tabs button[data-tab="${tabId}"]`);if(!btn)return;document.querySelectorAll("#tabs button").forEach(x=>x.classList.toggle("active",x===btn));document.querySelectorAll("main section").forEach(s=>s.classList.toggle("active",s.id===tabId));window.scrollTo({top:document.querySelector(".topbar").offsetTop,behavior:"smooth"})}
function renderPortalStats(){const t=cur();if(!$("portalActiveTunnel"))return;const rows=t.overbreak&&t.overbreak.rows?t.overbreak.rows:[],profiles=t.overbreak&&t.overbreak.sectionProfiles?t.overbreak.sectionProfiles:[];$("portalActiveTunnel").textContent=t.name;$("portalSections").textContent=rows.length||profiles.length||t.cards["断面数"]||t.cards["识别记录"]||0;$("portalAlerts").textContent=(t.alerts||[]).length;$("portalMaxOver").textContent=(t.overbreak&&t.overbreak.maxDepthSeries&&t.overbreak.maxDepthSeries.length)?`${Math.max(...t.overbreak.maxDepthSeries.map(x=>Number(x.y)||0)).toFixed(3)} m`:"-";$("portalModel").textContent=t.modelUrl?"已接入":"待生成"}
function runPortalSearch(){const q=$("portalSearch").value.trim();if(!q){activateTab("overview");return}const tunnelId=DATA.tunnelOrder.find(id=>DATA.tunnels[id].name.includes(q));if(tunnelId){currentId=tunnelId;renderTunnelSelect();renderAll();activateTab("overview");return}const t=cur();if((t.overbreak.rows||[]).some(r=>JSON.stringify(r).includes(q))||(t.overbreak.sectionProfiles||[]).some(r=>JSON.stringify(r).includes(q))){$("overbreakSearch").value=q;renderOverbreak();activateTab("overbreak");return}if(["surface","crown","convergence"].some(k=>(t.monitoring[k]||[]).some(r=>JSON.stringify(r).includes(q)))){$("monitorSearch").value=q;renderMonitoring();activateTab("monitoring");return}if((t.resources||[]).some(r=>JSON.stringify(r).includes(q))){activateTab("resources");return}pushBrainMessage("assistant",`没有在当前结构化数据中直接匹配到“${q}”。可以在智慧大脑里继续追问，或上传包含该测点/桩号的数据包后再检索。`)}
async function loadUploadedTunnels(selectId){try{const r=await fetch("/api/uploaded-tunnels");const data=await r.json();if(data.items){mergeUploadedEntries(data.items);if(selectId&&DATA.tunnels[selectId])currentId=selectId;renderTunnelSelect();renderUploadManager();return data.items}}catch(e){console.warn("uploaded tunnels load failed",e)}renderTunnelSelect();renderUploadManager();return []}
function lineChart(el,points,opt={}){if(!points||!points.length){el.innerHTML=empty("当前隧道暂无趋势数据。");return}const w=940,h=300,L=54,R=24,T=24,B=66,values=points.map(d=>Number(d.y)),min=Math.min(0,...values),max=Math.max(...values,1),span=max-min||1;const xScale=i=>L+i*(w-L-R)/Math.max(1,points.length-1);const yScale=v=>h-B-(Number(v)-min)*(h-T-B)/span;const path=points.map((d,i)=>`${xScale(i)},${yScale(d.y)}`).join(" ");const area=`${L},${h-B} ${path} ${w-R},${h-B}`;const yTicks=[0,.25,.5,.75,1].map(t=>min+t*span);let xTickStep=Math.max(1,Math.ceil(points.length/8));const xTicks=points.map((d,i)=>({d,i})).filter(x=>x.i%xTickStep===0||x.i===points.length-1);el.innerHTML=`<svg viewBox="0 0 ${w} ${h}">${yTicks.map(v=>{const y=yScale(v);return `<line class="gridline" x1="${L}" y1="${y}" x2="${w-R}" y2="${y}"/><text x="${L-8}" y="${y+4}" text-anchor="end" font-size="11" fill="#65748b">${formatValue(v,opt.decimals??1)}</text>`}).join("")}<line class="axis" x1="${L}" y1="${h-B}" x2="${w-R}" y2="${h-B}"/><line class="axis" x1="${L}" y1="${T}" x2="${L}" y2="${h-B}"/><polyline class="area" points="${area}"/><polyline class="${opt.lineClass||"plot"}" points="${path}"/>${xTicks.map(({d,i})=>{const x=xScale(i);return `<line class="gridline" x1="${x}" y1="${h-B}" x2="${x}" y2="${h-B+5}"/><text x="${x}" y="${h-B+18}" text-anchor="middle" font-size="10" fill="#65748b" transform="rotate(35 ${x} ${h-B+18})">${esc(d.x)}</text>`}).join("")}<text x="${(L+w-R)/2}" y="${h-6}" text-anchor="middle" fill="#65748b" font-size="12">${esc(opt.xLabel||"桩号/测试断面")}</text><text x="${w-12}" y="18" text-anchor="end" fill="#65748b" font-size="12">${esc(opt.unit||"")}</text><line class="cross hx" x1="${L}" x2="${w-R}" y1="0" y2="0" style="display:none"/><line class="cross vx" y1="${T}" y2="${h-B}" x1="0" x2="0" style="display:none"/><circle class="dot hd" r="4" style="display:none"/><rect class="capture" x="${L}" y="${T}" width="${w-L-R}" height="${h-T-B}" fill="transparent"/></svg><div class="chartTip"></div>`;const svg=el.querySelector("svg"),tip=el.querySelector(".chartTip"),hx=el.querySelector(".hx"),vx=el.querySelector(".vx"),hd=el.querySelector(".hd");function hide(){tip.style.display="none";hx.style.display=vx.style.display=hd.style.display="none"}svg.addEventListener("mouseleave",hide);svg.addEventListener("mousemove",e=>{const pt=svg.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;const loc=pt.matrixTransform(svg.getScreenCTM().inverse());let idx=Math.round((loc.x-L)/(w-L-R)*(points.length-1));idx=Math.max(0,Math.min(points.length-1,idx));const d=points[idx],x=xScale(idx),y=yScale(d.y);hx.style.display=vx.style.display=hd.style.display="block";hx.setAttribute("y1",y);hx.setAttribute("y2",y);vx.setAttribute("x1",x);vx.setAttribute("x2",x);hd.setAttribute("cx",x);hd.setAttribute("cy",y);tip.style.display="block";tip.style.left=Math.min(el.clientWidth-190,Math.max(8,e.offsetX+12))+"px";tip.style.top=Math.max(8,e.offsetY-42)+"px";tip.innerHTML=`${esc(opt.xLabel||"桩号")}: ${esc(d.x)}<br>${esc(opt.name||"数值")}: ${formatValue(d.y,opt.decimals??2)} ${esc(opt.unit||"")}`})}
function sectionMetricChart(el,p){if(!p){el.innerHTML=empty("请选择测试断面。");return}const w=720,h=220,L=130,R=38,T=24,rowH=42;const areaMax=Math.max(Number(p.overArea),Number(p.underArea),0.001),depthMax=Math.max(Number(p.maxOver),Number(p.maxUnder),0.001);const bars=[["超挖面积",p.overArea,"㎡","#ffa500",areaMax],["欠挖面积",p.underArea,"㎡","#cf2e2e",areaMax],["最大超挖",p.maxOver,"m","#1767c2",depthMax],["最大欠挖",p.maxUnder,"m","#cf2e2e",depthMax]];el.innerHTML=`<svg viewBox="0 0 ${w} ${h}"><text x="${L}" y="16" fill="#65748b" font-size="12">当前断面超/欠挖指标对比</text>${bars.map((b,i)=>{const y=T+i*rowH+10,bw=Number(b[1])/b[4]*(w-L-R);return `<text x="${L-10}" y="${y+14}" text-anchor="end" fill="#43536a" font-size="12">${esc(b[0])}</text><rect x="${L}" y="${y}" width="${Math.max(1,bw)}" height="18" rx="5" fill="${b[3]}"></rect><text x="${L+Math.max(8,bw)+8}" y="${y+14}" fill="#182338" font-size="12">${formatValue(b[1],b[2]==="㎡"?3:3)} ${b[2]}</text>`}).join("")}</svg>`}
function sectionProfileChart(el,p){if(!p||!p.curve||!p.curve.length){el.innerHTML=empty("当前断面暂无可绘制的 PDF 轮廓数据。");return}const w=740,h=380,L=42,R=24,T=24,B=34;const curve=p.curve.map(q=>[Number(q[0]),Number(q[1])]);const tps=(p.testPoints||[]).map(q=>[Number(q.y),Number(q.z),q.status]);const all=curve.concat(tps.map(q=>[q[0],q[1]])).concat([[0,0]]);let minY=Math.min(...all.map(q=>q[0])),maxY=Math.max(...all.map(q=>q[0])),minZ=Math.min(...all.map(q=>q[1])),maxZ=Math.max(...all.map(q=>q[1]));const py=(maxY-minY)*.08||1,pz=(maxZ-minZ)*.10||1;minY-=py;maxY+=py;minZ-=pz;maxZ+=pz;const sx=y=>L+(y-minY)*(w-L-R)/(maxY-minY||1),sz=z=>h-B-(z-minZ)*(h-T-B)/(maxZ-minZ||1);const ticks=(a,b,n)=>Array.from({length:n},(_,i)=>a+(b-a)*i/(n-1));const path=curve.map((q,i)=>`${i?"L":"M"}${sx(q[0]).toFixed(1)},${sz(q[1]).toFixed(1)}`).join(" ");el.innerHTML=`<svg viewBox="0 0 ${w} ${h}">${ticks(minY,maxY,7).map(v=>`<line class="gridline" x1="${sx(v)}" y1="${T}" x2="${sx(v)}" y2="${h-B}"/><text x="${sx(v)}" y="${h-12}" text-anchor="middle" fill="#8a99ad" font-size="10">${formatValue(v,1)}</text>`).join("")}${ticks(minZ,maxZ,6).map(v=>`<line class="gridline" x1="${L}" y1="${sz(v)}" x2="${w-R}" y2="${sz(v)}"/><text x="${L-8}" y="${sz(v)+4}" text-anchor="end" fill="#8a99ad" font-size="10">${formatValue(v,1)}</text>`).join("")}<line x1="${sx(0)}" x2="${sx(0)}" y1="${T}" y2="${h-B}" stroke="#9aa9bd" stroke-dasharray="3 3"/><line x1="${L}" x2="${w-R}" y1="${sz(0)}" y2="${sz(0)}" stroke="#cf2e2e" stroke-dasharray="3 3"/><path d="${path} Z" fill="rgba(255,165,0,.08)" stroke="#111" stroke-width="1.4"/><text x="${w-10}" y="${sz(0)-6}" text-anchor="end" fill="#cf2e2e" font-size="11">0 基线</text>${tps.map(q=>{const color=q[2]==="欠挖"?"#cf2e2e":q[2]==="正常"?"#23854b":"#ffa500";return `<circle cx="${sx(q[0])}" cy="${sz(q[1])}" r="3" fill="${color}" opacity=".9"><title>y=${formatValue(q[0],3)}, z=${formatValue(q[1],3)}</title></circle>`}).join("")}<text x="${(L+w-R)/2}" y="${h-2}" text-anchor="middle" fill="#65748b" font-size="12">横向位置 y / m</text><text x="${w-12}" y="18" text-anchor="end" fill="#65748b" font-size="12">竖向 z / m</text></svg>`}
function renderSectionDetail(profile){if(!profile){$("sectionMetrics").innerHTML=empty("请选择测试断面。");$("sectionLegend").innerHTML="";sectionMetricChart($("sectionMetricChart"),null);sectionProfileChart($("sectionProfileChart"),null);$("sectionQuality").textContent="暂无";return}$("sectionQuality").textContent=profile.valid?"PDF轮廓完整提取":profile.extracted?"PDF轮廓补齐/质量有限":"无 PDF 轮廓";const items=[["桩号",profile.station,""],["超挖面积",formatValue(profile.overArea,3),"㎡"],["欠挖面积",formatValue(profile.underArea,3),"㎡"],["最大超挖",formatValue(profile.maxOver,3),"m"],["最大欠挖",formatValue(profile.maxUnder,3),"m"],["测试位点",profile.testPointCount,"个"]];$("sectionMetrics").innerHTML=items.map(([k,v,u])=>`<div class="metric"><span class="label">${esc(k)}</span><b>${esc(v)} ${esc(u)}</b></div>`).join("");$("sectionLegend").innerHTML=`<p><b>数据说明：</b>${esc(profile.sourceNote)}</p><div class="legend-line"><span class="legend-item"><i class="legend-dot" style="background:#ffa500"></i>PDF 测试位点：${profile.testPointCount} 个</span><span class="legend-item"><i class="legend-dot" style="background:#cf2e2e"></i>欠挖点位/断面：${(profile.statusCounts&&profile.statusCounts["欠挖"])||0}</span><span class="legend-item"><i class="legend-dot" style="background:#23854b"></i>正常点位：${(profile.statusCounts&&profile.statusCounts["正常"])||0}（待原始分类数据）</span><span class="legend-item"><i class="legend-dot" style="background:#111"></i>PDF 断面轮廓</span></div>`;sectionMetricChart($("sectionMetricChart"),profile);sectionProfileChart($("sectionProfileChart"),profile)}
function renderSectionSelector(t){const profiles=t.overbreak.sectionProfiles||[],select=$("sectionSelect");if(!profiles.length){select.innerHTML='<option value="">暂无测试断面</option>';renderSectionDetail(null);return}const chosen=sectionSelections[currentId]&&profiles.some(p=>p.station===sectionSelections[currentId])?sectionSelections[currentId]:profiles[0].station;sectionSelections[currentId]=chosen;select.innerHTML=profiles.map(p=>`<option value="${esc(p.station)}">${esc(p.station)} ｜超挖 ${formatValue(p.overArea,3)}㎡ ｜欠挖 ${formatValue(p.underArea,3)}㎡</option>`).join("");select.value=chosen;renderSectionDetail(profiles.find(p=>p.station===chosen)||profiles[0])}
function barChart(el,obj){const entries=Object.entries(obj||{});if(!entries.length){el.innerHTML=empty("暂无预警统计。");return}const w=720,h=240,p=36,max=Math.max(...entries.map(x=>x[1]),1);el.innerHTML=`<svg viewBox="0 0 ${w} ${h}">${entries.map(([k,v],i)=>{const bw=(w-2*p)/entries.length*.62,x=p+i*(w-2*p)/entries.length+bw*.3,bh=v*(h-2*p)/max,y=h-p-bh;return `<rect x="${x}" y="${y}" width="${bw}" height="${bh}" rx="5" fill="#1767c2"><title>${esc(k)}: ${v}</title></rect><text x="${x+bw/2}" y="${h-12}" text-anchor="middle" font-size="12" fill="#65748b">${esc(k)}</text><text x="${x+bw/2}" y="${y-6}" text-anchor="middle" font-size="12" fill="#182338">${v}</text>`}).join("")}</svg>`}
function renderCards(){const t=cur();$("cards").innerHTML=Object.entries(t.cards).map(([k,v])=>`<div class="card"><div class="label">${esc(k)}</div><div class="value">${esc(v)}</div></div>`).join("")}
function renderSummary(){const t=cur();$("tunnelTitle").textContent=t.name;$("tunnelDesc").textContent=t.description;$("projectSummary").innerHTML=Object.entries(t.overview).map(([k,v])=>`<p><b>${esc(k)}：</b>${esc(v)}</p>`).join("");$("alertStats").innerHTML=Object.entries(t.alertStats.byLevel).map(([k,v])=>`<span class="tag"><span class="pill ${esc(k)}">${esc(k)}</span> ${v} 条</span>`).join("")||"<span class='tag'>暂无预警</span>";barChart($("alertChart"),t.alertStats.byCategory);lineChart($("overbreakTrend"),t.overbreak.series,{unit:"㎡",decimals:2,name:"超挖面积"});renderMonitorTop()}
function renderMonitorTop(){const tops=cur().monitoring.tops;const parts=[];for(const k of ["地表下沉","拱顶下沉","周边收敛"]){const r=(tops[k]||[])[0];if(!r)continue;const value=k==="周边收敛"?r["本期收敛(mm)"]:r["本期沉降(mm)"];parts.push(`<p><b>${k}：</b>${esc(r["测点"])}，本期 ${esc(value)} mm，结果 ${esc(r["结果分析"])}</p>`)}$("monitorTop").innerHTML=parts.length?parts.join(""):empty("当前隧道暂无监控量测数据。")}
function renderAlerts(){const t=cur(),q=$("alertSearch").value.trim(),level=$("alertLevel").value;const rows=t.alerts.filter(r=>(!level||r.level===level)&&(!q||JSON.stringify(r).includes(q)));$("alertTable").innerHTML=table(rows,["level","category","item","value","threshold","advice"])}
function renderMonitoring(){const t=cur();lineChart($("surfaceChart"),t.monitoring.series["地表下沉"],{unit:"mm",decimals:1,name:"地表下沉",xLabel:"测点"});lineChart($("crownChart"),t.monitoring.series["拱顶下沉"],{unit:"mm",decimals:1,name:"拱顶下沉",xLabel:"测点"});lineChart($("convChart"),t.monitoring.series["周边收敛"],{unit:"mm",decimals:1,name:"周边收敛",xLabel:"测点"});const type=$("monitorType").value,q=$("monitorSearch").value.trim();const rows=t.monitoring[type].filter(r=>!q||JSON.stringify(r).includes(q));$("monitorTable").innerHTML=table(rows)}
function renderOverbreak(){const t=cur();lineChart($("overbreakAreaChart"),t.overbreak.series,{unit:"㎡",decimals:3,name:"超挖面积",xLabel:"桩号/测试断面"});lineChart($("overbreakDepthChart"),t.overbreak.maxDepthSeries,{unit:"m",decimals:3,name:"最大超挖深度",xLabel:"桩号/测试断面"});const audit=t.overbreak.underbreakAudit;$("underbreakSummary").innerHTML=audit?`<p><b>核对结果：</b>${esc(audit.message)}</p><p>欠挖断面数：${audit.underbreakCount}；最大欠挖面积：${Number(audit.maxUnderbreakArea).toFixed(3)} ㎡；最大欠挖深度：${Number(audit.maxUnderbreakDepth).toFixed(3)} m。</p>`:empty("暂无欠挖核对数据。");lineChart($("underbreakChart"),t.overbreak.underbreakSeries,{unit:"㎡",decimals:3,name:"欠挖面积",xLabel:"桩号/测试断面",lineClass:"plot2"});renderSectionSelector(t);const q=$("overbreakSearch").value.trim();$("overbreakTable").innerHTML=table(t.overbreak.rows.filter(r=>!q||r["桩号"].includes(q)))}
function renderResources(){const t=cur();$("resourcesList").innerHTML=(t.resources||[]).map(r=>`<a href="${esc(r.path)}" target="_blank">${esc(r.name)}<br><span class="muted">${esc(r.path)}</span></a>`).join("")||empty("当前隧道暂无资料链接。");$("notes").innerHTML=[...(t.notes||[]),...DATA.notes].map(x=>`<li>${esc(x)}</li>`).join("");$("modelFrame").src=t.modelUrl;$("modelKind").textContent=currentId.startsWith("uploaded:")?"上传生成模型":"内置模型";$("modelHint").textContent=currentId.startsWith("uploaded:")?"该模型已整合点位筛选：勾选正常/超挖/欠挖后显示点位，悬停查看坐标。":"内置模型用于展示既有资料；上传模型会在这里显示点位筛选工具。"}
function guideCard(title,body,extra=""){return `<div class="guide-card"><h4>${title}</h4>${body}${extra}</div>`}
function renderUploadManager(){const box=$("uploadedTunnelManager");if(!box)return;if(!uploadedEntries.length){box.innerHTML=empty("当前还没有上传生成的隧道模型。");return}box.innerHTML=uploadedEntries.map(entry=>{const s=entry.model_stats||{},created=entry.created_at?new Date(entry.created_at*1000).toLocaleString():"";return `<div class="manage-item" data-batch="${esc(entry.batch_id)}"><div class="manage-head"><div><b>${esc(entry.name)}</b><p class="muted">批次：${esc(entry.batch_id)}　上传：${esc(created)}　记录：${esc(entry.recognized_records||0)}　断面：${esc(s.meshSections||0)}　超挖：${esc(s.overPoints||0)}　欠挖：${esc(s.underPoints||0)}</p></div><div class="manage-actions"><button class="small-btn" data-action="view">查看</button><button class="small-btn danger" data-action="delete">删除过期数据</button></div></div><div class="manage-actions"><input value="${esc(entry.name)}" data-name><button class="small-btn" data-action="rename">保存名称</button><a href="${esc(entry.model_url)}" target="_blank">模型</a><a href="${esc(entry.obj_url)}" target="_blank">OBJ</a></div></div>`}).join("")}
function renderIngest(){const ing=DATA.ingestion,guide=DATA.modelingGuide||{};$("pipeline").innerHTML=(guide.automationFlow||ing.pipeline).map(x=>`<li>${esc(x)}</li>`).join("");$("supportedFiles").innerHTML=ing.supportedFiles.map(x=>`<span class="tag">${esc(x)}</span>`).join(" ");$("requiredData").innerHTML=(guide.requiredData||[]).map(x=>guideCard(`${esc(x.name)} <span class="level">${esc(x.level)}</span>`,`<p><b>格式：</b>${esc(x.formats)}</p><p><b>字段：</b>${esc(x.fields)}</p><p class="muted">${esc(x.why)}</p>`)).join("");$("formatMatrix").innerHTML=(guide.formats||[]).map(x=>guideCard(esc(x.stage),`<p><b>${esc(x.format)}</b></p><p class="muted">${esc(x.note)}</p>`)).join("");$("toolchain").innerHTML=(guide.toolchain||[]).map(x=>guideCard(esc(x.part),`<p><b>工具：</b>${esc(x.tools)}</p><p class="muted">${esc(x.role)}</p>`)).join("");$("qualityChecks").innerHTML=(guide.qualityChecks||[]).map(x=>`<li>${esc(x)}</li>`).join("");$("sourceLinks").innerHTML=(guide.references||[]).map(x=>`<a href="${esc(x.url)}" target="_blank">${esc(x.name)}</a>`).join("");renderUploadManager()}
function renderAll(){renderCards();renderSummary();renderAlerts();renderMonitoring();renderOverbreak();renderResources();renderIngest();renderPortalStats()}
function initTabs(){$("tabs").innerHTML=TABS.map(([id,label],i)=>`<button data-tab="${id}" class="${i===0?"active":""}">${label}</button>`).join("");$("tabs").onclick=e=>{const b=e.target.closest("button");if(!b)return;activateTab(b.dataset.tab)}}
function initTunnelSelect(){renderTunnelSelect();$("tunnelSelect").onchange=e=>{currentId=e.target.value;renderAll()}}
function initPortal(){document.querySelectorAll("[data-jump]").forEach(el=>el.addEventListener("click",()=>activateTab(el.dataset.jump)));$("portalSearchBtn").onclick=runPortalSearch;$("portalSearch").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();runPortalSearch()}})}
function loadBrainHistory(){try{const raw=localStorage.getItem(BRAIN_STORAGE_KEY);brainHistory=raw?JSON.parse(raw):[];if(!Array.isArray(brainHistory))brainHistory=[]}catch(e){brainHistory=[]}}
function saveBrainHistory(){try{localStorage.setItem(BRAIN_STORAGE_KEY,JSON.stringify(brainHistory.slice(-BRAIN_STORE_LIMIT)))}catch(e){}}
function brainWindow(){const rows=brainHistory.filter(m=>!m.pending).slice().reverse();const picked=[];let chars=0;for(const m of rows){const len=String(m.content||"").length;if(picked.length>=BRAIN_CONTEXT_MAX_MESSAGES||chars+len>BRAIN_CONTEXT_MAX_CHARS)break;picked.push(m);chars+=len}return picked.reverse()}
function renderBrainMessages(){const box=$("brainMessages");const msgs=brainWindow();$("brainLimit").textContent=`上下文动态窗口：最多 ${BRAIN_CONTEXT_MAX_MESSAGES} 条 / ${BRAIN_CONTEXT_MAX_CHARS} 字，可见区最高 420px`;if(!msgs.length){box.innerHTML=`<div class="brainEmpty">可以直接问当前隧道的数据问题，也可以连续追问，例如“这个断面的最大超挖是多少？”“给出处理建议”。聊天窗口会随内容自动变高，超过上限后滚动显示。</div>`;box.scrollTop=0;return}box.innerHTML=msgs.map(m=>`<div class="brainMsg ${m.role==="user"?"user":"assistant"}"><div class="brainBubble"><span class="brainMeta">${m.role==="user"?"我": "智慧大脑"} · ${esc(m.tunnel_name||"当前隧道")}</span>${esc(m.content)}</div></div>`).join("");box.scrollTop=box.scrollHeight}
function pushBrainMessage(role,content,extra={}){brainHistory.push({role,content,tunnel_id:extra.tunnel_id||currentId,tunnel_name:extra.tunnel_name||cur().name,time:new Date().toISOString(),pending:!!extra.pending});brainHistory=brainHistory.slice(-BRAIN_STORE_LIMIT);saveBrainHistory();renderBrainMessages()}
async function askBrain(){const q=$("brainQuestion").value.trim();if(!q){pushBrainMessage("assistant","请输入问题后再发送。");return}const prior=brainWindow();$("brainQuestion").value="";pushBrainMessage("user",q);const pendingId=`pending-${Date.now()}`;brainHistory.push({role:"assistant",content:"正在分析当前隧道数据和最近对话...",tunnel_id:currentId,tunnel_name:cur().name,time:new Date().toISOString(),pending:true,id:pendingId});renderBrainMessages();try{const r=await fetch(DATA.brain.endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tunnel_id:currentId,question:q,history:prior})});const data=await r.json();const msg=data.message||data.answer||"接口已预留，等待模型接入后可回答该问题。";const item=brainHistory.find(m=>m.id===pendingId);if(item){item.content=msg;item.pending=false}else{brainHistory.push({role:"assistant",content:msg,tunnel_id:currentId,tunnel_name:cur().name,time:new Date().toISOString()})}saveBrainHistory();renderBrainMessages()}catch(e){const item=brainHistory.find(m=>m.id===pendingId);if(item){item.content="当前接口暂时不可用，请稍后重试。";item.pending=false}saveBrainHistory();renderBrainMessages()}}
function initBrain(){loadBrainHistory();renderBrainMessages();$("brainAsk").onclick=askBrain;$("brainQuestion").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();askBrain()}});$("brainClear").onclick=()=>{brainHistory=[];saveBrainHistory();renderBrainMessages()}}
function setUploadFiles(files){selectedUploadFiles=[...files];$("uploadFiles").textContent=selectedUploadFiles.length?`已选择 ${selectedUploadFiles.length} 个文件：${selectedUploadFiles.map(f=>f.name).join("、")}`:"尚未选择文件。"}
function uploadResultHtml(data){const stats=data.model_stats||{};const links=data.model_url?`<p><a href="${esc(data.model_url)}" target="_blank">打开 3D HTML 模型</a>　<a href="${esc(data.obj_url)}" target="_blank">下载 OBJ</a>　<a href="${esc(data.manifest_url)}" target="_blank">查看 manifest</a></p>`:"";const statText=Object.entries(stats).map(([k,v])=>`<span class="tag">${esc(k)}: ${esc(v)}</span>`).join(" ");const warns=(data.warnings||[]).length?`<div class="upload-warn"><b>质量提示</b>${data.warnings.map(x=>`<p>${esc(x)}</p>`).join("")}</div>`:"";return `<div class="upload-ok"><b>${esc(data.message||"上传完成")}</b><p>批次：${esc(data.batch_id||"-")}；识别记录：${esc(data.recognized_records??0)} 条；已加入顶部隧道列表。</p><p>${statText}</p>${links}</div>${warns}`}
async function postJson(url,payload){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await r.json();if(!r.ok)throw new Error(data.message||data.error||"操作失败");return data}
async function renameUploadedTunnel(batchId,name){await postJson("/api/uploaded-tunnels/rename",{batch_id:batchId,name});await loadUploadedTunnels(uploadedId(batchId));renderAll()}
async function deleteUploadedTunnel(batchId){const entry=uploadedEntries.find(x=>x.batch_id===batchId);if(!confirm(`确定删除上传隧道“${entry?entry.name:batchId}”？\\n这会删除该批次的上传文件和生成模型。`))return;await postJson("/api/uploaded-tunnels/delete",{batch_id:batchId});if(currentId===uploadedId(batchId))currentId=DATA.tunnelOrder.find(id=>!id.startsWith("uploaded:"))||DATA.tunnelOrder[0];await loadUploadedTunnels(currentId);renderAll()}
function initUploadManager(){const box=$("uploadedTunnelManager");box.addEventListener("click",async e=>{const btn=e.target.closest("[data-action]");if(!btn)return;const item=btn.closest(".manage-item"),batchId=item&&item.dataset.batch;if(!batchId)return;try{if(btn.dataset.action==="view"){currentId=uploadedId(batchId);renderTunnelSelect();renderAll();const tab=document.querySelector('button[data-tab="model3d"]');if(tab)tab.click()}else if(btn.dataset.action==="rename"){await renameUploadedTunnel(batchId,item.querySelector("[data-name]").value.trim())}else if(btn.dataset.action==="delete"){await deleteUploadedTunnel(batchId)}}catch(err){alert(err.message||err)}})}
function initUpload(){const input=$("packageInput"),drop=$("dropZone");input.onchange=e=>setUploadFiles(e.target.files);["dragenter","dragover"].forEach(evt=>drop.addEventListener(evt,e=>{e.preventDefault();drop.classList.add("drag")}));["dragleave","drop"].forEach(evt=>drop.addEventListener(evt,e=>{e.preventDefault();drop.classList.remove("drag")}));drop.addEventListener("drop",e=>setUploadFiles(e.dataTransfer.files));$("packageUpload").onclick=async()=>{const files=selectedUploadFiles.length?selectedUploadFiles:[...input.files];if(!files.length){$("packageResult").innerHTML='<div class="upload-warn">请先选择或拖入数据文件。</div>';return}$("packageResult").innerHTML=`<div class="upload-warn">正在上传 ${files.length} 个文件并生成模型，请稍等...</div>`;try{const body=new FormData();files.forEach(f=>body.append("files",f));body.append("tunnel_id",currentId);body.append("tunnel_name",cur().name);const r=await fetch(DATA.ingestion.uploadEndpoint,{method:"POST",body});const data=await r.json();if(!r.ok)throw new Error(data.message||data.error||"上传失败");$("packageResult").innerHTML=uploadResultHtml(data);const newId=data.entry&&data.entry.id?data.entry.id:uploadedId(data.batch_id);await loadUploadedTunnels(newId);renderAll();const btn=document.querySelector('button[data-tab="model3d"]');if(btn)btn.click()}catch(e){$("packageResult").innerHTML=`<div class="upload-warn"><b>上传或建模失败</b><p>${esc(e.message||e)}</p><p>请检查是否包含 station/x/y/z/status/deviation 或 station/over_area/under_area 字段。</p></div>`}}}
async function init(){initTabs();initPortal();initTunnelSelect();initBrain();initUpload();initUploadManager();await loadUploadedTunnels(currentId);renderAll();["alertSearch","alertLevel"].forEach(id=>$(id).addEventListener("input",renderAlerts));["monitorType","monitorSearch"].forEach(id=>$(id).addEventListener("input",renderMonitoring));$("overbreakSearch").addEventListener("input",renderOverbreak);$("sectionSelect").addEventListener("change",e=>{sectionSelections[currentId]=e.target.value;const profile=(cur().overbreak.sectionProfiles||[]).find(p=>p.station===e.target.value);renderSectionDetail(profile)})}
init();
</script>
</body>
</html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_assets()
    payload = build_payload()
    (OUT / "control_data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "platform": str(OUT / "index.html"),
                "tunnels": [payload["tunnels"][i]["name"] for i in payload["tunnelOrder"]],
                "alerts": {i: len(payload["tunnels"][i]["alerts"]) for i in payload["tunnelOrder"]},
                "underbreak_audit": payload["tunnels"]["east"]["overbreak"]["underbreakAudit"],
                "reserved_api": {"brain": payload["brain"]["endpoint"], "upload": payload["ingestion"]["uploadEndpoint"]},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
