FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WEB_CONCURRENCY=1

WORKDIR /opt/jeux-rpg
COPY pyproject.toml constraints.txt ./
COPY jeuxRPG/ ./jeuxRPG/
RUN python -m pip install --no-cache-dir -c constraints.txt . \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin rpg \
    && mkdir -p /var/lib/jeux-rpg \
    && chown rpg:rpg /var/lib/jeux-rpg

USER 10001:10001
WORKDIR /var/lib/jeux-rpg
EXPOSE 8080
STOPSIGNAL SIGTERM
CMD ["python", "-m", "jeuxRPG.multiplayer.container_host"]
