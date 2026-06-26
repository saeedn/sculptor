from sculptor.state.chat_state import AskUserQuestionData


def test_ask_user_question_data_deserializes_without_plan_file_path() -> None:
    legacy_payload = {
        "questions": [
            {
                "question": "Pick one",
                "header": "Header",
                "options": [{"label": "A", "description": "first"}],
                "multi_select": False,
            }
        ],
        "tool_use_id": "toolu_legacy",
    }
    parsed = AskUserQuestionData.model_validate(legacy_payload)
    assert parsed.plan_file_path is None
    assert parsed.tool_use_id == "toolu_legacy"
