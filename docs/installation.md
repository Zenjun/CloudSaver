# 설치 및 실행

CloudSaver는 Python 3.11 이상이 필요합니다. 현재 설치 검증 결과와 미검증 환경은 [Phase 6 기록](development-plan.md)에 있습니다. 공개 패키지 레지스트리에 아직 게시하지 않았으므로 아래 명령은 저장소를 내려받은 뒤 루트에서 실행합니다.

## Python 패키지

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/cloudsaver demo scan --format json
```

기본 설치는 오프라인 데모와 저장된 보고서 명령만 제공합니다. AWS 수집에는 `.[aws]`, Custodian 검증·평가에는 `.[custodian]` 추가 의존성을 설치합니다. 두 기능을 함께 쓰려면 다음 명령을 실행합니다.

```bash
.venv/bin/python -m pip install '.[aws,custodian]'
```

휠을 직접 검증하려면 `python -m pip install build`, `python -m build` 후 새 가상환경에 `dist/cloudsaver-*.whl`을 설치합니다. 실제 AWS 자격 증명이나 네트워크 없이 `cloudsaver demo scan`이 실행되어야 합니다.

## Docker

```bash
docker build --platform linux/arm64 -t cloudsaver:local .
docker run --rm --network none --read-only cloudsaver:local demo scan --format json
```

x86-64에서는 `--platform linux/amd64`를 사용합니다. 이미지에는 AWS와 Custodian 추가 의존성이 포함되고, 기본 사용자는 UID/GID 10001이며 자격 증명은 포함하지 않습니다. 기본 명령은 도움말입니다. 이미지 빌드와 실행은 로컬 Docker 이미지·컨테이너를 사용합니다. 레지스트리에는 게시하지 않습니다.

실제 AWS 수집을 실행할 때는 자격 증명을 **명시적으로** 읽기 전용 마운트합니다. 호스트의 사용자 UID/GID로 실행하면 일반적인 `~/.aws/credentials` 파일 권한을 읽을 수 있습니다. 아래 예시는 네트워크를 사용하며 계정 조회를 수행하므로 권한·호출 비용을 먼저 검토해야 합니다.

```bash
docker run --rm --read-only --tmpfs /tmp:rw,nosuid,size=64m \
  --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$HOME/.aws,dst=/home/cloudsaver/.aws,readonly" \
  -e AWS_PROFILE=dev cloudsaver:local \
  scan --regions ap-northeast-2 --format json
```

EC2 인스턴스 프로필을 사용하는 경우 이미지 기본값인 `AWS_EC2_METADATA_DISABLED=true`를 명시적으로 재설정해야 합니다. 출력 파일은 기존 파일을 덮어쓰지 않으며, 컨테이너 밖에 보존하려면 소유권이 맞는 디렉터리를 별도로 마운트해야 합니다. Custodian 평가에는 임시 출력 공간이 필요하므로 리소스 수에 맞게 `/tmp` 크기를 조정합니다.

패키지 및 Docker 모두 macOS, Windows, 실제 AWS 계정과 Custodian 역할에서의 동작은 별도 검증 전입니다. 현재 서비스나 데몬을 설치하지 않습니다.
