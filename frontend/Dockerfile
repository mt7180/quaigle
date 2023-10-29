FROM python:3.10

WORKDIR /app_frontend

COPY requirements.txt ./requirements.txt

ENV BACKEND_URL=http://54.93.192.159:8000

RUN pip3 install -r requirements.txt

EXPOSE 8501

COPY . /app_frontend

CMD streamlit run --server.port 8501 --server.enableCORS false streamlit_app.py