from llama_index import (
    SimpleWebPageReader,
    VectorStoreIndex,
    SimpleDirectoryReader,
    ServiceContext,
    StorageContext,
    load_index_from_storage,
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

# from llama_index.indices.vector_store.retrievers import VectorIndexRetriever
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

    cfd = pathlib.Path(__file__).parent / "data"

    def __init__(
        self,
        document_name: str,
        llm_str: str,
        callback_manager: CallbackManager | None = None,
    ):
        self.callback_manager: CallbackManager | None = callback_manager
        self.document = self._load_document(document_name)
        self.nodes = self.split_document_and_extract_metadata(llm_str)
        self.text_category = (
            self.nodes[0].metadata["marvin_metadata"].get("text_category")
        )
        self.text_summary: str = (
            self.nodes[0].metadata["marvin_metadata"].get("description")
        )

    @classmethod
    def _load_document(cls, identifier: str):
        """loads only the data of the specified name

        identifier: name of the text file as str
        """
        return SimpleDirectoryReader(
            input_files=[str(AITextDocument.cfd / identifier)],
            encoding="utf-8",
        ).load_data()[0]

    def _get_text_splitter(self):
        return TokenTextSplitter(
            separator=" ",
            chunk_size=1024,
            chunk_overlap=128,
            callback_manager=self.callback_manager,
        )

    def _get_metadata_extractor(self, llm_str):
        return MetadataExtractor(
            extractors=[
                MarvinMetadataExtractor(
                    marvin_model=AITextDocument.AIDocument,
                    llm_model_string=llm_str,
                    show_progress=True,
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
            callback_manager=self.callback_manager,
        )
        return node_parser.get_nodes_from_documents([self.document])

    @ai_model
    class AIDocument(BaseModel):
        description: str = Field(
            ..., description="A brief summary of the document content in 5 sentences."
        )
        text_category: str = Field(
            ...,
            description=f"""best matching text category from the following list: 
                {str(CATEGORY_LABELS)}
            """,
        )


class AIHtmlDocument(AITextDocument):
    @classmethod
    def _load_document(cls, identifier: str):
        """loads the data of an html file at a given url

        identifier: url of the html file as str
        """
        return SimpleWebPageReader(
            html_to_text=True,
        ).load_data(
            [identifier]
        )[0]


class CustomLlamaIndexChatEngineWrapper:
    system_prompt: str = """You are a chatbot that responds to all questions about 
    the given context. The user gives you instructions on which questions to answer. 
    When you write the answers, you need to make sure that the user's expectations are 
    met. Remember that you are an accurate and experienced writer 
    and you write unique answers. Don't add anything hallucinatory.
    Use friendly, easy-to-read language, and if it is a technical or scientific text, 
    please stay correct and focused.
    Responses should be no longer than 10 sentences, unless the user explicitly 
    specifies the number of sentences.
    """

    OPENAI_MODEL = "gpt-3.5-turbo"
    llm = OpenAI(model=OPENAI_MODEL, temperature=0, max_tokens=512)
    cfd = pathlib.Path(__file__).parent

    def __init__(self, callback_manager=None):
        self.callback_manager = callback_manager
        self.text_category: str = ""  # default, if no document is loaded yet
        self.llm = OpenAI(
            model=CustomLlamaIndexChatEngineWrapper.OPENAI_MODEL,
            temperature=0,
            max_tokens=512,
        )
        self.service_context = self._create_service_context()
        set_global_service_context(self.service_context)
        self.documents = []

        if any(
            pathlib.Path(CustomLlamaIndexChatEngineWrapper.cfd / "storage").iterdir()
        ):
            self.storage_context = StorageContext.from_defaults(
                persist_dir=str(CustomLlamaIndexChatEngineWrapper.cfd / "storage"),
            )
            self.vector_index = load_index_from_storage(
                storage_context=self.storage_context
            )
        else:
            self.vector_index = self.create_vector_index()
        self.chat_engine = self.create_chat_engine()

    def _create_service_context(self):
        return ServiceContext.from_defaults(
            chunk_size=1024,
            chunk_overlap=152,
            llm=self.llm,
            system_prompt=CustomLlamaIndexChatEngineWrapper.system_prompt,
            callback_manager=self.callback_manager,
        )

    def add_document(self, document: AITextDocument):
        self.documents.append(document)
        self._add_to_vector_index(document.nodes)
        self.text_category = (
            document.text_category
        )  # TODO: find mojority, if multiple docs are loaded
        self.vector_index.storage_context.persist(
            persist_dir=CustomLlamaIndexChatEngineWrapper.cfd / "storage"
        )

    def empty_vector_store(self):
        doc_ids = list(self.vector_index.ref_doc_info.keys())
        for doc_id in doc_ids:
            self.vector_index.delete_ref_doc(doc_id, delete_from_docstore=True)
        self.vector_index.storage_context.persist(
            persist_dir=CustomLlamaIndexChatEngineWrapper.cfd / "storage"
        )
        self.documents.clear()

    def create_vector_index(self):
        # print(node. for doc in self.documents for node in doc.nodes)
        return VectorStoreIndex(
            [
                node for doc in self.documents for node in doc.nodes
            ],  # current use case: no docs availabe, so empty list []
            service_context=self.service_context,
            storage_context=self.storage_context,
        )  # openai api is called with whole text to make the embeddings

    def _add_to_vector_index(self, nodes):
        self.vector_index.insert_nodes(
            nodes,
            # service_context=self.service_context)
            # # is this enough or do I have to recreate the chat engine?
        )

    def _create_vector_index_retriever(self):
        vector_store_info = VectorStoreInfo(
            content_info="content of uploaded text documents",
            metadata_info=[
                MetadataInfo(
                    name="text_category",
                    type="str",
                    description="""best matching text category (e.g. Technical, 
                        Biagraphy, Sience Fiction, ... )
                    """,
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
            # condense_question_prompt=custom_prompt,
            # chat_history=custom_chat_history,
            memory=ChatMemoryBuffer.from_defaults(token_limit=1500),
            verbose=True,
            callback_manager=self.callback_manager,
        )

    def clear_chat_history(self):
        self.chat_engine.reset()

    def update_temp(self, temperature):
        # see https://gpt-index.readthedocs.io/en/v0.8.34/examples/llm/XinferenceLocalDeployment.html
        self.vector_index.service_context.llm.__dict__.update(
            {"temperature": temperature}
        )
        # self.llm.temperature=temperature


def set_up_chatbot():
    token_counter = TokenCountingHandler(
        tokenizer=tiktoken.encoding_for_model("gpt-3.5-turbo").encode
    )
    callback_manager = CallbackManager([token_counter])

    return (
        CustomLlamaIndexChatEngineWrapper(callback_manager=callback_manager),
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

    # API_KEY = os.getenv('OPENAI_API_KEY')
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
        "What did he work on?",  # does memory work (-> he)?
        "What was his favorite food?",
        # correct response: There is no information provided in the context
        # about Einstein's favorite food.
    ]
    for question in questions:
        response = chat_engine.chat_engine.chat(question)
        print(response.response)
        logging.info(
            f"Number of used tokens: {token_counter.total_embedding_token_count}"
        )
