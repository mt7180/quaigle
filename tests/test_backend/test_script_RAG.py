from backend.script_RAG import (
    set_up_text_chatbot,
)


def test_set_up_chatbot():
    chat_engine, callback_manager, token_counter = set_up_text_chatbot()
    assert chat_engine is not None
    assert callback_manager is not None
    assert token_counter is not None
