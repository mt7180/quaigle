# https://python.langchain.com/docs/expression_language/cookbook/sql_db
import logging
import sys
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SQLDatabase
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableLambda, RunnableMap, RunnablePassthrough
from langchain.prompts import ChatPromptTemplate

# from langchain_experimental.sql import SQLDatabaseChain

from operator import itemgetter

from dotenv import load_dotenv
import certifi
import os

# load your API key to the environment variables
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
# openai_log = "debug"

# workaround for mac to solve SSL: CERTIFICATE_VERIFY_FAILED Error
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
db = SQLDatabase.from_uri("sqlite:///data/database.sqlite")
logging.debug(db.get_table_info())


def get_schema(_):
    return db.get_table_info()


def run_query(working_dict):
    logging.debug(working_dict["query"])
    return db.run(working_dict["query"])


query_generator = (
    RunnableMap(
        {"schema": RunnableLambda(get_schema), "question": itemgetter("question")}
    )
    | ChatPromptTemplate.from_template(
        """Based on the table schema below, write a SQL query that would answer 
        the user's question:
        {schema}

        Question: {question}
        SQL Query:"""
    )
    | llm.bind(stop=["\nSQLResult:"])
    | StrOutputParser()
    | {"query": RunnablePassthrough()}
)


chain = (
    query_generator
    | {"response": RunnableLambda(run_query), "question": RunnablePassthrough()}
    | ChatPromptTemplate.from_template(
        """Based on the question and the sql response, 
        write a natural language response:

        Question: {question}
        SQL Response: {response}"""
    )
    | llm
)

ai_response = chain.invoke(
    {
        "question": """What is the name of the user who wrote the largest number of 
        helpful reviews for amazon?
        """
    }
)
print(ai_response.content)


# if __name__ == "__main__":
