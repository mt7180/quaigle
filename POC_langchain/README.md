# langchain_vectordb_openai_project

## Talk to your data
### query_text_files.ipynb
- extract and embed text files from the data folder and store it in a faiss vector database
- make OpenAI query including vector database and query-history to [ask questions about the text]()
- to ensure OpenAI uses your own database, provide a text about e.g. a fictive person or animal the AI doesn't know yet

### query_pdf_files.ipynb
- extract and embed pdf files from the data folder and store the text in a FAISS vector database
- perform OpenAI query including vector database and query-history to [ask questions about the text in a pdf file]()

### query_with_functions
- provide openai API with different functions that it can call in addition to its own knowledge base
- here, the Wolfram Alpha API is used to [improve Chatgpt output in the field of real-time data, mathematical calculations, and scientific problems](). (put your free wolfram alpha app id to the .env file)
- even images provided by the wolfram alpha API are catched (as with the expensive chatgpt plus plugin) and displayed in the notebook (to my knowledge langchain WolframAlphaAPIWrapper does not trigger the includepodid parameter in the request)
- [talk with your own database](): give openai a function which gives access to your database and the langchain SQLDatabaseChain gives easiest access ever, just type your question concerning the data in natural language

# General Advice
- add a /data folder to your project directory and put your own data files in here (.txt, .pdf or db/ .sql)
- get your OpenAI API keys online (chatgpt plus or billing on demand)
- put your keys safely in an .env file in the project folder and do not upload them somewhere (github), list the file e.g. in your .gitignore file
- note that costs will arise for using the OpenAI API, which depend on the length of the text or pdf files. However, the costs for embedding and querying on a 30-page scientific paper were still less than 0.02USD in my case, the amazon database query still below 0.01USD - regularly check your daily usage online in your OpenAI account!

