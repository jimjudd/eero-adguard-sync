FROM python:3.10-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

COPY requirements.txt pyproject.toml setup.py VERSION README.md ./
COPY eero_adguard_sync ./eero_adguard_sync

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY docker/entrypoint.sh .
COPY docker/sync.sh .
RUN chmod +x /usr/src/app/entrypoint.sh /usr/src/app/sync.sh
ENTRYPOINT ["./entrypoint.sh"]
CMD ["crond", "-f", "-l", "2"]
