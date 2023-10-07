# https://python.langchain.com/docs/expression_language/cookbook/sql_db
import logging
import sys
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SQLDatabase
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableLambda, RunnableMap
from langchain.prompts import ChatPromptTemplate

# from langchain_experimental.sql import SQLDatabaseChain

from operator import itemgetter

from dotenv import load_dotenv
import certifi
import os

# load your API key to the environment variables
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
openai_log = "debug"

# workaround for mac to solve SSL: CERTIFICATE_VERIFY_FAILED Error
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
db = SQLDatabase.from_uri("sqlite:///data/database.sqlite")
logging.debug(db.get_table_info())


def get_schema(_):
    return db.get_table_info()


def run_query(working_dict):
    return db.run(working_dict["query"])


prompt1 = ChatPromptTemplate.from_template(
    """Based on the table schema below, write a SQL query that would answer 
    the user's question:
    {schema}

    Question: {question}
    SQL Query:"""
)

query_generator = (
    RunnableMap(
        {"schema": RunnableLambda(get_schema), "question": itemgetter("question")}
    )
    | prompt1
    | llm.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
)

prompt2 = ChatPromptTemplate.from_template(
    """Based on the question the sql query and the sql response, 
    write a natural language response:

    Question: {question}
    SQL Query: {query}
    SQL Response: {response}"""
)

full_chain = (
    RunnableMap(
        {
            "question": itemgetter("question"),
            "query": query_generator,
        }
    )
    | {
        "question": itemgetter("question"),
        "query": itemgetter("query"),
        "response": RunnableLambda(
            run_query
        ),  # same as "response": lambda x: db.run(x["query"]),
    }
    | prompt2
    | llm
)
response = full_chain.invoke(
    {
        "question": """What is the name of the user who wrote the largest number of 
        helpful reviews for amazon?
        """
    }
)
print(response)


# if __name__ == "__main__":
