"""Small deterministic JSON predicates; no expression evaluation or code imports."""

from copy import deepcopy

from .spec import Predicate, Ref, Value


def resolve_value(value: Ref | Value, context: dict):
    if isinstance(value, Value):
        return deepcopy(value.value)
    cursor = context
    try:
        for segment in value.ref.split("."):
            cursor = (
                cursor[int(segment)]
                if isinstance(cursor, list) and segment.isdigit()
                else cursor[segment]
            )
    except (KeyError, IndexError, TypeError):
        if value.optional:
            return deepcopy(value.default)
        raise ValueError(f"unavailable value reference: {value.ref}") from None
    return deepcopy(cursor)


def resolve_inputs(values: dict, context: dict) -> dict:
    return {key: resolve_value(value, context) for key, value in values.items()}


def predicate(condition: Predicate, context: dict) -> bool:
    left = resolve_value(condition.left, context)
    if condition.op == "truthy":
        return bool(left)
    right = resolve_value(condition.right, context)
    compatible = type(left) is type(right) or (
        type(left) in (int, float) and type(right) in (int, float)
    )
    if condition.op in {"eq", "ne"}:
        equal = compatible and left == right
        return equal if condition.op == "eq" else not equal
    if condition.op == "contains":
        if isinstance(left, str) and isinstance(right, str):
            return right in left
        if isinstance(left, dict) and isinstance(right, str):
            return right in left
        if isinstance(left, list):
            return any(type(item) is type(right) and item == right for item in left)
        raise ValueError("contains expects text, a list or an object")
    if not compatible or isinstance(left, (bool, dict, list)) or left is None:
        raise ValueError("ordered comparisons require compatible strings or numbers")
    return {
        "lt": lambda: left < right,
        "le": lambda: left <= right,
        "gt": lambda: left > right,
        "ge": lambda: left >= right,
    }[condition.op]()
