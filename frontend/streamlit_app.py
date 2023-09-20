# run ommand: streamlit run streamlit_app.py 

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
    st.title(APP_TITLE)
    
    
def initialize_session(refresh_session=False):
    if refresh_session:
        st.session_state.messages = []
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "counter" not in st.session_state:
            st.session_state.counter = 0
        if "costs" not in st.session_state:
            st.session_state.costs = []
        if "total_tokens" not in st.session_state:
            st.session_state.total_tokens = []
    

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
            "container": {"padding": "5!important", "background-color": "white", "border":"1px solid black"},
            }
        )
        st.session_state.selected_page = selected_page.lower()


def uploader_callback():
    if st.session_state['file_uploader'] is not None:
        uploaded_file = st.session_state['file_uploader']
        try:
            s_response = requests.post(os.path.join(API_URL,"upload"), files={"file": uploaded_file})
            print(s_response.json())
            if s_response.status_code == 200:
                response_data = s_response.json()
                st.session_state.counter += 1
                print(response_data["summary"], st.session_state.counter)
                post_ai_message_to_chat(response_data.get("summary", "Unknown response"))
            else:
                st.error(f"Error: {s_response.status_code}")
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
        - pdf  
        - html
        """
    )
    col2.markdown(
        """
        - db 
        - sqlite  
        - bla
        """
    )
    with st.sidebar.container():
        if uploaded_file := st.file_uploader(
            'dragndrop',
            type=["txt","csv","pdf","sqlite","db","html" ],
            on_change=uploader_callback,
            key="file_uploader",
            label_visibility="collapsed"
        ):
            st.success(f"File uploaded to backend")
            
        else:
            url = st.text_input('url',placeholder='OR enter url', label_visibility="collapsed")
            # TODO: if url is entered deactivate file upload
        add_vertical_space(1)
        with stylable_container(
            key="styled_container",
            css_styles="""
                {
                    background-color: #ffb499;
                    border-radius: 0.5em;
                }
                """,
        ):
            add_vertical_space(1)
            _, c2, _ = st.columns((1, 6, 1))
            with c2:
                temperature = st.slider('temperature', min_value=0, max_value=1)
                max_tokens = st.slider("max tokens:",min_value=1000, max_value=4000,value=4000)


@register_page(MAIN_PAGE)
def questionai():
    with st.container():
        for message in st.session_state.messages:
            #image = "xxx.png" if message["role"] == "user" else "xxx.png"
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("-> Post questions regarding the content of your file, AI will answer..."):
            # print(prompt)
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            response = f"Echo: {prompt}" # TODO: connect to API response
            
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
        elif len(st.session_state.messages)==0:
            image = Image.open('./static/main_picture3.png')
            st.image(image, caption=None)
    

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
    display_options_menu()
    MAIN_PAGE[st.session_state.selected_page]()

if __name__ == "__main__":
    main()