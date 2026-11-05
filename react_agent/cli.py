"""命令行参数、会话切换与交互入口。"""
import argparse
import json
import uuid

from .runtime import Agent
from .models import ChatModel
from .demo import demo_model
from .session import SessionStore


def main():
    parser = argparse.ArgumentParser(description="Minimal Python ReAct Agent")
    parser.add_argument("--user", default="A")
    parser.add_argument("--session", default=None)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()
    try:
        model = demo_model if args.demo else ChatModel()
        agent = Agent(model, max_steps=args.max_steps)
    except ValueError as error:
        parser.error(str(error))
    session_id = args.session or str(uuid.uuid4())
    store = SessionStore(args.data_dir)
    print(f"{'规则演示' if args.demo else '真实模型'} | user={args.user} | session={session_id}")
    print("/exit 退出；/trace 最近日志；/session ID 切换会话")
    while True:
        try:
            text = input("你 > ").strip()
            if text == "/exit":
                break
            if text.startswith("/session "):
                session_id = text.split(maxsplit=1)[1]
                print("当前会话：", session_id)
                continue
            if not text:
                continue
            if text == "/trace":
                result, _ = store.transact(args.user, session_id, lambda state: state["trace"])
                print(json.dumps(result, ensure_ascii=False, indent=2))
                continue
            answer, _ = store.transact(args.user, session_id, lambda state: agent.run(state, text))
            print("Agent >", answer)
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as error:
            print("操作失败（同会话正在执行时请稍后重试）：", error)

