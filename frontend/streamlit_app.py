# run ommand: streamlit run streamlit_app.py 
import pathlib
import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.stylable_container import stylable_container
import requests
import os
from PIL import Image

from utils.helpers import register_page
#from utils.request_wrapper import Client, APIResponse

DEBUG = True
API_URL = (
    "http://localhost:8000/" if DEBUG else "http://quagleapi:8000/"
)

APP_TITLE = "Quaigle"
MAIN_PAGE = {}

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
        unsafe_allow_html=True
    )


def set_page_settings():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🤖",
        layout="wide",
    )
    with open("./static/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>", 
            unsafe_allow_html=True
       )
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
        #if "counter" not in st.session_state:
            #st.session_state.counter = 0
        if "temperature" not in st.session_state:
            st.session_state.temperature = 0
        if "total_tokens" not in st.session_state:
            st.session_state.total_tokens = []

def clear_storage():
    response = requests.get(os.path.join(API_URL,"clear_storage"))
    if response.status_code == 200:
        data = response.json()
        return f"Success: {data['message']}"
    else:
        return st.error(f"Error: {response.status_code} - {response.text}")

def clear_history():
    st.session_state.messages.clear()
    response = requests.get(os.path.join(API_URL,"clear_history"))
    if response.status_code == 200:
        data = response.json()
        return f"Success: {data['message']}"
    else:
        return st.error(f"Error: {response.status_code} - {response.text}")
    

def display_options_menu():
    with st.container():
        selected_page = option_menu(
            menu_title=None,
            options=["QuestionAI","QuizMe","Statistics"],
            icons=["chat-right-text", "clipboard2-check",  "activity"],  # https://icons.getbootstrap.com/
            #menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
            "container": {"padding": "3!important", "background-color": "white", "border":"1px solid black", "position": "sticky", "top": "5rem"},
            }
        )
        st.session_state.selected_page = selected_page.lower()


def uploader_callback():
    if st.session_state['file_uploader'] is not None:
        uploaded_file = st.session_state['file_uploader']
        with st.spinner("Waiting for response"):
            try:
                response = requests.post(os.path.join(API_URL,"upload"), files={"file": uploaded_file})
                # print(response.json())
                if response.status_code == 200:
                    response_data = response.json()
                    #st.session_state.counter += 1
                    # print(response_data["summary"], st.session_state.counter)
                    post_ai_message_to_chat(response_data.get("summary", "Unknown response"))
                else:
                    st.error(f"Error: {response.status_code}")
            except Exception as e:
                print(f"Exception occurred while uploading file to backend: {e.args}")
                st.error(f"Error: {e}")


def display_sidemenu():
    st.sidebar.title('Menu')
    st.sidebar.markdown(
    """
    Please uploade your file or enter a url. Supported file types: 
    """
    )
    col1, col2 = st.sidebar.columns(2)
    col1.markdown(
        """
        - txt  
        - html
        """
    )
    col2.markdown(
        """
        - db 
        - sqlite  
        """
    )
    with st.sidebar.container():
        success_message = st.empty()
        if uploaded_file := st.file_uploader(
            'dragndrop',
            type=["txt","sqlite","db" ],
            on_change=uploader_callback,
            key="file_uploader",
            label_visibility="collapsed"
        ):
            success_message.success(f"File successfully uploaded")
        
        if  url := st.text_input('url',placeholder='OR enter url', label_visibility="collapsed"):
            success_message.success(f"url successfully uploaded")
        add_vertical_space(1)
        
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
                temperature = st.slider('temperature', min_value=0, max_value=1)
                st.session_state.temperature = float(temperature)
                
        if st.button('Clear chat history', use_container_width=True):
            success_message.success(clear_history())
        if st.button('Clear knowledge base: texts/ urls', use_container_width=True):
            success_message.success(clear_storage())

@register_page(MAIN_PAGE)
def questionai():
    with st.container():
        for message in st.session_state.messages:
            #image = "xxx.png" if message["role"] == "user" else "xxx.png"
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        if prompt := st.chat_input("-> Post questions regarding the content of your file, AI will answer..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.spinner("Waiting for response"):
                payload = {"prompt": prompt, "temperature": st.session_state.temperature}
                response = requests.post(os.path.join(API_URL,"qa_text"), json=payload)
                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    ai_answer=""
                    if response.status_code == 200:
                        ai_answer = response.json().get("ai_answer", "Unknown response type")
                        message_placeholder.markdown(ai_answer)
                        st.session_state.messages.append({"role": "assistant", "content": ai_answer})
                    else:
                        st.error(f"Error: {response.status_code}")
                message_placeholder.markdown(ai_answer)
                add_vertical_space(7)
        elif len(st.session_state.messages)==0:
            cfd = pathlib.Path(__file__).parent 
            image = Image.open(cfd / "static" / "main_picture3.png")
            st.image(image, caption=None,)
    

@register_page(MAIN_PAGE)
def quizme():
    with st.container():
        st.text('Quiz')

@register_page(MAIN_PAGE)
def statistics():
    with st.container():
        st.text('Statics')

def post_ai_message_to_chat(message):
    st.session_state.messages.append({"role": "assistant", "content": message})

def main():
    set_page_settings()
    initialize_session()
    display_sidemenu()
    #display_options_menu()
    #st.write('')
    MAIN_PAGE[st.session_state.selected_page]()


if __name__ == "__main__":
    main()