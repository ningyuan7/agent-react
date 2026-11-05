"""离线规则演示模型。"""
import json


def demo_model(context):
    """Deterministic demo adapter. Real model mode uses the same runtime."""
    messages = context["messages"]
    start = max(i for i, m in enumerate(messages) if m["role"] == "user" and not m["content"].startswith(("Observation", "协议错误")))
    current = messages[start:]
    text = current[0]["content"]
    called = [json.loads(m["content"])["tool"] for m in current if m["role"] == "assistant"]

    def action(tool, arguments):
        return {"type": "action", "thought": "调用 " + tool + " 获取所需结果", "tool": tool, "arguments": arguments}

    if "天气" in text and "weather" not in called:
        city = next((city for city in ["北京", "上海", "杭州", "深圳"] if city in text), "北京")
        return action("weather", {"city": city})
    if any(word in text for word in ["待办", "记下来"]) and "todo" not in called:
        return action("todo", {"action": "list"} if any(word in text for word in ["查看", "列出"]) else {"action": "add", "text": text})
    if "计算" in text and "calculator" not in called:
        return action("calculator", {"expression": text.split("计算", 1)[1].strip()})
    if "搜索" in text and "search" not in called:
        return action("search", {"query": text})
    observations = [m["content"] for m in current if m["content"].startswith("Observation")]
    answer = "\n".join(observations) or "规则演示支持天气、待办、搜索和计算。自由对话请配置真实模型。"
    if "刚才" in text:
        answer = "本会话之前的输入：" + "\n".join(m["content"] for m in messages[:start] if m["role"] == "user" and not m["content"].startswith(("Observation", "协议错误")))
    return {"type": "final", "thought": "汇总当前结果", "answer": answer}

