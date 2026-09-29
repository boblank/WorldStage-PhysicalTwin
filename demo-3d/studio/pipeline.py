"""WorldStage demo: six inspectable skill stages and an optional local LLM.

The fallback is intentionally labeled as a template. It is useful for offline demos,
but never presented as an AI inference result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ALLOWED = {"tree", "crystal", "tower", "orb", "arch", "book", "portal"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(data)
    return _sha(data)


def _theme(prompt: str) -> dict[str, Any]:
    q = prompt.lower()
    if any(word in q for word in ("森林", "树", "蘑菇", "forest", "garden")):
        return {"key": "forest", "title": "夜光森林", "subtitle": "会回应访客的微型森林剧场", "colors": ["#0b2231", "#83d6ab", "#ffbc83"], "types": ["tree", "tree", "crystal", "orb", "arch", "portal"], "names": ["守夜古树", "月影幼苗", "露光晶簇", "萤火星核", "苔藓拱门", "黎明之门"], "stories": ["古树记得每个走进森林的人，树冠亮起便是它的回答。", "幼苗会朝最近的声音生长，把路留给后来者。", "露珠把昨夜的星光收在晶面里，轻触就会闪烁。", "萤火虫围着光核飞行，替迷路的人标出方向。", "穿过拱门，脚下的苔藓会记录新的旅程。", "当六处光源醒来，森林便把黎明交还给天空。"], "chapter": "每次触碰都会改变林间的光与故事。"}
    if any(word in q for word in ("海底", "海洋", "潮汐", "海水", "鲸", "ocean", "underwater")):
        return {"key": "ocean", "title": "潮汐档案馆", "subtitle": "一座随潮汐醒来的海底藏书城", "colors": ["#071c35", "#2accc5", "#e9b777"], "types": ["arch", "book", "crystal", "orb", "tower", "portal"], "names": ["珊瑚入口", "漂流之书", "盐光水晶", "潮汐罗盘", "深蓝灯塔", "回声海门"], "stories": ["珊瑚在潮起时展开，替新的访客打开馆门。", "这本书记录每一条洋流走过的路线。", "水晶保存海面落下的最后一束日光。", "罗盘指向今晚尚未被讲述的故事。", "灯塔让归来的鱼群找到安全的通道。", "海门一开，六段记忆便重新汇入大海。"], "chapter": "触碰珊瑚灯，唤醒沉睡的海洋故事。"}
    if any(word in q for word in ("城", "都市", "city", "cyber", "未来")):
        return {"key": "city", "title": "浮空城之夜", "subtitle": "一座由访客点亮的未来微城", "colors": ["#161b43", "#8ca8ff", "#ffae8a"], "types": ["tower", "tower", "arch", "orb", "crystal", "portal"], "names": ["云端电站", "星航塔台", "空轨车站", "城市心核", "记忆终端", "远行传送门"], "stories": ["电站收集日落后的余温，为整座城续航。", "塔台会为夜航者留下一条发光的航线。", "轨道连起远处的街区，也让失散的人重逢。", "心核每跳动一次，街上的灯便亮起一片。", "终端保存居民写给未来的一封封短笺。", "传送门将这座城的下一章交给你的选择。"], "chapter": "点亮城中的设施，重排夜晚的运行方式。"}
    return {"key": "orbit", "title": "星屿实验室", "subtitle": "可以探索、编辑和讲述的空中岛屿", "colors": ["#112844", "#9ccbd8", "#f6b877"], "types": ["tower", "tree", "crystal", "orb", "arch", "portal"], "names": ["观测灯塔", "愿望之树", "时间晶体", "引力核心", "星环入口", "远航之门"], "stories": ["灯塔为每次探索记录新的坐标。", "每片叶子都写着一个尚未实现的愿望。", "晶体封存着这座岛屿的第一秒。", "核心轻轻牵引漂浮的石块，让岛屿保持平衡。", "星环连接现在与下一段旅途。", "门后没有预设答案，只有你决定的方向。"], "chapter": "让每个物件成为故事的入口。"}


def _call_local_model(prompt: str) -> tuple[dict[str, Any] | None, str | None]:
    base = os.getenv("NEMOTRON_BASE_URL", "").rstrip("/")
    model = os.getenv("NEMOTRON_MODEL", "")
    if not base or not model:
        return None, "未配置 NVIDIA Nemotron 服务"
    if "nemotron" not in model.lower():
        return None, "核心模型必须为 NVIDIA Nemotron"
    instruction = (
        "你是互动3D场景策展人。根据用户主题返回一个JSON对象，不要代码块。字段："
        "title(不超过12字), subtitle(不超过28字), chapter(不超过50字), "
        "colors(3个#RRGGBB色值), objects(恰好6个对象，每个含name、type、story；"
        "type仅可为tree,crystal,tower,orb,arch,book,portal；name不超过12字，story不超过38字)。"
        "物件应有可点击的叙事意义，内容适合全年龄用户。"
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 850,
    }).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            payload = json.load(response)
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        match = re.search(r"\{.*\}", content, flags=re.S)
        if not match:
            raise ValueError("模型未返回 JSON 对象")
        return json.loads(match.group(0)), None
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, f"Nemotron 调用失败：{type(exc).__name__}"


def _clean_text(value: Any, limit: int, default: str) -> str:
    if not isinstance(value, str):
        return default
    cleaned = " ".join(value.strip().split())
    return cleaned[:limit] or default


def intake(prompt: str) -> dict[str, Any]:
    prompt = _clean_text(prompt, 300, "会回应访客的漂浮岛屿")
    return {"prompt": prompt, "source_type": "user_text", "status": "provided", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def plan(brief: dict[str, Any], allow_model: bool = True) -> dict[str, Any]:
    seed = _theme(brief["prompt"])
    candidate, error = _call_local_model(brief["prompt"]) if allow_model else (None, "选择了模板模式")
    source = "nvidia_nemotron" if candidate else "template"
    value = candidate if isinstance(candidate, dict) else {}
    colors = value.get("colors")
    if not isinstance(colors, list) or len(colors) < 3 or not all(isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c) for c in colors[:3]):
        colors = seed["colors"]
    raw_objects = value.get("objects", [])
    if not isinstance(raw_objects, list) or len(raw_objects) < 6:
        raw_objects = []
    objects = []
    for i in range(6):
        raw = raw_objects[i] if i < len(raw_objects) and isinstance(raw_objects[i], dict) else {}
        kind = raw.get("type") if raw.get("type") in ALLOWED else seed["types"][i]
        objects.append({"id": f"artifact-{i+1}", "name": _clean_text(raw.get("name"), 12, seed["names"][i]), "type": kind, "story": _clean_text(raw.get("story"), 38, seed["stories"][i])})
    return {"theme": seed["key"], "title": _clean_text(value.get("title"), 12, seed["title"]), "subtitle": _clean_text(value.get("subtitle"), 28, seed["subtitle"]), "chapter": _clean_text(value.get("chapter"), 50, seed["chapter"]), "colors": colors[:3], "objects": objects, "provenance": {"mode": source, "model": os.getenv("NEMOTRON_MODEL") if source == "nvidia_nemotron" else None, "fallback_reason": error}}


def compose(plan_result: dict[str, Any]) -> dict[str, Any]:
    locations = [[-3.0, -1.5], [-1.3, 1.4], [1.0, -1.7], [3.0, 0.5], [-0.3, 3.1], [2.3, 3.0]]
    return {"coordinate_system": "meters_y_up", "ground_radius_m": 6.2, "objects": [{**obj, "position": [locations[i][0], 0, locations[i][1]], "scale": 0.85 + (i % 3) * 0.17} for i, obj in enumerate(plan_result["objects"])]}


def interactions(scene: dict[str, Any]) -> dict[str, Any]:
    return {"initial_state": "dormant", "states": ["dormant", "awakened"], "events": [{"target": obj["id"], "trigger": "click", "effect": "awaken_and_reveal", "reversible": True} for obj in scene["objects"]]}


def narrate(plan_result: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    return {"opening": plan_result["chapter"], "beats": [{"target": obj["id"], "title": obj["name"], "text": obj["story"]} for obj in scene["objects"]], "ending": "六个节点都被唤醒。你已经写下这个世界的第一章。"}


def verify(scene: dict[str, Any], interaction_result: dict[str, Any], story: dict[str, Any]) -> dict[str, Any]:
    ids = [o["id"] for o in scene["objects"]]
    problems = []
    if len(ids) != 6 or len(set(ids)) != 6:
        problems.append("object_ids_invalid")
    if {e["target"] for e in interaction_result["events"]} != set(ids):
        problems.append("interaction_targets_invalid")
    if {b["target"] for b in story["beats"]} != set(ids):
        problems.append("story_targets_invalid")
    if any(abs(o["position"][0]) > 5 or abs(o["position"][2]) > 5 for o in scene["objects"]):
        problems.append("object_out_of_bounds")
    return {"status": "PASS" if not problems else "FAIL", "checks": 4, "problems": problems, "scope": "schema_and_interaction_contract_only"}


def build(prompt: str, allow_model: bool = True) -> dict[str, Any]:
    brief = intake(prompt)
    plan_result = plan(brief, allow_model)
    scene = compose(plan_result)
    interaction_result = interactions(scene)
    story = narrate(plan_result, scene)
    evaluation = verify(scene, interaction_result, story)
    if evaluation["status"] != "PASS":
        raise ValueError(f"Scene contract failed: {evaluation['problems']}")
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + _sha(os.urandom(12))[:6]
    folder = RUNS / run_id
    artifacts = {}
    for name, value in [("intake", brief), ("plan", plan_result), ("scene", scene), ("interactions", interaction_result), ("story", story), ("evaluation", evaluation)]:
        artifacts[f"{name}.json"] = _write(folder / f"{name}.json", value)
    manifest = {"run_id": run_id, "status": "COMPLETE", "mode": plan_result["provenance"]["mode"], "artifacts_sha256": artifacts, "pipeline": ["intake", "plan", "compose", "interact", "narrate", "verify"]}
    _write(folder / "manifest.json", manifest)
    return {"run_id": run_id, "brief": brief, "plan": plan_result, "scene": scene, "interactions": interaction_result, "story": story, "evaluation": evaluation, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="?", default="会回应访客的漂浮岛屿")
    parser.add_argument("--template", action="store_true", help="Do not call a local model")
    args = parser.parse_args()
    print(json.dumps(build(args.prompt, allow_model=not args.template), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
