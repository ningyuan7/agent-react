"""解析模型的 action / final 输出协议。"""
import json


def parse_decision(raw):
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith("```json") and raw.endswith("```"):
            raw = raw[7:-3].strip()
        elif raw.startswith("```") and raw.endswith("```"):
            raw = raw[3:-3].strip()
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict) or not isinstance(data.get("thought"), str):
        raise ValueError("Expected thought summary")
    if data.get("type") == "final" and isinstance(data.get("answer"), str) and data["answer"].strip():
        return data
    if data.get("type") == "action" and isinstance(data.get("tool"), str) and isinstance(data.get("arguments"), dict):
        return data
    raise ValueError("Expected action with tool/arguments or final with answer")

