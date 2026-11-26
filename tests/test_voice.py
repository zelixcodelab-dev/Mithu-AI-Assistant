from types import SimpleNamespace

from app.voice import (
    ALLOWED_BROWSER_EVENTS,
    LIVE_TOOLS,
    _minimal_voice_result,
    _session_configuration,
)


def settings(enabled=False):
    return SimpleNamespace(
        mithu_live_model="gpt-live-1.1",
        mithu_live_voice="marin",
        mithu_responses_model="gpt-6-luna",
        educonnect_api_enabled=enabled,
    )


def test_browser_event_allowlist_rejects_arbitrary_commands():
    assert "session.input_audio.append" in ALLOWED_BROWSER_EVENTS
    assert "response.create" not in ALLOWED_BROWSER_EVENTS
    assert "session.start" not in ALLOWED_BROWSER_EVENTS


def test_voice_tools_are_disabled_until_gateway_is_enabled():
    config = _session_configuration(settings(enabled=False))
    responses = config["delegation"]["responses"]
    assert responses["tools"] == []
    assert responses["tool_choice"] == "none"


def test_only_read_tools_are_registered_when_gateway_is_enabled():
    config = _session_configuration(settings(enabled=True))
    responses = config["delegation"]["responses"]
    assert responses["tool_choice"] == "auto"
    names = {tool["name"] for tool in responses["tools"]}
    assert names == {"list_colleges", "list_students", "list_leads", "get_student"}


def test_student_voice_result_removes_private_fields():
    result = _minimal_voice_result("get_student", {
        "id": "s1",
        "name": "Student One",
        "course": "BSc Nursing",
        "college": "Example College",
        "status": "enrolled",
        "phone": "9999999999",
        "application": {"aadhaar_number": "1234"},
        "payments": [{"amount": 50000}],
        "fees_plan": {"year_1": 90000},
    })
    assert result == {"items": [{
        "id": "s1",
        "name": "Student One",
        "course": "BSc Nursing",
        "college": "Example College",
        "status": "enrolled",
    }], "truncated": False}


def test_college_voice_result_never_exposes_revenue_fields():
    result = _minimal_voice_result("list_colleges", [{
        "name": "Example College",
        "place": "Bengaluru",
        "courses": ["BSc Nursing"],
        "sc_rates": {"BSc Nursing": 25000},
    }])
    assert result == {"items": [{
        "name": "Example College",
        "place": "Bengaluru",
        "courses": ["BSc Nursing"],
    }], "truncated": False}
