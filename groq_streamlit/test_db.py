"""Tests for db.py.

Each test uses a temporary database file, so your real chat.db is
never touched.
"""
import pytest

import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point db.py to a throwaway database, and create its tables.

    - tmp_path: a temporary folder that pytest creates and deletes for us.
    - monkeypatch: replaces db.DB_PATH during this test only.
    """
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_chat.db")
    db.init_db()


def test_create_and_list_conversations(temp_db):
    """A new conversation appears in the list, newest first."""
    first_id = db.create_conversation("First chat")
    second_id = db.create_conversation("Second chat")

    conversations = db.list_conversations()

    assert [c["id"] for c in conversations] == [second_id, first_id]
    assert conversations[0]["title"] == "Second chat"


def test_messages_are_returned_in_order(temp_db):
    """Messages come back in the order they were saved."""
    conv_id = db.create_conversation()
    db.add_message(conv_id, "user", "Hello")
    db.add_message(conv_id, "assistant", "Hi, how can I help?")

    messages = db.get_messages(conv_id)

    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi, how can I help?"},
    ]


def test_messages_stay_in_their_own_conversation(temp_db):
    """Messages of one chat never leak into another chat."""
    chat_a = db.create_conversation("A")
    chat_b = db.create_conversation("B")
    db.add_message(chat_a, "user", "message for A")

    assert db.get_messages(chat_b) == []


def test_rename_conversation(temp_db):
    """Renaming changes the title."""
    conv_id = db.create_conversation("Old title")
    db.rename_conversation(conv_id, "New title")

    assert db.list_conversations()[0]["title"] == "New title"


def test_delete_conversation_removes_its_messages(temp_db):
    """Deleting a chat also deletes its messages."""
    conv_id = db.create_conversation()
    db.add_message(conv_id, "user", "to be deleted")

    db.delete_conversation(conv_id)

    assert db.list_conversations() == []
    assert db.get_messages(conv_id) == []