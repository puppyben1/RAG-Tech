from jinrong.ask import ask


def test_pre_search_refusal_exposes_stable_reason() -> None:
    response = ask(question="请说明月球商业银行的账户密码。")

    assert response.route == "rag_refusal"
    assert response.refusal_reason == "out_of_scope_or_sensitive"
    assert response.answer_text == "无法根据当前资料确定。"
