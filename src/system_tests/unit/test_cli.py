"""
Simple tests ensuring CLI interface can be called, with underlying functionality mocked.
"""

import datetime
import re
from cuga.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_health_check(monkeypatch):
    from cuga.backend.memory import Memory

    monkeypatch.setattr(Memory, "health_check", lambda self: False)

    result = runner.invoke(app, ["memory", "namespace", "create", "foobar", "--user-id", "baz"])
    assert result.exit_code == 1
    assert result.output == "Memory service is not running.\n"


def test_create_namespace(monkeypatch):
    from cuga.backend.memory import Memory, Namespace

    def create_namespace(self, namespace_id, user_id, agent_id, app_id):
        return Namespace(id="foobar", created_at=datetime.datetime.now(datetime.UTC), user_id="baz")

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "create_namespace", create_namespace)

    result = runner.invoke(app, ["memory", "namespace", "create", "foobar", "--user-id", "baz"])
    assert result.exit_code == 0
    assert result.output == "Created namespace `foobar`\n"


def test_create_namespace_already_exists(monkeypatch):
    from cuga.backend.memory import Memory, APIRequestException

    def create_namespace(self, namespace_id, user_id, agent_id, app_id):
        raise APIRequestException('409')

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "create_namespace", create_namespace)

    result = runner.invoke(app, ["memory", "namespace", "create", "foobar", "--user-id", "baz"])
    assert result.exit_code == 1
    assert result.output == "Namespace `foobar` already exists.\n"


def test_get_namespace_details(monkeypatch):
    from cuga.backend.memory import Memory, Namespace

    created_at = datetime.datetime.now(datetime.UTC)

    def get_namespace_details(self, namespace_id):
        return Namespace(id="foobar", created_at=created_at, user_id="baz")

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "get_namespace_details", get_namespace_details)

    result = runner.invoke(app, ["memory", "namespace", "details", "foobar"])
    assert result.exit_code == 0
    header = re.compile(r"┃ ID\s+┃ Created At\s+┃ User ID\s+┃ Agent ID\s+┃ Application ID\s+┃ Entities\s+┃")
    assert header.search(result.output) is not None
    assert "foobar" in result.output
    assert "baz" in result.output
    assert created_at.isoformat()[:10] in result.output


def test_get_namespace_details_not_found(monkeypatch):
    from cuga.backend.memory import Memory, NamespaceNotFoundException

    def get_namespace_details(self, namespace_id):
        raise NamespaceNotFoundException()

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "get_namespace_details", get_namespace_details)

    result = runner.invoke(app, ["memory", "namespace", "details", "foobar"])
    assert result.exit_code == 1
    assert result.output == "Namespace `foobar` not found.\n"


def test_search_namespaces(monkeypatch):
    from cuga.backend.memory import Memory, Namespace

    created_at = datetime.datetime.now(datetime.UTC)

    def search_namespaces(self, user_id, agent_id, app_id, limit):
        return [Namespace(id="foobar", created_at=created_at, user_id="baz")]

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "search_namespaces", search_namespaces)

    result = runner.invoke(app, ["memory", "namespace", "search"])
    assert result.exit_code == 0
    header = re.compile(r"┃ ID\s+┃ Created At\s+┃ User ID\s+┃ Agent ID\s+┃ Application ID\s+┃")
    assert header.search(result.output) is not None
    assert "foobar" in result.output
    assert "baz" in result.output
    assert created_at.isoformat()[:10] in result.output


def test_delete_namespace(monkeypatch):
    from cuga.backend.memory import Memory

    def delete_namespace(self, namespace_id):
        pass

    monkeypatch.setattr(Memory, "health_check", lambda self: True)
    monkeypatch.setattr(Memory, "delete_namespace", delete_namespace)

    result = runner.invoke(app, ["memory", "namespace", "delete", "foobar"])
    assert result.exit_code == 0
    assert result.output == "Deleted namespace `foobar`\n"
