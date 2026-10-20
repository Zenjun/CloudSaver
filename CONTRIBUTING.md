# 기여 안내

CloudSaver는 Python 3.11 이상에서 동작하는 CLI입니다. 개발 전에 [요구사항](agent.md), [아키텍처](docs/architecture.md), [보안 경계](docs/security.md)를 읽어 주세요. 기능 요청과 버그는 GitHub Issue에서 논의할 수 있습니다. 보안 문제는 [비공개 신고 안내](SECURITY.md)를 따릅니다.

## 개발 환경

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,custodian]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy
```

AWS 테스트는 Stubber 또는 fixture로 작성합니다. 테스트 및 CI에서 실제 계정을 호출하지 않습니다. 정책·비용 계산을 바꿀 때는 보호 리소스, 데이터 결측, 오류 상태와 금액 `UNKNOWN`을 함께 확인해 주세요. 출력에 실제 계정 ID, 태그 값, 공개 IP, 자격 증명이 나타나지 않도록 합니다.

작은 단위의 PR을 권장합니다. PR 설명에는 변경 이유, 재현 방법, 실행한 검사, 문서 변경, 남은 제약을 적어 주세요. 커밋 제목은 `feat:`, `fix:`, `docs:`, `test:`처럼 변경 성격을 짧게 표시합니다. 자동 포맷으로 무관한 파일을 바꾸지 않습니다.
