FROM python:3.5

RUN pip install \
	boto3 \
	flask \
	requests

COPY . /src

EXPOSE 5000

CMD ["python", "/src/app.py"]
