FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY static ./static
COPY templates ./templates

EXPOSE 5001

CMD ["python", "app.py"]