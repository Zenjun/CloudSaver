# CloudSaver

AWS 비용 절감 후보의 근거, 예상 절감액과 운영 위험을 함께 설명하는 셀프 호스팅 CLI입니다. **현재 Phase 1–5의 데모, AWS 읽기 전용 수집, 후보 탐지, 로컬 비용 시나리오·위험 설명, Cloud Custodian 정책 검증·평가 어댑터가 구현되었습니다.** 실제 AWS 가격·청구 조회는 아직 없습니다.

- [제품 요구사항과 원본 계획](agent.md)
- [아키텍처와 결정 기록](docs/architecture.md)
- [CLI 및 JSON 계약](docs/cli-contract.md)
- [보안 경계](docs/security.md)와 [AWS 읽기 권한](docs/aws-permissions.md)
- [단계별 개발 계획과 완료 기준](docs/development-plan.md)
- [탐지 정책과 판단 한계](docs/policies.md)
- [비용 계산과 위험 평가](docs/cost-model.md)
- [Cloud Custodian 정책 연동](docs/custodian.md)

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

## AWS 읽기 전용 스캔과 후보 탐지 (Phase 2–3)

AWS 수집기는 구현됐고 Stubber로만 검증했습니다. **실제 계정에서는 아직 실행하지 않았습니다.** 계정에서 사용할 때는 [읽기 권한과 호출 비용](docs/aws-permissions.md)을 먼저 확인하세요.

```bash
.venv/bin/python -m pip install -e '.[aws]'
.venv/bin/cloudsaver scan --profile dev --regions ap-northeast-2 --format json
```

`--profile`은 생략할 수 있으며, 이때 AWS SDK의 표준 자격 증명 체인을 사용합니다. `--regions`는 필수이고 쉼표로 여러 리전을 지정할 수 있습니다. 결과에는 발견 리소스와 세 가지 가설적 후보 정책의 결과가 함께 들어갑니다. `analysis_status`는 `COMPLETE`, `PARTIAL`, `NOT_EVALUATED` 중 하나입니다. [정책 조건](docs/policies.md)을 확인하세요. 오류가 나면 범위별 수집 실패와 종료 코드가 표시됩니다.

## 저장된 보고서 설명과 비용 시나리오 (Phase 4)

```bash
.venv/bin/cloudsaver demo scan --format json --output demo-report.json
.venv/bin/cloudsaver opportunities --input demo-report.json
.venv/bin/cloudsaver explain demo:low_utilization_ec2:ap-northeast-2:i-demo-dev --input demo-report.json
.venv/bin/cloudsaver report --input demo-report.json --format json
.venv/bin/cloudsaver report --input demo-report.json --cost-input costs.json --format json
```

`--cost-input`은 사용자가 월별 비용 항목과 출처를 직접 제공할 때만 사용합니다. 계산 결과는 실제 청구 절감이 아닌 **조건부 시나리오**이며, 입력이 없으면 `UNKNOWN`입니다. 형식과 잔존 비용 처리 방식은 [비용 계산 문서](docs/cost-model.md)에 있습니다. 저장된 보고서 명령은 AWS에 접속하지 않습니다.

## Cloud Custodian 정책 검증과 평가 (Phase 5)

```bash
.venv/bin/python -m pip install -e '.[custodian]'
.venv/bin/cloudsaver custodian validate --policy policy.yml --format json
.venv/bin/cloudsaver custodian evaluate --policy policy.yml --region ap-northeast-2 --assume-role arn:aws:iam::123456789012:role/CloudSaverReadOnly --format json
```

`validate`는 로컬에서 정책 구문을 확인합니다. `evaluate`는 지정한 계정에 읽기 API를 호출하므로 IAM 역할과 해당 역할을 맡을 권한이 필요합니다. 실제 AWS 계정에서는 아직 시험하지 않았습니다. 입력 정책의 허용 범위, 역할 권한, 결과 형식은 [Custodian 연동 문서](docs/custodian.md)에 있습니다.

## 개발 검증

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests
.venv/bin/mypy
```

Python 패키지 구성은 [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)의 `pyproject.toml` 및 콘솔 스크립트 방식에 따릅니다. Phase 2 이후의 AWS 수집과 비용 데이터 조회에는 별도 권한·비용 검토가 필요합니다.

라이선스와 정식 패키지 릴리스는 아직 결정되지 않았습니다. 실제 AWS 계정 조회도 검증하지 않았습니다.
