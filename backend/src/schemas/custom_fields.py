import ast
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CustomFieldDefinition(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,49}$")
    name: str = Field(min_length=1, max_length=100)
    type: Literal["TEXT", "NUMBER", "DROPDOWN", "DATE", "FORMULA", "USERS"]
    options: list[str] = Field(default_factory=list, max_length=100)
    formula: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def valid(self):
        if self.type == "DROPDOWN" and not self.options:
            raise ValueError("Dropdowns require options")
        if self.type == "FORMULA":
            try:
                tree = ast.parse(self.formula or "", mode="eval")
            except SyntaxError as exc:
                raise ValueError("Invalid formula") from exc
            for node in ast.walk(tree):
                if not isinstance(
                    node,
                    (
                        ast.Expression,
                        ast.BinOp,
                        ast.UnaryOp,
                        ast.Name,
                        ast.Load,
                        ast.Constant,
                        ast.Add,
                        ast.Sub,
                        ast.Mult,
                        ast.Div,
                        ast.Mod,
                        ast.UAdd,
                        ast.USub,
                    ),
                ):
                    raise ValueError("Formulas support numeric fields and arithmetic only")
                if isinstance(node, ast.Constant) and (
                    isinstance(node.value, bool)
                    or not isinstance(node.value, (float, int))
                    or abs(node.value) > 1e15
                ):
                    raise ValueError("Formula constants must be bounded numbers")
        return self


class CustomFieldsRequest(BaseModel):
    fields: list[CustomFieldDefinition] = Field(max_length=30)

    @model_validator(mode="after")
    def unique(self):
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Field keys must be unique")
        numeric = {field.key for field in self.fields if field.type == "NUMBER"} | {
            "story_points",
            "estimated_hours",
        }
        for field in self.fields:
            if field.type == "FORMULA" and any(
                node.id not in numeric
                for node in ast.walk(ast.parse(field.formula, mode="eval"))
                if isinstance(node, ast.Name)
            ):
                raise ValueError(
                    "Formulas may reference number fields, story_points, and estimated_hours"
                )
        return self
