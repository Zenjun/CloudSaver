# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN python -m venv /opt/cloudsaver \
    && /opt/cloudsaver/bin/python -m pip install --no-cache-dir '.[aws,custodian]'

FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641

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
