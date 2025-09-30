FROM python:3.13-slim
ENV PYTHONFAULTHANDLER=1 PYTHONHASHSEED=random PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app
RUN pip install --upgrade pip && \
    pip install pipx
RUN pipx install "poetry==2.2.1"
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true && \
    poetry env use /usr/local/bin/python
RUN poetry install --only=main --no-root
COPY lib lib/
COPY get-sites.py .
CMD ["poetry", "run", "python", "get-sites.py"]