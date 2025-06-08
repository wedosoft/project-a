FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
# Python의 표준 출력을 즉시 플러시하여 Docker 로그에 실시간 표시
ENV PYTHONUNBUFFERED=1

# 더 상세한 로그 출력을 위한 Uvicorn 설정 개선
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info", "--access-log"]