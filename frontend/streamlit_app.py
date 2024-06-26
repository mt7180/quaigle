# run command from root: streamlit run streamlit_app.py
import os
import sys
import logging
import pathlib
import random

from streamlit.runtime.uploaded_file_manager import UploadedFile

import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_extras.stylable_container import stylable_container
import requests

from PIL import Image
import certifi
from dotenv import load_dotenv
import sentry_sdk

from utils.helpers import MultiPage


# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
LLM_NAME = "gpt-3.5-turbo"

load_dotenv()
DEBUG_STATUS = int(os.getenv("DEBUG", 1))

if not DEBUG_STATUS:
    logging_level = logging.INFO
    SENTRY_DSN = os.getenv("SENTRY_DSN")
    sentry_sdk.init(SENTRY_DSN)

API_URL = os.getenv("BACKEND_URL", "http://localhost") + ":8000"
logging.info(f"{API_URL=}")

APP_TITLE = "Quaigle"
cfd = pathlib.Path(__file__).parent

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


def stick_navbar():
    st.markdown(
        """
            <div class='fixed-header'/>
            <style>
                div[data-testid="stVerticalBlock"] div:has(div.fixed-header) {
                    position: sticky;
                    top: 2rem;
                    background-color: white;
                    z-index: 999;
                }
            </style>
        """,
        unsafe_allow_html=True,
    )


