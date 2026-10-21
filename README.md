# CloudSaver

CloudSaver는 AWS에서 **비용 절감 검토 후보**를 찾고, 판단 근거·운영 위험·예상 비용의 불확실성을 함께 보여주는 셀프 호스팅 CLI입니다. 리소스를 자동으로 중지하거나 삭제하지 않습니다. AWS 계정이 없어도 가상 데이터로 전체 분석 흐름을 시험할 수 있습니다.

> **현재 상태:** 개발 버전입니다. 데모·탐지·저장 보고서 분석·HTML 대시보드와 Cloud Custodian 정책 검증을 사용할 수 있습니다. AWS 읽기 전용 수집과 Custodian 평가는 모의 테스트를 거쳤지만 **실제 AWS 계정에서는 아직 검증하지 않았습니다.** 기본 스캔은 가격·청구 API를 호출하지 않아 절감액이 `UNKNOWN`입니다.

## 목차

- [5분 시작: AWS 없이 데모 실행](#5분-시작-aws-없이-데모-실행)
- [결과 읽는 법](#결과-읽는-법)
- [명령 한눈에 보기](#명령-한눈에-보기)
- [저장 보고서와 비용 시나리오](#저장-보고서와-비용-시나리오)
- [HTML 대시보드와 실행 안전 검토](#html-대시보드와-실행-안전-검토)
- [AWS 읽기 전용 스캔](#aws-읽기-전용-스캔)
- [Cloud Custodian 정책 검증](#cloud-custodian-정책-검증)
- [Docker 실행](#docker-실행)
- [안전·제한 사항](#안전제한-사항)
- [문제 해결](#문제-해결)
- [개발·문서·라이선스](#개발문서라이선스)

## 5분 시작: AWS 없이 데모 실행

Python **3.11 이상**과 `venv`/`pip`가 필요합니다. 패키지 레지스트리 설치 안내 대신 현재 저장소의 소스에서 설치합니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
git clone https://github.com/Zenjun/CloudSaver.git
cd CloudSaver
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/cloudsaver --help
.venv/bin/cloudsaver demo scan
.venv/bin/cloudsaver demo scan --format json --output demo-report.json
```

마지막 명령은 저장된 보고서 예제입니다. 데모에는 개발 EC2, 보호된 프로덕션 EC2, 분리된 EBS, 연결되지 않은 Elastic IP, 메트릭이 부족한 EC2가 포함됩니다. 출력의 `DEMO DATA`는 모두 가상 데이터라는 표시입니다. **데모 실행에는 AWS 자격 증명과 AWS API 호출이 필요하지 않습니다.** 설치 과정에서는 Python 빌드 의존성을 내려받기 위해 인터넷이 필요할 수 있습니다.

`--output`은 새 파일만 만들며 기존 파일은 덮어쓰지 않습니다. 출력 파일의 권한은 소유자 읽기/쓰기(`0600`)입니다. 예제를 다시 실행할 때는 새 파일명을 지정하세요.

## 결과 읽는 법

하나의 탐지 결과(`finding`)에는 정책·리소스 참조, 상태, 근거(`evidence`), 위험(`risk`), 비용(`savings`)이 들어갑니다. JSON에는 `schema_version`, `data_kind`, `scanned_at`, `scope`, `status`, `findings`, `collection_issues`가 포함됩니다.

| 표시 | 뜻 |
|---|---|
| `CANDIDATE` | 추가 검토가 필요한 후보. 중지·삭제 권고나 실행 허가가 아닙니다. |
| `EXCLUDED` | 보호 태그 등으로 후보에서 제외했습니다. |
| `INSUFFICIENT_DATA` | 메트릭이나 관찰 기간이 부족합니다. 사용량 0으로 해석하지 않습니다. |
| 위험 `UNKNOWN` | 운영 영향이 불분명합니다. 안전하다는 뜻이 아닙니다. |
| 절감액 `UNKNOWN` | 검증 가능한 가격·청구 자료가 없습니다. 0원이라는 뜻이 아닙니다. |
| 신뢰도 `CONDITIONAL` | 사용자가 제공한 금액으로 계산한 가상 시나리오입니다. 실제 청구 절감액이 아닙니다. |

AWS 보고서의 `status: PARTIAL` 또는 `FAILED`와 `scope.failed`는 일부 범위가 수집되지 않았다는 뜻입니다. 빈 `findings` 목록만 보고 낭비가 없다고 판단하지 마세요. 기본 탐지 정책은 분리 EBS, 저사용률 의심 EC2, 미연결 Elastic IP의 세 가지입니다. 기준과 한계는 [탐지 정책](docs/policies.md)에 있습니다.

## 명령 한눈에 보기

아래 예제는 가상환경 설치 후 `.venv/bin/cloudsaver`로 실행합니다. 각 명령의 상세 옵션은 `cloudsaver <명령> --help`에서 확인할 수 있습니다.

| 명령 | 용도 | AWS 연결 |
|---|---|---|
| `demo scan` | 가상 데이터 분석 | 없음 |
| `scan --regions ...` | EC2·EBS·Elastic IP와 CloudWatch 읽기 전용 수집 | 있음 |
| `opportunities --input ...` | 저장 보고서의 `CANDIDATE`만 보기 | 없음 |
| `explain FINDING_ID --input ...` | 특정 후보의 근거·위험·비용 설명 | 없음 |
| `report --input ...` | 저장 보고서 전체 다시 보기 | 없음 |
| `dashboard --input ... --output ...` | 독립 HTML 대시보드 생성 | 없음 |
| `action-review FINDING_ID --input ...` | 가정한 작업의 차단 사유 확인 | 없음 |
| `custodian validate --policy ...` | 허용된 정책 부분집합 검증 | 없음 |
| `custodian evaluate --policy ... --region ... --assume-role ...` | 읽기 전용 역할로 정책 평가 | 있음 |

표가 기본 출력이고 지원 명령에 `--format json`을 붙이면 기계가 읽을 수 있는 JSON이 나옵니다. `dashboard`는 HTML 파일을 만들기 때문에 `--output`이 필수입니다. 명령 성공 종료 코드는 `0`이며, `action-review`의 `0`은 **검토 명령 성공**만 뜻하고 실행 허가는 아닙니다. `2`는 인수·입력 오류, `3`은 자격 증명 문제, `4`는 권한 거부, `5`는 전체 수집/평가 실패, `6`은 부분 수집 성공을 나타냅니다. 자세한 구조와 종료 코드는 [CLI 계약](docs/cli-contract.md)에 있습니다.

## 저장 보고서와 비용 시나리오

앞에서 만든 `demo-report.json`으로 후보를 확인합니다.

```bash
.venv/bin/cloudsaver opportunities --input demo-report.json
.venv/bin/cloudsaver explain demo:low_utilization_ec2:ap-northeast-2:i-demo-dev \
  --input demo-report.json
.venv/bin/cloudsaver report --input demo-report.json --format json
```

비용 데이터가 있다면 UTF-8 JSON 파일을 직접 준비해 조건부 월별 절감액을 계산할 수 있습니다. 다음 값은 **설명용 가상 금액**이며 AWS에서 조회한 가격이 아닙니다.

```json
{
  "schema_version": "1.0.0",
  "scenarios": [
    {
      "finding_id": "demo:low_utilization_ec2:ap-northeast-2:i-demo-dev",
      "region": "ap-northeast-2",
      "currency": "USD",
      "source": "AWS_PRICING",
      "as_of": "2026-10-01T00:00:00Z",
      "components": [
        {"kind": "compute", "baseline": "20.00", "optimized": "0.00"},
        {"kind": "ebs", "baseline": "5.00", "optimized": "5.00"},
        {"kind": "ipv4", "baseline": "3.00", "optimized": "3.00"}
      ]
    }
  ]
}
```

이를 `demo-costs.json`으로 저장한 뒤 실행합니다.

```bash
.venv/bin/cloudsaver report --input demo-report.json \
  --cost-input demo-costs.json --format json
```

이 예에서는 컴퓨트 비용만 제거하고 EBS·IPv4 비용은 남깁니다. 계산값이 보이더라도 `confidence: CONDITIONAL`이며 입력 출처의 진위나 실제 청구 절감은 검증하지 않습니다. `source`에 `AWS_PRICING`을 적는 것만으로 공식 가격을 조회한 것은 아닙니다. 필요한 필드, 정책별 비용 구성요소와 계산 제외 항목은 [비용 계산 문서](docs/cost-model.md)에 있습니다.

## HTML 대시보드와 실행 안전 검토

저장된 보고서를 브라우저에서 열 수 있는 **독립 HTML 파일**로 변환합니다. 웹 서버나 JavaScript는 필요하지 않습니다.

```bash
.venv/bin/cloudsaver dashboard --input demo-report.json --output dashboard.html
.venv/bin/cloudsaver dashboard --input demo-report.json \
  --cost-input demo-costs.json --output priced-dashboard.html
```

브라우저에서 로컬 `dashboard.html`을 열면 후보 수, 상태, 위험·비용 근거, 수집 실패를 볼 수 있습니다. HTML에도 보고서 내용이 포함되므로 공개 웹 서버에 올리지 마세요. [대시보드 안내](docs/dashboard.md)

탐지 건에 대한 가정한 작업과 차단 사유를 보려면 다음 명령을 사용합니다.

```bash
.venv/bin/cloudsaver action-review demo:low_utilization_ec2:ap-northeast-2:i-demo-dev \
  --input demo-report.json --format json
```

`action-review` 결과는 항상 `BLOCKED`, `execution_ready: false`입니다. 승인서나 AWS 변경 명령이 아닙니다. 실제 실행에 필요한 인증·대상 고정·재조회·감사 설계는 [Phase 8 보안 검토](docs/phase8-approval-review.md)에 있습니다.

## AWS 읽기 전용 스캔

AWS 계정 조회는 **선택 사항**입니다. 자격 증명, 사용 가능한 리전, 최소 권한 IAM 정책과 CloudWatch 호출 비용을 먼저 확인하세요. 현재 기능은 모의 응답으로 검증했으며 실제 계정에서는 아직 시험하지 않았습니다. [권한·API 목록](docs/aws-permissions.md)

```bash
.venv/bin/python -m pip install -e '.[aws]'
.venv/bin/cloudsaver scan --profile dev --regions ap-northeast-2 \
  --format json --output aws-report.json
```

`--profile`을 빼면 AWS SDK의 표준 자격 증명 체인을 사용합니다. `--regions`는 필수이며 `ap-northeast-2,us-east-1`처럼 쉼표로 여러 지역을 지정할 수 있습니다. 스캔은 EC2·EBS·Elastic IP와 실행 중인 EC2의 CloudWatch CPU 메트릭을 읽습니다. 일반 공인 IPv4 전체를 찾는 기능은 아닙니다. Cost Explorer·Pricing API도 호출하지 않습니다. 실제 계정에서는 API 사용량에 따라 비용이 발생할 수 있습니다.

```bash
.venv/bin/cloudsaver report --input aws-report.json
.venv/bin/cloudsaver opportunities --input aws-report.json --format json
```

자격 증명을 명령 인수, 저장소 파일 또는 공개 이슈에 넣지 마세요. 스캔 결과도 리소스 식별 정보를 포함할 수 있으므로 보관·공유 범위를 제한하세요.

## Cloud Custodian 정책 검증

Cloud Custodian 통합을 쓰려면 선택 의존성을 설치합니다. 다음 정책은 **검증 예제**이며 `actions`나 자동 실행 모드가 없습니다.

```bash
.venv/bin/python -m pip install -e '.[custodian]'
cat > policy.yml <<'YAML'
policies:
  - name: detached-ebs
    resource: aws.ebs
    filters:
      - type: value
        key: State
        value: available
YAML
.venv/bin/cloudsaver custodian validate --policy policy.yml --format json
```

`validate`는 로컬에서 정책 형식만 검사합니다. `evaluate`는 실제 AWS 읽기 API를 호출하므로 읽기 전용 IAM 역할과 그 역할을 맡을 권한이 필요합니다. 이 경로도 실제 계정에서는 아직 시험하지 않았습니다. 허용 필터, 차단 항목, 역할·세션 정책은 [Custodian 연동 문서](docs/custodian.md)를 참고하세요.

## Docker 실행

로컬 이미지에는 AWS와 Custodian 선택 의존성이 포함됩니다. 먼저 네트워크·자격 증명 없이 데모를 실행할 수 있습니다.

```bash
docker build --platform linux/arm64 -t cloudsaver:local .
docker run --rm --network none --read-only cloudsaver:local demo scan --format json
```

`linux/arm64`는 로컬에서 검증한 플랫폼입니다. x86-64에서는 빌드 플랫폼을 `linux/amd64`로 바꾸세요. 이미지는 일반 사용자로 실행하며 자격 증명을 포함하지 않습니다. AWS 프로필을 컨테이너에 **명시적으로** 읽기 전용 마운트하는 방법은 [설치 문서](docs/installation.md)에 있습니다. 레지스트리 이미지 설치나 Docker Compose 배포는 현재 제공하지 않습니다.

## 안전·제한 사항

- 기본 동작은 분석 및 읽기 전용입니다. `apply`, `delete`, `stop` 같은 AWS 변경 명령은 없습니다.
- 후보 탐지는 가설입니다. CPU가 낮거나 볼륨이 분리됐다는 이유만으로 중지·삭제 안전성을 알 수 없습니다.
- 비용 자료가 없으면 `UNKNOWN`이고, 사용자가 제공한 비용은 `CONDITIONAL`입니다. 실제 청구 금액이나 검증된 절감액으로 표현하지 않습니다.
- 실제 AWS 계정에서의 IAM/API 동작, macOS·Windows와 Docker amd64 동작은 아직 직접 검증하지 않았습니다. 로컬 Linux aarch64/Python 3.13.5와 Python 3.11 arm64 컨테이너에서 패키지·테스트 일부를 검증했습니다.
- 공개 태그·GitHub Release·PyPI 패키지·외부 이미지 배포는 아직 하지 않았습니다. 공개 전 점검 목록은 [릴리스 준비](docs/release-readiness.md)에 있습니다.

## 문제 해결

| 상황 | 확인할 내용 |
|---|---|
| `AWS support is not installed` | `.[aws]`를 설치했는지 확인하세요. 데모·저장 보고서 명령에는 필요하지 않습니다. |
| 자격 증명·프로필 오류 (`3`) | 로컬 AWS 프로필 또는 역할 설정을 확인하세요. 비밀 키를 명령·이슈에 붙이지 마세요. |
| `AccessDenied` 또는 부분 수집 (`4`/`6`) | [읽기 권한](docs/aws-permissions.md)과 보고서의 `collection_issues`, `scope.failed`를 확인하세요. |
| `Output file already exists` | 새 출력 파일명을 사용하세요. 기존 파일은 덮어쓰지 않습니다. |
| `Invalid report, cost input, or finding ID` | CloudSaver가 만든 JSON인지, `schema_version`과 비용 항목이 맞는지 확인하세요. |
| Custodian 미설치·정책 거부 | `.[custodian]` 설치 여부와 [허용 정책 범위](docs/custodian.md)를 확인하세요. |

## 개발·문서·라이선스

```bash
.venv/bin/python -m pip install -e '.[dev,custodian]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check src tests scripts
.venv/bin/mypy
```

아키텍처와 JSON 계약은 [설계 문서](docs/architecture.md)와 [CLI 계약](docs/cli-contract.md)에, 단계별 검증 상태는 [개발 계획](docs/development-plan.md)에 있습니다. 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md), 취약점 신고 방법은 [SECURITY.md](SECURITY.md), 변경 이력은 [CHANGELOG.md](CHANGELOG.md)를 참고하세요.

CloudSaver는 [Apache License 2.0](LICENSE)으로 배포하며 저작권 고지는 [NOTICE](NOTICE)에 있습니다. 종속성 라이선스 검토는 [별도 문서](docs/third-party-licenses.md)에 기록했습니다.
