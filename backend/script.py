

from llama_index import (
    VectorStoreIndex, 
    SimpleDirectoryReader,
    ServiceContext,
    set_global_service_context,
    get_response_synthesizer,
)
from llama_index.llms import OpenAI
from llama_index.node_parser import SimpleNodeParser
from llama_index.text_splitter import TokenTextSplitter
from llama_index.node_parser.extractors import (
    MetadataExtractor,
)
from llama_index.node_parser.extractors.marvin_metadata_extractor import (
    MarvinMetadataExtractor,
)
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.chat_engine.condense_question import CondenseQuestionChatEngine
from llama_index.callbacks import CallbackManager, TokenCountingHandler
from llama_index.memory import ChatMemoryBuffer
from llama_index.indices.vector_store.retrievers import VectorIndexRetriever
from llama_index.vector_stores.types import MetadataInfo, VectorStoreInfo

from marvin import ai_model
from llama_index.bridge.pydantic import BaseModel, Field
import pathlib
import tiktoken
import logging

from document_categories import CATEGORY_LABELS


class AITextDocument:
    """Loads and converts a text file into LlamaIndex nodes.
       The marvin ai_model predicts the text category based on a 
       given list and gives a short summary of the text based on the given llm_str. 
    """

    FILE_DIR = pathlib.Path(__file__).parent / "data"

    def __init__(self, document_name: str, llm_str: str, callback_manager: CallbackManager | None =None):
        self.callback_manager: CallbackManager | None = callback_manager
        self.document = self._load_document(document_name)
        self.nodes = self.split_document_and_extract_metadata(llm_str)
        self.text_category = self.nodes[0].metadata["marvin_metadata"].get("text_category")
        self.text_summary: str = self.nodes[0].metadata["marvin_metadata"].get("description")
        # logging.debug(f"Number of used tokens: {token_counter.total_embedding_token_count}")
        logging.debug(f"Category: {self.text_category}, Summary: {self.text_summary}")

    @classmethod
    def _load_document(cls, document_name, log=True):
        """loads only the data of the specified name"""
        return(
            SimpleDirectoryReader(
                input_files=[str(AITextDocument.FILE_DIR / document_name)],
                encoding="utf-8",
            ).load_data()[0]
        )

    def _get_text_splitter(self):
        return TokenTextSplitter(
            separator=" ", 
            chunk_size=1024, 
            chunk_overlap=128,
            callback_manager=self.callback_manager
        )
    
    def _get_metadata_extractor(self, llm_str):
        return MetadataExtractor(
            extractors=[
                MarvinMetadataExtractor(
                    marvin_model=AITextDocument.AIDocument, 
                    llm_model_string=llm_str,
                    show_progress = True,
                    callback_manager=self.callback_manager,

                ),
            ],
        )
    
    def split_document_and_extract_metadata(self, llm_str):
        text_splitter = self._get_text_splitter()
        metadata_extractor = self._get_metadata_extractor(llm_str)
        node_parser = SimpleNodeParser(
            text_splitter=text_splitter,
            metadata_extractor=metadata_extractor,
            callback_manager = self.callback_manager,
        )
        return node_parser.get_nodes_from_documents([self.document])


    @ai_model
    class AIDocument(BaseModel):
        description: str = Field(..., description="a brief summary of the document content")
        text_category: str = Field(...,description=f"best matching text category from the following list: {str(CATEGORY_LABELS)}")
    