def set_page_settings():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🤖",
        layout="wide",
    )
    with open(cfd / "static" / "style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def display_header():
    with st.container():
        st.title(APP_TITLE)
        display_options_menu()
        stick_navbar()


def initialize_session(refresh_session=False):
    if refresh_session:
        st.session_state.messages = []
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "score" not in st.session_state:
            st.session_state.score = 0
        if "temperature" not in st.session_state:
            st.session_state.temperature = 0
        if "total_tokens" not in st.session_state:
            st.session_state.total_tokens = []
        if "url" not in st.session_state:
            st.session_state["url"] = ""
        if "question_data" not in st.session_state:
            st.session_state["question_data"] = []
        if "chat_mode" not in st.session_state:
            st.session_state["chat_mode"] = ""
        if "selected_page" not in st.session_state:
            st.session_state["selected_page"] = "questionai"
        if "redirect_page" not in st.session_state:
            st.session_state["redirect_page"] = None
        if "file_uploader_key" not in st.session_state:
            st.session_state["file_uploader_key"] = 0
        if "url_uploader_key" not in st.session_state:
            st.session_state["url_uploader_key"] = 0


def clear_history():
    initialize_session(refresh_session=True)
    response = requests.get(os.path.join(API_URL, "clear_history"))
    st.session_state["redirect_page"] = 0
    if response.status_code == 200:
        data = response.json()
        return f"{data['message']}"
    else:
        return f"Error: {response.status_code} - {response.text}"


def clear_storage():
    st.session_state["url"] = ""
    st.session_state["question_data"] = []
    st.session_state["chat_mode"] = ""
    st.session_state["file_uploader_key"] += 1
    st.session_state["url_uploader_key"] += 1
    st.session_state["redirect_page"] = 0
    st.session_state["selected_page"] = "questionai"
    # st.session_state["url_input"]=""
    clear_history()
    response = requests.get(os.path.join(API_URL, "clear_storage"))
    if response.status_code == 200:
        data = response.json()
        return f"{data['message']}"
    else:
        return f"Error: {response.status_code} - {response.text}"


def set_selected_page(key):
    st.session_state["selected_page"] = st.session_state["option_menu1"].lower()


def display_options_menu():
    translate = {"questionai": 0, "quizme": 1, "statistics": 2}
    with st.container():
        selected_page = option_menu(
            key="option_menu1",
            menu_title=None,
            options=["QuestionAI", "QuizMe", "Statistics"],
            icons=[
                "chat-right-text",
                "clipboard2-check",
                "activity",
            ],  # https://icons.getbootstrap.com/
            on_change=set_selected_page,
            default_index=translate.get(st.session_state["selected_page"], 0),
            # small hack to prevent menu flom flicking to default
            # in combination with chat input:
            manual_select=st.session_state["redirect_page"],
            orientation="horizontal",
            styles={
                "container": {
                    "padding": "3!important",
                    "background-color": "white",
                    "border": "1px solid black",
                    "position": "sticky",
                    "top": "5rem",
                },
            },
        )
        st.session_state.selected_page = selected_page.lower()
        st.session_state["redirect_page"] = None


def make_get_request(route: str) -> requests.Response:
    return requests.get(os.path.join(API_URL, route))


def post_data_to_backend(
    route: str, url: str = "", uploaded_file: UploadedFile | None = None
) -> None:
    with st.spinner("Waiting for openai API response"):
        try:
            if url:
                data = {"upload_url": url}
                response = requests.post(os.path.join(API_URL, route), data=data)
            elif uploaded_file:
                files = {"upload_file": (uploaded_file.name, uploaded_file)}
                data = {"upload_url": ""}
                response = requests.post(
                    os.path.join(API_URL, route), files=files, data=data
                )
            else:
                raise FileNotFoundError

            if response.status_code == 200:
                response_data = response.json()
                logging.info(f"upload response data: {response_data}")
                # st.session_state.counter += 1
                post_ai_message_to_chat(
                    response_data.get("summary", "Unknown response"),
                    response_data.get("text_category"),
                )
                st.session_state.total_tokens.append(
                    response_data.get("used_tokens", 0)
                )
            else:
                st.sidebar.error(f"Error: {response.status_code} - {response}")
        except FileNotFoundError:
            st.sidebar.error(
                "No context is given. Please provide a url or upload a file"
            )
        except requests.RequestException as e:
            st.sidebar.error(f"Server Request Error: is backend {API_URL} up? {e}")


def uploader_callback():
    file_uploader_key = "file_uploader" + str(st.session_state["file_uploader_key"])
    if uploaded_file := st.session_state.get(file_uploader_key):
        post_data_to_backend("upload", None, uploaded_file)


def url_callback():
    text_input_key = "text_input" + str(st.session_state["url_uploader_key"])
    if url := st.session_state.get(text_input_key):
        post_data_to_backend("upload", url, None)


def display_sidemenu():
    st.sidebar.title("Menu")
    sidebar_container = st.sidebar.container()
    success_message = st.sidebar.empty()

    with sidebar_container:
        st.markdown(
            """
        Please uploade your file or enter a url. Supported types: 
        
        - txt - as upload
        - pdf - as upload
        - website - as url
        - sqlite - as upload
            """
        )

        if st.file_uploader(
            "dragndrop",
            type=["txt", "pdf", "sqlite"],
            on_change=uploader_callback,
            key="file_uploader" + str(st.session_state["file_uploader_key"]),
            label_visibility="collapsed",
        ):
            success_message.success("File uploaded")

        if st.text_input(
            "text:",
            placeholder="OR enter url",
            key="text_input" + str(st.session_state["url_uploader_key"]),
            label_visibility="collapsed",
            on_change=url_callback,
        ):
            success_message.success("url uploaded")

        with stylable_container(
            key="red_container",
            css_styles="""
                {
                    background-color: #ffb499;
                    border-radius: 0.5em;
                }
                """,
        ):
            _, c2, _ = st.columns((1, 6, 1))
            with c2:
                temperature = st.slider(
                    "temperature", min_value=0.0, max_value=1.0, step=0.1
                )
                st.session_state.temperature = float(temperature)

        if st.button("Clear chat history", use_container_width=True):
            success_message.success(clear_history())
            # st.rerun()
        if st.button("Clear knowledge base: texts/ urls", use_container_width=True):
            success_message.success(clear_storage())
            st.rerun()


@MultiPage
def questionai():
    with st.container():
        messages = stylable_container(
            key="message_container",
            css_styles=[
                """
                {
                    padding: 0.5em;
                    min-height: 65vh;
                    overflow-y: scroll;
                }
                """,
                """
                .stMarkdown {
                    padding-right: 1.5em;
                }
                """,
            ],
        )

        for message in st.session_state.messages:
            messages.chat_message(message["role"]).write(message["content"])

        if prompt := st.chat_input("-> Your Question ..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            messages.chat_message("user").write(prompt)

            with messages.chat_message("assistant"), st.spinner(
                "Waiting for Response ..."
            ):
                payload = {
                    "prompt": prompt,
                    "temperature": st.session_state.temperature,
                }
                response = requests.post(os.path.join(API_URL, "qa_text"), json=payload)
                ai_answer = ""

                if response.status_code == 200:
                    response_data = response.json()
                    ai_answer = response_data.get("ai_answer", "Unknown response type")
                    st.session_state.total_tokens.append(
                        response_data.get("used_tokens", 0)
                    )
                    st.write(ai_answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": ai_answer}
                    )
                else:
                    st.error(f"Error: {response.status_code} - {response.text}")

        elif len(st.session_state.messages) == 0:
            with messages:
                _, center, _ = st.columns((1, 5, 1))
                image = Image.open(cfd / "static" / "main_picture3.png")
                center.image(
                    image,
                    caption=None,
                    use_column_width=True,
                )


@MultiPage
def quizme():
    if st.session_state["chat_mode"] == "database":
        st.markdown(
            """Sorry, you are in database mode, no quiz available.  
        Please upload a text or give a url to a webpage to generate a quiz."""
        )
    else:
        st.markdown("### A Quiz for You")
        st.session_state.score = 0
        message_placeholder = st.empty()
        if st.button("Generate a Quiz"):
            response = make_get_request("quiz")
            if response.status_code == 200:
                for question in response.json().get("questions"):
                    answer_options = [
                        question["correct_answer"],
                        question["wrong_answer_1"],
                        question["wrong_answer_2"],
                    ]
                    random.shuffle(answer_options)
                    st.session_state["question_data"].append(
                        {
                            "question_txt": question["question"],
                            "correct_answer": question["correct_answer"],
                            "answer_options": answer_options,
                        }
                    )
            else:
                message_placeholder.error(response.json().get("detail"))

        for question in st.session_state["question_data"]:
            st.markdown(f"##### Question: {question['question_txt']}")
            user_answer = st.radio(
                "Select an answer:",
                ["Please Select an answer:", *question["answer_options"]],
                label_visibility="collapsed",
            )

            if user_answer == question["correct_answer"]:
                st.session_state.score += 1

        if st.session_state["score"] > 0:
            message_placeholder.success(
                f"You answered {st.session_state.score} questions correct!"
            )
        if not st.session_state["question_data"]:
            image = Image.open(cfd / "static" / "Hippo.png")
            _, center, _ = st.columns([1, 3, 1])
            center.image(
                image,
                caption=None,
                use_column_width=True,
            )


@MultiPage
def statistics():
    import pandas as pd

    st.markdown("### Used API Tokens per Request of your Current Session")
    st.markdown("(Usage not persisted)")
    _, center, _ = st.columns((1, 5, 1))
    chart_data = pd.DataFrame({"Used API Tokens": st.session_state.total_tokens})
    center.bar_chart(
        data=chart_data,
        color="#D3DCE5",
        y="Used API Tokens",
        use_container_width=False,
    )


def post_ai_message_to_chat(message, document_category):
    document_category_str = document_category.lower()
    if document_category_str == "database":
        st.session_state["chat_mode"] = "database"
        message = f"""
        {message}
        """
    else:
        st.session_state["chat_mode"] = "text"
        document_category_str += " text"
    chat_message = f"""**Upload of your text was successful:**  
    {message}"""
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": chat_message,
        }
    )


def main():
    """set up the streamlit app"""
    set_page_settings()
    initialize_session()
    display_header()
    display_sidemenu()
    # implement the selected page from options menu
    MultiPage.registry[st.session_state.selected_page]()


if __name__ == "__main__":
    main()
