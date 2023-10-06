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
# provide OpenAI access to data in specific database (in this case: kaggle Amazon
# database about customers' reviews and their helpfulness)
# db = SQLDatabase.from_uri("sqlite:///data/database.sqlite")
# db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True, use_query_checker=True)


def get_schema(_):
    return db.get_table_info()


def run_query(query):
    return db.run(query)


inputs = {"schema": RunnableLambda(get_schema), "question": itemgetter("question")}

template = """Based on the table schema below, write a SQL query that would answer 
the user's question:
{schema}

Question: {question}
SQL Query:"""
prompt = ChatPromptTemplate.from_template(template)

sql_response = (
    RunnableMap(inputs) | prompt | llm.bind(stop=["\nSQLResult:"]) | StrOutputParser()
)

# print(sql_response.invoke({"question": "How many employees are there?"}))

template = """Based on the table schema below, question, sql query, and sql response, 
write a natural language response:
{schema}

Question: {question}
SQL Query: {query}
SQL Response: {response}"""
prompt_response = ChatPromptTemplate.from_template(template)

full_chain = (
    RunnableMap(
        {
            "question": itemgetter("question"),
            "query": sql_response,
        }
    )
    | {
        "schema": RunnableLambda(get_schema),
        "question": itemgetter("question"),
        "query": itemgetter("query"),
        "response": lambda x: db.run(x["query"]),
    }
    | prompt_response
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
