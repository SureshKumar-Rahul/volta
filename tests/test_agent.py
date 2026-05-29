import json
import types

from agent import run_agent


def _msg(content=None, tool_calls=None):
    m = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=m)])


def _tool_call(call_id, name, args):
    fn = types.SimpleNamespace(name=name, arguments=json.dumps(args))
    return types.SimpleNamespace(id=call_id, type="function", function=fn)


class FakeClient:
    """Returns scripted responses in order from .chat.completions.create."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._scripted.pop(0)


def test_trade_commits_last_optimizer_schedule():
    fake_schedule = [-1.0] * 12 + [1.0] * 12
    tools = {
        "get_forecast": lambda date_str: {"prices": [10.0] * 24},
        "run_optimizer": lambda prices: {"schedule": fake_schedule, "expected_revenue": 100.0},
    }
    client = FakeClient([
        _msg(tool_calls=[_tool_call("1", "get_forecast", {"date_str": "2025-01-02"})]),
        _msg(tool_calls=[_tool_call("2", "run_optimizer", {"prices": [10.0] * 24})]),
        _msg(content="FINAL: trade - clear spread, executing the optimizer plan."),
    ])
    result = run_agent("2025-01-02", tools, client=client, model="x")
    assert result["action"] == "trade"
    assert result["schedule"] == fake_schedule


def test_hold_commits_zeros():
    tools = {"get_forecast": lambda date_str: {"prices": [30.0] * 24}}
    client = FakeClient([
        _msg(tool_calls=[_tool_call("1", "get_forecast", {"date_str": "2025-01-02"})]),
        _msg(content="FINAL: hold - prices are flat, not worth trading."),
    ])
    result = run_agent("2025-01-02", tools, client=client, model="x")
    assert result["action"] == "hold"
    assert result["schedule"] == [0.0] * 24


def test_trade_without_optimizer_falls_back_to_hold():
    # If the model says trade but never ran the optimizer, there is nothing to
    # commit, so the recorded action must be hold with a zero schedule.
    tools = {"get_forecast": lambda date_str: {"prices": [30.0] * 24}}
    client = FakeClient([
        _msg(content="FINAL: trade - but I never produced a schedule."),
    ])
    result = run_agent("2025-01-02", tools, client=client, model="x")
    assert result["action"] == "hold"
    assert result["schedule"] == [0.0] * 24
