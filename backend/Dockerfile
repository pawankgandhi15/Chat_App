FROM python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY backend/requirements.lock /service/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && useradd --uid 10001 --no-create-home app
COPY backend/app /service/app
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "app.run"]
