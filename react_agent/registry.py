"""工具注册与参数 Schema 校验。"""


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, name, description, properties, required, function):
        if name in self.tools:
            raise ValueError("Duplicate tool")
        self.tools[name] = ({"name": name, "description": description,
                            "parameters": {"type": "object", "properties": properties,
                                           "required": required, "additionalProperties": False}}, function)

    def schemas(self):
        return [item[0] for item in self.tools.values()]

    def call(self, name, arguments, session):
        if name not in self.tools:
            raise ValueError("Unknown tool: " + name)
        schema, function = self.tools[name]
        parameters = schema["parameters"]
        if not isinstance(arguments, dict):
            raise ValueError("Arguments must be an object")
        if set(arguments) - set(parameters["properties"]):
            raise ValueError("Unexpected parameter")
        if set(parameters["required"]) - set(arguments):
            raise ValueError("Missing required parameter")
        for key, value in arguments.items():
            spec = parameters["properties"][key]
            if spec.get("type") == "string" and (not isinstance(value, str) or not value.strip() or not spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", float("inf"))):
                raise ValueError(key + " must satisfy the string Schema")
            if spec.get("type") == "integer" and (type(value) is not int or value < spec.get("minimum", float("-inf"))):
                raise ValueError(key + " must satisfy the integer Schema")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError("Invalid " + key)
        return function(arguments, session)

