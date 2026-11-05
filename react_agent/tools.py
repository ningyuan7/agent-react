"""工具实现与默认工具集注册。"""
import ast
import math
import operator

from .registry import ToolRegistry


def calculate(expression):
    if len(expression) > 300:
        raise ValueError("Expression too long")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError("Only numbers and + - * / parentheses are supported")

    value = visit(ast.parse(expression, mode="eval").body)
    if not math.isfinite(value):
        raise ValueError("Result is not finite")
    return value



def make_registry():
    registry = ToolRegistry()
    string = {"type": "string", "minLength": 1, "maxLength": 2000}
    registry.register("calculator", "计算四则运算", {"expression": string}, ["expression"],
                      lambda args, session: {"value": calculate(args["expression"])})
    registry.register("search", "搜索示例知识库（mock）", {"query": string}, ["query"],
                      lambda args, session: {"mock": True, "query": args["query"], "results": [
                          "ReAct 交替执行模型决策、工具调用和观察结果，直到给出最终答案。"]})
    registry.register("weather", "城市天气（mock）", {"city": string}, ["city"],
                      lambda args, session: {"mock": True, "city": args["city"], "temperature": 22, "condition": "多云"})

    def todo(args, session):
        action = args["action"]
        if action == "add":
            if not args.get("text"):
                raise ValueError("text required for add")
            session["todos"].append({"id": len(session["todos"]) + 1, "text": args["text"], "done": False})
        if action == "complete":
            item = next((item for item in session["todos"] if item["id"] == args.get("id")), None)
            if item is None:
                raise ValueError("Todo not found")
            item["done"] = True
        return {"todos": session["todos"]}

    registry.register("todo", "管理当前会话待办", {
        "action": {"enum": ["add", "list", "complete"]}, "text": string,
        "id": {"type": "integer", "minimum": 1}}, ["action"], todo)
    return registry

