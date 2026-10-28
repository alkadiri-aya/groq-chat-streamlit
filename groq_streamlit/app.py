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


icon("🐼")

st.subheader("Groq Chat Streamlit App", divider="rainbow", anchor=False)

client = Groq(
    api_key=st.secrets["GROQ_API_KEY"],
)

# Initialize the values kept between reruns
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

# id of the conversation in the database.
# None means "no conversation yet": it is created at the first message.
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

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

# If the user switches model, start a fresh chat.
# The "is not None" check avoids resetting on the very first run.
if st.session_state.selected_model != model_option:
    if st.session_state.selected_model is not None:
        st.session_state.messages = []
        st.session_state.conversation_id = None  # new conversation at next message
    st.session_state.selected_model = model_option

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


def generate_chat_responses(chat_completion) -> Generator[str, None, None]:
    """Yield chat response content from the Groq API response."""
    for chunk in chat_completion:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


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