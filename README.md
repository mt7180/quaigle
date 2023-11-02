# Quaigle - Your Talk-to-Your-Document Companion

**Welcome to Quaigle!** Quaigle is a versatile program for text-based interactions with documents, whether text documents (txt, pdf or a url to a static, non-complex website) or databases. It leverages the new evolving technology of generative AI and uses the Generative Pre-trained Transformer 3 (gpt-3.5-turbo & gpt-3.5-turbo-instruct) LLM  to answer your questions about the uploaded documents. It can extract insights from your documents, gives you a quiz about the content or harness the power of natural language based querying of databases.

## Table of Contents

- [Features](#features)
  - [Query Text](#query-Text)
  - [Create Quizzes](#create-quizzes)
  - [Query SQL Databases](#query-sql-databases)
- [Continuous Deployment](#continuous-deployment)
- [Future Improvements](#future-improvements)

## Features

### Query Text

Quaigle allows for upload text in several formats, including TXT and PDF files, or through a URL. The text will be embedded and stored to a vector database. While embedding a marvin ai-model determines its category and main subject. Keep in mind that the length of the text is limited by the max-token limit for embeddings, especially when using a Free Tier OpenAI API Key. Larger PDFs can be devided into smaller parts and uploaded sequentially, and all text data is stored in the same vector database. The embedding can take some time, depending on the amount of words to embed.
A LlamaIndex CondenseQuestionChatEngine with RetrieverQueryEngine is used to extract relevant context from the vector database and use it for the query using the openai API. 

### Create Quizzes

Using the data from a text source (PDF, TXT, or URL), also a quizz can be generated. Quaigle backend provides structured output for quizzes, which is seamlessly integrated to the frontend quiz interface.

### Query SQL Databases

Quaigle supports querying a SQLite database by natural language, which is a powerful tool for data-driven questions and makes databases accessible to everyone. The size of the uploadable database is currently limited by the frontend (max 40MB), but with optimal frontend scaling no limit is set. A Langchain SQLDatabaseChain with Runnables is used to provide natural language answers. For conveniance also the used SQL query is given as output.

## Continuous Deployment

Quaigle is deployed via CI/CD using GitHub Actions and Pulumi for infrastructure as code to deploy the backend to AWS EC2 instance. The frontend is hosted on fly.io. Changes in the frontend, backend, or infrastructure trigger automated updates to the hosted application.

## Future Improvements
- Possible future improvement on quality of quiz-questions:
  using  Llamaindex DatasetGenerator and RelevancyEvaluator in combination with gpt4 to generate the list of questions of relevance that could be asked about the data won't have to stick the questions to the main subject of the text
  https://gpt-index.readthedocs.io/en/latest/examples/evaluation/QuestionGeneration.html
  https://betterprogramming.pub/llamaindex-how-to-evaluate-your-rag-retrieval-augmented-generation-applications-2c83490f489
- Improvement for text Embedding with training data (EmbeddingAdapterFinetuneEngine): https://levelup.gitconnected.com/enhancing-rag-through-llamaindexs-blueprint-for-effective-embedding-and-llm-fine-tuning-a5b19f9cdeb0
- for url upload: split website to bypass the token limit


![frontend_view](screenshots/frontend_view.png)
![frontend_view](screenshots/questions.png)
![frontend_view](screenshots/quiz.png)
![frontend_view](screenshots/database.png)
