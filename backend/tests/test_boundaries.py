import ast
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable

from ted.domain.models import User
from ted.infrastructure.persistence.records import UserRow

ROOT = Path(__file__).resolve().parents[1] / "src/ted"


def test_domain_and_application_imports_point_inward():
    forbidden = ("fastapi", "sqlalchemy", "ted.infrastructure", "ted.presentation")
    for layer in ["domain", "application"]:
        for file in (ROOT / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text())):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith(forbidden), file
                elif isinstance(node, ast.Import):
                    assert not any(n.name.startswith(forbidden) for n in node.names), file


def test_domain_is_not_an_orm_object():
    with pytest.raises(NoInspectionAvailable):
        inspect(User)
    assert inspect(UserRow).local_table.name == "users"


def test_repositories_have_no_commit_or_rollback():
    for file in (ROOT / "infrastructure/persistence").glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            assert not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"commit", "rollback"}
            ), file


def test_existing_public_paths_and_methods_are_preserved():
    import json

    from fastapi.routing import APIRoute

    from ted.presentation.api import app

    expected = json.loads((Path(__file__).parent / "contracts/http_paths.json").read_text())
    verbs = {"get", "post", "put", "patch", "delete", "head", "options"}
    actual = sorted(
        [
            [method.upper(), path]
            for path, operations in app.openapi()["paths"].items()
            for method in operations
            if method in verbs
        ]
        + [
            [method, route.path]
            for route in app.routes
            if isinstance(route, APIRoute) and not route.include_in_schema
            for method in route.methods
        ]
    )
    assert actual == expected
