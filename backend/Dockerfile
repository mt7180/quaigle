FROM --platform=linux/amd64 python:3.10

ENV DEBUG 0

WORKDIR /app_backend

COPY ./requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 8000:8000

COPY . /app_backend/code

# for internal communication of front- and backend, which are both deployed on
# flyio in seperate containers, ipv6 needs to be bind to the host aswell, this
# is reached by exchanging host from "0.0.0.0" to "::"
CMD ["uvicorn", "code.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]