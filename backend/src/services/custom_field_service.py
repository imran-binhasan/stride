import ast
import math
import operator
from datetime import date

from src.core.exceptions import ValidationException
from src.models.auth import MemberStatus
from src.repositories.user_repo import UserRepository

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


def evaluate_formula(expression, values):
    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return float(values.get(node.id) or 0)
        if isinstance(node, ast.UnaryOp):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            result = OPS[type(node.op)](visit(node.left), visit(node.right))
            if not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError("Formula result out of range")
            return result
        raise ValueError("Invalid formula expression")

    try:
        return round(visit(ast.parse(expression, mode="eval").body), 6)
    except (ValueError, ZeroDivisionError, TypeError, OverflowError, SyntaxError):
        return None


def computed_values(task, definitions):
    values = {
        **task.custom_fields,
        "story_points": task.story_points,
        "estimated_hours": task.estimated_hours,
    }
    return {
        **task.custom_fields,
        **{
            d["key"]: evaluate_formula(d["formula"], values)
            for d in definitions
            if d["type"] == "FORMULA"
        },
    }


async def validate_values(db, org_id, values, definitions):
    for definition in definitions:
        key = definition["key"]
        if key not in values:
            continue
        value = values[key]
        if definition["type"] == "FORMULA":
            raise ValidationException("Formula columns are read-only")
        if value is None:
            continue
        kind = definition["type"]
        valid = True
        if kind == "TEXT":
            valid = isinstance(value, str) and len(value) <= 10000
        elif kind == "NUMBER":
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (float, int))
                and math.isfinite(value)
                and abs(value) <= 1e15
            )
        elif kind == "DROPDOWN":
            valid = value in definition["options"]
        elif kind == "DATE":
            try:
                date.fromisoformat(value)
            except (ValueError, TypeError):
                valid = False
        elif kind == "USERS":
            valid = (
                isinstance(value, list)
                and len(value) <= 50
                and all(isinstance(v, str) for v in value)
            )
            if valid:
                for user_id in value:
                    member = await UserRepository(db).get_org_membership(org_id, user_id)
                    if not member or member.status != MemberStatus.ACTIVE:
                        valid = False
        if not valid:
            raise ValidationException(f"Invalid value for {definition['name']}")
