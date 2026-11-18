# syntax=docker/dockerfile:1
FROM node:24.11.1-bookworm-slim@sha256:48abc13a19400ca3985071e287bd405a1d99306770eb81d61202fb6b65cf0b57 AS desktop

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHON=python3 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ELECTRON_CACHE=/opt/cache/electron \
    ELECTRON_BUILDER_CACHE=/opt/cache/electron-builder \
    WINEDEBUG=-all \
    CSC_IDENTITY_AUTO_DISCOVERY=false
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 git wine wine64 xvfb xauth \
    libgtk-3-0 libnss3 libasound2 libgbm1 libxss1 libfuse2 \
    zip unzip xz-utils p7zip-full \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /project
COPY desktop/package.json desktop/package-lock.json ./desktop/
RUN --mount=type=cache,target=/root/.npm npm --prefix desktop ci --no-audit --no-fund
COPY pyproject.toml ./
COPY jeuxRPG/ ./jeuxRPG/
COPY projects/authored/ ./projects/authored/
COPY desktop/main.cjs desktop/runtime.cjs desktop/build.cjs ./desktop/
COPY desktop/test/ ./desktop/test/
COPY scripts/ ./scripts/
COPY docs/DISTRIBUTION_LIREMOI.md ./docs/
COPY deploy/build/ ./deploy/build/
RUN node desktop/build.cjs --prepare-only && node --test desktop/test/*.test.cjs
ENTRYPOINT ["python3", "scripts/build_container.py"]
CMD ["windows"]

FROM desktop AS android
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    ANDROID_HOME=/project/.toolchains/android-sdk \
    ANDROID_USER_HOME=/opt/cache/android \
    GRADLE_USER_HOME=/opt/cache/gradle
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
COPY android/ ./android/
RUN python3 deploy/build/install_tools.py
CMD ["all"]
