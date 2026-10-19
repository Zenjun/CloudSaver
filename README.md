# CloudSaver

AWS 비용 절감 후보의 근거, 예상 절감액과 운영 위험을 함께 설명하는 셀프 호스팅 CLI입니다. **현재 Phase 1 데모 CLI만 구현되었습니다.** 실제 AWS 조회나 리소스 변경 기능은 없습니다.

- [제품 요구사항과 원본 계획](agent.md)
- [아키텍처와 결정 기록](docs/architecture.md)
- [CLI 및 JSON 계약](docs/cli-contract.md)
- [보안 경계와 AWS 권한](docs/security.md)
- [단계별 개발 계획과 완료 기준](docs/development-plan.md)

## 로컬 설치와 5분 데모

Python 3.11 이상과 `venv`/`pip`가 필요합니다. 현재 직접 검증한 환경은 Linux aarch64, Python 3.13.5입니다. 다음 명령은 저장소 루트에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/cloudsaver --help
.venv/bin/cloudsaver demo scan
.venv/bin/cloudsaver demo scan --format json
.venv/bin/cloudsaver demo scan --format json --output demo-report.json
```

데모에는 개발 EC2, 보호된 프로덕션 EC2, 분리된 EBS, 미연결 Elastic IP, 메트릭 부족 EC2가 들어 있습니다. 모든 데이터는 가상이며 출력에 `DEMO DATA`를 표시합니다. 가격 자료가 없으므로 절감액은 `UNKNOWN`입니다. 낮은 CPU나 분리 상태만으로 중지·삭제를 권하지 않습니다.

`--output`은 새 파일에만 쓰고 기존 파일을 덮어쓰지 않습니다. 생성 파일 권한은 소유자 읽기/쓰기로 제한합니다. JSON은 표준 출력으로도 받을 수 있습니다. 데모 명령은 AWS 자격 증명과 네트워크가 필요 없습니다.

## 개발 검증

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests
.venv/bin/mypy
```

Python 패키지 구성은 [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)의 `pyproject.toml` 및 콘솔 스크립트 방식에 따릅니다. Phase 2 이후의 AWS 수집과 비용 데이터 조회에는 별도 권한·비용 검토가 필요합니다.

라이선스, 실제 AWS 계정 연결, 공개 배포는 아직 결정되지 않았습니다.
