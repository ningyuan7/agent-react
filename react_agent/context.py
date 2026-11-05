"""历史上下文的基础压缩。"""
import json


def compress(session, budget=12000):
    while len(json.dumps(session["turns"], ensure_ascii=False)) > budget and len(session["turns"]) > 1:
        old = session["turns"].pop(0)
        excerpt = "\n".join(message["role"] + ": " + message["content"][:500] for message in old)
        session["summary"] = (session["summary"] + "\n" + excerpt)[-4000:]

