import streamlit as st
from typing import Generator
from groq import Groq

import db  # our SQLite helper (db.py, same folder as this file)

st.set_page_config(page_icon="🎀", layout="wide",
                   page_title="Groq Goes mewwwwww...")

# Create the database tables if they don't exist yet.
# Safe to run on every rerun (it uses CREATE TABLE IF NOT EXISTS).
db.init_db()


def icon(emoji: str):
    """Shows an emoji as a Notion-style page icon."""
    st.write(
        f'<span style="font-size: 78px; line-height: 1">{emoji}</span>',
        unsafe_allow_html=True,
    )


def generate_chat_responses(chat_completion) -> Generator[str, None, None]:
    """Yield chat response content from the Groq API response."""
    for chunk in chat_completion:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def start_new_chat():
    """Callback of the 'New chat' button: empty screen, no conversation yet.

    The conversation row is only created in the database when you send
    the first message (see the chat_input block below).
    """
    st.session_state.messages = []
    st.session_state.conversation_id = None


def open_conversation(conversation_id: int):
    """Callback of a conversation button: load its messages from the database."""
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = db.get_messages(conversation_id)


def delete_chat(conversation_id: int):
    """Delete a conversation and all its messages from the database."""
    db.delete_conversation(conversation_id)
    # If the deleted conversation is the one on screen, clear the screen too
    if st.session_state.conversation_id == conversation_id:
        start_new_chat()


def ask_rename(conversation_id: int, title: str):
    """Callback of the '✏️ Rename' button: remember that we must open the rename dialog."""
    st.session_state.pending_action = ("rename", conversation_id, title)


def ask_delete(conversation_id: int):
    """Callback of the '🗑️ Delete' button: remember that we must open the delete dialog."""
    st.session_state.pending_action = ("delete", conversation_id, None)


# @st.dialog turns a function into a pop-up window shown in the middle of the page
@st.dialog("Rename conversation")
def rename_dialog(conversation_id: int, current_title: str):
    """Pop-up with a text box to change the title of a conversation."""
    new_title = st.text_input("New title", value=current_title)
    if st.button("Save"):
        if new_title.strip():  # ignore empty titles
            db.rename_conversation(conversation_id, new_title.strip())
        st.rerun()  # closes the pop-up and refreshes the page


@st.dialog("Delete conversation")
def delete_dialog(conversation_id: int):
    """Pop-up asking for confirmation before deleting a conversation."""
    st.write("Delete this conversation and all its messages? "
             "This cannot be undone.")
    col_yes, col_no = st.columns(2)
    if col_yes.button("🗑️ Delete", type="primary", use_container_width=True):
        delete_chat(conversation_id)
        st.rerun()
    if col_no.button("Cancel", use_container_width=True):
        st.rerun()  # just closes the pop-up


icon("🐼")

st.subheader("Groq Chat Streamlit App", divider="rainbow", anchor=False)

client = Groq(
    api_key=st.secrets["GROQ_API_KEY"],
)

# Initialize the values kept between reruns
if "messages" not in st.session_state:
    st.session_state.messages = []

# id of the open conversation in the database.
# None means "no conversation yet": it is created at the first message.
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Action waiting to be shown as a pop-up: None, or
# ("rename", id, title) / ("delete", id, None)
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# Define model details
models = {
    "openai/gpt-oss-120b": {
        "name": "GPT-OSS 120B", "max_tokens": 65536, "developer": "OpenAI"},
    "openai/gpt-oss-20b": {
        "name": "GPT-OSS 20B", "max_tokens": 65536, "developer": "OpenAI"},
    "qwen/qwen3.8-27b": {  # preview model: may be removed at short notice
        "name": "Qwen 3.8 27B (preview)", "max_tokens": 16384, "developer": "Alibaba"},
}

# Layout for model selection and max_tokens slider
col1, col2 = st.columns(2)

with col1:
    model_option = st.selectbox(
        "Choose a model:",
        options=list(models.keys()),
        format_func=lambda x: models[x]["name"],
        index=0,  # 0 = first model in the dictionary (GPT-OSS 120B)
    )

max_tokens_range = models[model_option]["max_tokens"]

with col2:
    # Adjust max_tokens slider dynamically based on the selected model
    max_tokens = st.slider(
        "Max Tokens:",
        min_value=512,
        max_value=max_tokens_range,
        value=min(32768, max_tokens_range),
        step=512,
        help=f"Maximum number of tokens for the model's response. Max for selected model: {max_tokens_range}"
    )

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    avatar = '🤖' if message["role"] == "assistant" else '👩‍💻'
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

if prompt := st.chat_input("Enter your prompt here..."):
    # First message of a new chat: create the conversation in the database.
    # The title is the first 40 characters of the question.
    if st.session_state.conversation_id is None:
        st.session_state.conversation_id = db.create_conversation(
            title=prompt[:40]
        )
    conv_id = st.session_state.conversation_id

    # Save the user's message (in memory for display, in the database for good)
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message(conv_id, "user", prompt)

    with st.chat_message("user", avatar='👩‍💻'):
        st.markdown(prompt)

    # Fetch response from Groq API
    try:
        chat_completion = client.chat.completions.create(
            model=model_option,
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            max_tokens=max_tokens,
            stream=True,
        )

        with st.chat_message("assistant", avatar="🤖"):
            # write_stream shows the text live and returns the full answer
            full_response = st.write_stream(
                generate_chat_responses(chat_completion)
            )

        # Only reached if the API call worked: save the assistant's answer
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )
        db.add_message(conv_id, "assistant", full_response)

    except Exception as e:
        # Show the error in the app instead of crashing
        st.error(e, icon="🚨")

# ---------- Sidebar: list of saved conversations ----------
# This block is at the END of the script on purpose: when you send the
# first message, the new conversation is created above, so it is already
# in the database when we build the list here.
with st.sidebar:
    st.header("Conversations")

    # on_click=... runs start_new_chat() when the button is pressed
    st.button("➕ New chat", on_click=start_new_chat)
    st.divider()

    for conv in db.list_conversations():  # newest first
        conv_id_row = conv["id"]
        # Is this the conversation currently open on screen?
        is_current = conv_id_row == st.session_state.conversation_id

        # Two columns per row: the title (wide) and the ⋮ menu (narrow)
        col_title, col_menu = st.columns([5, 1])

        with col_title:
            st.button(
                conv["title"],
                key=f"conv_{conv_id_row}",   # each widget needs a unique key
                on_click=open_conversation,
                args=(conv_id_row,),         # value passed to open_conversation
                # the open conversation is highlighted, the others are plain
                type="primary" if is_current else "secondary",
                use_container_width=True,
            )

        with col_menu:
            # Small menu with only two buttons
            with st.popover("⋮", use_container_width=True):
                st.button(
                    "✏️ Rename",
                    key=f"rename_{conv_id_row}",
                    on_click=ask_rename,
                    args=(conv_id_row, conv["title"]),
                    use_container_width=True,
                )
                st.button(
                    "🗑️ Delete",
                    key=f"del_{conv_id_row}",
                    on_click=ask_delete,
                    args=(conv_id_row,),
                    use_container_width=True,
                )

# ---------- Pop-ups (rename / delete) ----------
# If a button asked for a pop-up, clear the request first (so the pop-up
# doesn't reopen by itself later), then open it.
if st.session_state.pending_action:
    kind, target_id, target_title = st.session_state.pending_action
    st.session_state.pending_action = None
    if kind == "rename":
        rename_dialog(target_id, target_title)
    else:
        delete_dialog(target_id)