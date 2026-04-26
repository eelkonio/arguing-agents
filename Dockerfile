# Stage 1 — Python dependencies
FROM python:3.13-slim AS builder
WORKDIR /app
RUN pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --output requirements.txt
RUN pip install --prefix=/install -r requirements.txt

# Stage 2 — Frontend build
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 3 — Final runtime
FROM python:3.13-slim
WORKDIR /app

# Install AWS CLI v2 (required for Bedrock subprocess calls)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip && \
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
      -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/awscliv2.zip /tmp/aws && \
    apt-get purge -y curl unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY src/ ./src/
COPY --from=frontend-builder /app/dist ./static/

ENV HOME="/tmp"
EXPOSE 8080
CMD ["uvicorn", "multi_agent_debate.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
