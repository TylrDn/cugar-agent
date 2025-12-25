import pytest

from cuga.agents.executor import ExecutionContext, Executor
from cuga.agents.planner import PlanStep
from cuga.agents.policy import PolicyEnforcer, PolicyViolation
from cuga.agents.registry import ToolRegistry


def _write_policy(tmp_path, name, contents):
    path = tmp_path / f"{name}.yaml"
    path.write_text(contents)
    return path


def test_allows_tool_with_valid_payload(tmp_path):
    policy_contents = """
profile: demo
allow_unknown_tools: false
metadata_schema:
  required: [request_id]
  properties:
    request_id:
      type: string
allowed_tools:
  echo:
    input_schema:
      required: [text]
      properties:
        text:
          type: string
    """
    _write_policy(tmp_path, "demo", policy_contents)

    enforcer = PolicyEnforcer(tmp_path)
    registry = ToolRegistry()

    def echo_handler(payload, *, config, context):
        assert context.metadata["request_id"] == "abc-123"
        return payload["text"]

    registry.register("demo", "echo", echo_handler)
    sandbox = registry.sandbox("demo")

    executor = Executor(policy_enforcer=enforcer)
    plan = [PlanStep(name="echo-step", tool="echo", input={"text": "hello"})]
    context = ExecutionContext(profile="demo", metadata={"request_id": "abc-123"})

    result = executor.execute_plan(plan, sandbox, context)
    assert result.output == "hello"


def test_rejects_disallowed_tool(tmp_path):
    policy_contents = """
profile: locked
allow_unknown_tools: false
allowed_tools: {}
    """
    _write_policy(tmp_path, "locked", policy_contents)

    enforcer = PolicyEnforcer(tmp_path)
    registry = ToolRegistry()
    registry.register("locked", "allowed", lambda *_args, **_kwargs: "ok")
    sandbox = registry.sandbox("locked")
    executor = Executor(policy_enforcer=enforcer)

    plan = [PlanStep(name="blocked", tool="forbidden", input={})]
    context = ExecutionContext(profile="locked", metadata=None)

    with pytest.raises(PolicyViolation) as excinfo:
        executor.execute_plan(plan, sandbox, context)

    assert excinfo.value.code == "tool_not_allowed"


def test_rejects_invalid_input_payload(tmp_path):
    policy_contents = """
profile: strict
allow_unknown_tools: false
allowed_tools:
  validator:
    input_schema:
      required: [value]
      properties:
        value:
          type: integer
      additionalProperties: false
    """
    _write_policy(tmp_path, "strict", policy_contents)

    enforcer = PolicyEnforcer(tmp_path)
    registry = ToolRegistry()
    registry.register("strict", "validator", lambda *_args, **_kwargs: "ok")
    sandbox = registry.sandbox("strict")
    executor = Executor(policy_enforcer=enforcer)

    bad_plan = [PlanStep(name="bad", tool="validator", input={"value": "not-an-int"})]
    context = ExecutionContext(profile="strict", metadata={})

    with pytest.raises(PolicyViolation) as excinfo:
        executor.execute_plan(bad_plan, sandbox, context)

    assert excinfo.value.code == "input_validation_failed"
    assert "not-an-int" in excinfo.value.details["errors"][0]


def test_falls_back_to_default_policy(tmp_path):
    default_policy = """
profile: default
allow_unknown_tools: true
allowed_tools: {}
    """
    _write_policy(tmp_path, "default", default_policy)

    enforcer = PolicyEnforcer(tmp_path)
    step = PlanStep(name="noop", tool="any_tool", input={"anything": "goes"})

    # Should not raise despite missing profile-specific policy
    enforcer.validate_step("missing_profile", step, metadata={"unused": True})
