"""A bounded Python expression/statement interpreter for JSON transformations.

Programs define run(inputs). The interpreter has no imports, Python object access,
filesystem, network, eval or exec. General Python can use a deployed sandbox tool
with the same {code, data} contract.
"""

import ast
import operator

from evosprig.core.protocols import Tool, ToolFeedbackError
from evosprig.core.spec import canonical_json


class Returned(Exception):
    def __init__(self, value):
        self.value = value


class Program:
    def __init__(self, code, *, steps=10000):
        if not isinstance(code, str) or len(code) > 32000:
            raise ValueError("code must be at most 32000 characters")
        tree = ast.parse(code)
        if len(list(ast.walk(tree))) > 2000:
            raise ValueError("program is too large")
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            raise ValueError("define exactly one function: run(inputs)")
        function = tree.body[0]
        if (
            function.name != "run"
            or function.decorator_list
            or function.returns
            or [a.arg for a in function.args.args] != ["inputs"]
            or function.args.posonlyargs
            or function.args.kwonlyargs
            or function.args.vararg
            or function.args.kwarg
            or function.args.defaults
            or function.args.args[0].annotation
        ):
            raise ValueError("entry point must be run(inputs)")
        self.body, self.steps = function.body, steps

    def tick(self):
        self.steps -= 1
        if self.steps < 0:
            raise ValueError("program instruction budget exceeded")

    @staticmethod
    def bounded(value):
        # Values cross a JSON boundary on every operation; no object capabilities.
        if type(value) is int and value.bit_length() > 1024:
            raise ValueError("integer exceeds program limit")
        if len(canonical_json(value)) > 65536:
            raise ValueError("value exceeds program limit")
        return value

    def expr(self, node, env):
        self.tick()
        return self.bounded(self.evaluate(node, env))

    def evaluate(self, node, env):
        if isinstance(node, ast.Constant):
            if type(node.value) not in {str, int, float, bool, type(None)}:
                raise ValueError("only JSON constants are supported")
            return node.value
        if isinstance(node, ast.Name):
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.expr(v, env) for v in node.elts]
        if isinstance(node, ast.Dict):
            values = {self.expr(k, env): self.expr(v, env) for k, v in zip(node.keys, node.values)}
            if any(type(k) is not str for k in values):
                raise ValueError("dictionary keys must be strings")
            return values
        if isinstance(node, ast.Subscript):
            value = self.expr(node.value, env)
            if isinstance(node.slice, ast.Slice):
                sl = node.slice
                return value[
                    slice(
                        *(self.expr(v, env) if v else None for v in (sl.lower, sl.upper, sl.step))
                    )
                ]
            return value[self.expr(node.slice, env)]
        if isinstance(node, ast.BinOp):
            left, right = self.expr(node.left, env), self.expr(node.right, env)
            operations = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.FloorDiv: operator.floordiv,
                ast.Mod: operator.mod,
            }
            if type(node.op) not in operations:
                raise ValueError("unsupported arithmetic operation")
            if isinstance(node.op, ast.Mod) and isinstance(left, str):
                raise ValueError("string formatting is unavailable")
            if isinstance(node.op, ast.Mult):
                for sequence, count in ((left, right), (right, left)):
                    if isinstance(sequence, (str, list)) and isinstance(count, int):
                        if len(canonical_json(sequence)) * max(count, 0) > 65536:
                            raise ValueError("sequence multiplication exceeds program limit")
            return operations[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            operation = {
                ast.Not: operator.not_,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }.get(type(node.op))
            if operation is None:
                raise ValueError("unsupported unary operation")
            return operation(self.expr(node.operand, env))
        if isinstance(node, ast.BoolOp):
            result = None
            for value in node.values:
                result = self.expr(value, env)
                if (isinstance(node.op, ast.And) and not result) or (
                    isinstance(node.op, ast.Or) and result
                ):
                    break
            return result
        if isinstance(node, ast.Compare):
            left = self.expr(node.left, env)
            operations = {
                ast.Eq: operator.eq,
                ast.NotEq: operator.ne,
                ast.Lt: operator.lt,
                ast.LtE: operator.le,
                ast.Gt: operator.gt,
                ast.GtE: operator.ge,
                ast.In: lambda a, b: a in b,
                ast.NotIn: lambda a, b: a not in b,
                ast.Is: operator.is_,
                ast.IsNot: operator.is_not,
            }
            for op, comparator in zip(node.ops, node.comparators):
                right = self.expr(comparator, env)
                if not operations[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self.expr(node.body if self.expr(node.test, env) else node.orelse, env)
        if isinstance(node, ast.ListComp):
            if len(node.generators) != 1:
                raise ValueError("use one comprehension generator")
            gen = node.generators[0]
            if gen.is_async or not isinstance(gen.target, ast.Name):
                raise ValueError("comprehensions need a plain variable")
            result = []
            for item in self.expr(gen.iter, env):
                scope = {**env, gen.target.id: item}
                self.tick()
                if all(self.expr(test, scope) for test in gen.ifs):
                    result.append(self.expr(node.elt, scope))
                    self.bounded(result)
            return result
        if isinstance(node, ast.Call):
            if node.keywords:
                raise ValueError("use positional arguments")
            args = [self.expr(v, env) for v in node.args]
            if isinstance(node.func, ast.Name):
                functions = {
                    "len": len,
                    "sum": sum,
                    "min": min,
                    "max": max,
                    "abs": abs,
                    "round": round,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "sorted": sorted,
                    "list": list,
                    "all": all,
                    "any": any,
                }
                if node.func.id == "range":
                    values = range(*args)
                    if len(values) > 1000:
                        raise ValueError("range exceeds 1000 items")
                    return list(values)
                if node.func.id not in functions:
                    raise ValueError("unavailable function")
                return functions[node.func.id](*args)
            if isinstance(node.func, ast.Attribute):
                value = self.expr(node.func.value, env)
                allowed = {
                    str: {
                        "lower",
                        "upper",
                        "strip",
                        "split",
                        "replace",
                        "startswith",
                        "endswith",
                        "join",
                    },
                    dict: {"get", "keys", "values", "items"},
                    list: {"count", "index"},
                }
                if node.func.attr not in allowed.get(type(value), set()):
                    raise ValueError("unavailable method")
                # Bound replacements/joins before allocating their results.
                if (
                    node.func.attr in {"replace", "join"}
                    and len(canonical_json([value, args])) > 8000
                ):
                    raise ValueError("string operation input exceeds limit")
                if (
                    node.func.attr == "replace"
                    and len(args) >= 2
                    and len(value) * (len(args[1]) + 1) > 65536
                ):
                    raise ValueError("replacement exceeds limit")
                if node.func.attr == "join" and len(args) == 1:
                    if not isinstance(args[0], (list, str)) or any(
                        not isinstance(v, str) for v in args[0]
                    ):
                        raise ValueError("join requires a sequence of strings")
                    if sum(len(v) for v in args[0]) + len(value) * max(0, len(args[0]) - 1) > 65536:
                        raise ValueError("joined value exceeds limit")
                result = getattr(value, node.func.attr)(*args)
                return list(result) if node.func.attr in {"keys", "values", "items"} else result
        raise ValueError(f"unsupported expression: {type(node).__name__}")

    def block(self, statements, env):
        for node in statements:
            self.tick()
            if isinstance(node, ast.Return):
                raise Returned(self.expr(node.value, env) if node.value else None)
            if isinstance(node, ast.Assign):
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    raise ValueError("assign to a plain variable")
                env[node.targets[0].id] = self.expr(node.value, env)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expr(node.test, env) else node.orelse, env)
            elif isinstance(node, ast.For):
                if not isinstance(node.target, ast.Name) or node.orelse:
                    raise ValueError("for loops need a plain variable and no else block")
                for item in self.expr(node.iter, env):
                    self.tick()
                    env[node.target.id] = item
                    self.block(node.body, env)
            elif isinstance(node, ast.While):
                if node.orelse:
                    raise ValueError("while-else is unavailable")
                while self.expr(node.test, env):
                    self.block(node.body, env)
            elif isinstance(node, ast.Expr):
                self.expr(node.value, env)
            elif not isinstance(node, ast.Pass):
                raise ValueError(f"unsupported statement: {type(node).__name__}")

    def run(self, inputs):
        try:
            self.block(self.body, {"inputs": self.bounded(inputs)})
        except Returned as returned:
            return self.bounded(returned.value)
        raise ValueError("run(inputs) must return a JSON value")


def execute(code, data):
    try:
        return Program(code).run(data)
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        SyntaxError,
        ArithmeticError,
        RecursionError,
    ) as exc:
        raise ToolFeedbackError("code_error", str(exc)) from None


def python_tool():
    return Tool(
        "code.python",
        "Run a bounded Python transformation over JSON data.",
        {
            "type": "object",
            "properties": {
                "code": {"type": "string", "maxLength": 32000},
                "data": {"type": "object"},
            },
            "required": ["code", "data"],
            "additionalProperties": False,
        },
        {},
        execute,
    )
