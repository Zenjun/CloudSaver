# syntax=docker/dockerfile:1
FROM python:3.15-slim-bookworm@sha256:2a41267d9de9d358f77a1de356e0f16ecba8d39827855be0ce9ef4792edce402 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m venv /opt/cloudsaver \
    && /opt/cloudsaver/bin/python -m pip install --no-cache-dir '.[aws,custodian]'

FROM python:3.15-slim-bookworm@sha256:2a41267d9de9d358f77a1de356e0f16ecba8d39827855be0ce9ef4792edce402

ENV PATH="/opt/cloudsaver/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AWS_EC2_METADATA_DISABLED=true
COPY --from=builder /opt/cloudsaver /opt/cloudsaver
RUN groupadd --system --gid 10001 cloudsaver \
    && useradd --system --uid 10001 --gid cloudsaver --create-home cloudsaver
USER 10001:10001
WORKDIR /home/cloudsaver
ENTRYPOINT ["cloudsaver"]
CMD ["--help"]
