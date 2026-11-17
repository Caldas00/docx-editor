from docx_agent.conversation import format_history


def test_empty_history_is_empty():
    assert format_history([]) == ""


def test_history_lists_edits_questions_and_selections():
    turns = [
        {"instruction": "add writer_test.cpp lines", "selection": {"text": "Hello, World!"},
         "status": "done", "message": "Added three paragraphs.",
         "changes": [{"op": "insert_paragraph", "before": None, "after": "writer_test.cpp"}]},
        {"instruction": "with the same colours as the others", "status": "needs_clarification",
         "question": "Which text?", "options": ["writer_test.cpp", "> ls"]},
        {"instruction": "remove it", "status": "done", "message": "Removed.", "undone": True,
         "changes": [{"op": "delete_paragraph", "before": "x", "after": None}]},
    ]
    text = format_history(turns)
    assert text.startswith("<conversation>") and text.endswith("</conversation>\n")
    assert '[with this text selected: "Hello, World!"]' in text
    assert 'added paragraph "writer_test.cpp"' in text
    assert 'Assistant asked: Which text? Options: "writer_test.cpp"; "> ls"' in text
    assert "UNDID" in text


def test_history_is_bounded():
    turns = [{"instruction": f"edit {i}", "status": "done", "message": "ok",
              "changes": [{"op": "replace_text", "before": "a" * 500, "after": "b"}] * 20}
             for i in range(30)]
    text = format_history(turns)
    assert "edit 0" not in text and "30. User: edit 29" in text
    assert "and 12 more changes" in text
    assert max(len(line) for line in text.splitlines()) < 400
