import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.stylable_container import stylable_container
from dotenv import load_dotenv
import os
from pathlib import Path
from PIL import Image

from utils.helpers import register_page

#load_dotenv()
#API_KEY = os.getenv('OPENAI_API_KEY')
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
        st.session_state.openai_lc_client = None
        st.session_state.result = None
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []
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


def display_sidemenu():
    st.sidebar.title('Menu')
    st.sidebar.markdown(
    """
    Please uploade your file or enter a url.  Supported file types: 
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
        st.file_uploader('dragndrop',label_visibility="collapsed")
        url = st.text_input('url',placeholder='OR enter url', label_visibility="collapsed")
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
                st.slider('temperature', min_value=0, max_value=1)
                st.slider("max tokens:",min_value=1000, max_value=4000,value=4000)


@register_page(MAIN_PAGE)
def questionai():
    with st.container():
        if prompt := st.chat_input("-> Post questions regarding the content of your file, AI will answer..."):
            print(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            for message in st.session_state.messages:
                #image = "xxx.png" if message["role"] == "user" else "xxx.png"
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        else:
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

def main():
    set_page_settings()
    initialize_session()
    display_sidemenu()
    display_options_menu()
    MAIN_PAGE[st.session_state.selected_page]()

if __name__ == "__main__":
    main()