class CustomLlamaIndexChatEngineWrapper:

    # system_prompt = f"""You are a chatbot that responds to all questions about the content of a given document, which is available in the form of embeddings in the given vector database. The user gives you instructions on which questions to answer. 
    #     When you write the answers, you need to make sure that the user's expectations are met. Remember that you are an accurate and experienced writer 
    #     and you write unique and short answers in the style of a {text_category} text. Don't add anything hallucinatory.
    #     Use friendly, easy-to-read language, and if it is a technical or scientific text, please stay correct and focused.
    #     Responses should be no longer than 10 sentences, unless the user explicitly specifies the number of sentences.
    # """

    OPENAI_MODEL = "gpt-3.5-turbo"
    llm = OpenAI(model=OPENAI_MODEL, temperature=0, max_tokens=512)

    def __init__(self, callback_manager=None):
        self.callback_manager = callback_manager
        self.service_context = self._create_service_context()
        set_global_service_context(self.service_context)
        self.documents = []
        #LlamaTextDocument(document_name, CustomLlamaIndexChatEngine.llm)
        self.vector_index = self._create_vector_index()
        #super().__init__()
        self.chat_engine = self.create_chat_engine() 
        

    def _create_service_context(self):
        return ServiceContext.from_defaults(
            llm=CustomLlamaIndexChatEngineWrapper.llm, 
            chunk_size=1024, 
            chunk_overlap=152,
            #system_prompt=system_prompt,
            callback_manager=self.callback_manager,
        )
    
    def add_document(self, document:AITextDocument):
        self.documents.append(document)
        self._add_to_vector_index(document.nodes)

    def _create_vector_index(self):
        #print(node. for doc in self.documents for node in doc.nodes)
        return VectorStoreIndex(
            [node for doc in self.documents for node in doc.nodes], # current use case: no docs availabe, so empty list []
            service_context=self.service_context
        ) # openai api is called with whole text to make the embeddings
    
    def _add_to_vector_index(self, nodes):
        self.vector_index.insert_nodes(
            nodes, 
            service_context=self.service_context) # is this enough or do I have to recreate the chat engine?

    def _create_vector_index_retriever(self):
        vector_store_info = VectorStoreInfo(
            content_info="content of uploaded text documents",
            metadata_info=[
                MetadataInfo(
                    name="text_category",
                    type="str",
                    description="best matching text category (e.g. Technical, Biagraphy, Sience Fiction, ... )",
                ),
                MetadataInfo(
                    name="description",
                    type="str",
                    description="a brief summary of the document content",
                ),
            ],
        )
        return VectorIndexRetriever(
            index=self.vector_index,
            vector_store_info=vector_store_info,
            similarity_top=10,
        )

    def create_chat_engine(self):
        vector_query_engine = RetrieverQueryEngine(
            retriever=self._create_vector_index_retriever(),
            response_synthesizer=get_response_synthesizer(),
            callback_manager=self.callback_manager,
        )
        return CondenseQuestionChatEngine.from_defaults(
            query_engine=vector_query_engine, 
            #condense_question_prompt=custom_prompt,
            #chat_history=custom_chat_history,
            memory = ChatMemoryBuffer.from_defaults(token_limit=1500),
            verbose=True,
            callback_manager=self.callback_manager,
        )

def set_up_chatbot():
    token_counter = TokenCountingHandler(
        tokenizer=tiktoken.encoding_for_model("gpt-3.5-turbo").encode
    )
    callback_manager = CallbackManager([token_counter])

    return (
        CustomLlamaIndexChatEngineWrapper(
            callback_manager=callback_manager
        ),
        callback_manager,
        token_counter,
    )

if __name__ == "__main__":
    import os
    import sys
    import certifi
    from dotenv import load_dotenv

    # workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
    os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
    os.environ["SSL_CERT_FILE"] = certifi.where()

    load_dotenv()

    API_KEY = os.getenv('OPENAI_API_KEY')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
    # openai_log = "debug"
    
    chat_engine, callback_manager, token_counter = set_up_chatbot()

    try: 
        document = AITextDocument("test2.txt", "gpt-3.5-turbo", callback_manager)
        chat_engine.add_document(document)

    except Exception as e:
        print(f"ERROR while loading and adding document to vector index: {e.args}")
        exit()

    questions = [
        "Where did Einstein live?",
        "What did he work on?", # does memory work (-> he)?
        "What was his favorite food?", # correct response: There is no information provided in the context about Einstein's favorite food.
    ]
    for question in questions:
        response = chat_engine.chat_engine.chat(question)
        print(response.response)
        logging.info(f"Number of used tokens: {token_counter.total_embedding_token_count}")

