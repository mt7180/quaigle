FROM python:3.10

WORKDIR /app_backend

COPY ./requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 8000:8000

COPY . /app_backend

CMD ["uvicorn", "fastapi_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]