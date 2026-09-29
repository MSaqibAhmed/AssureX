FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home assurex && mkdir -p /app/private/evidence /app/artifacts && chown -R assurex:assurex /app
USER assurex
EXPOSE 8000
CMD ["uvicorn","src.main:app","--host","0.0.0.0","--port","8000"]
