# CloudSaver — 오픈소스 개발 계획서 & Codex 마스터 프롬프트

> **프로젝트 한 줄 소개**  
> AWS의 비용 낭비 후보를 탐지하고 **절감 가능액·운영 위험·판단 근거**를 함께 제시하는 **CLI-first, self-hosted 오픈소스 FinOps 도구**.  
> **기본 원칙:** *Analyze first, change nothing by default.*

- 문서 버전: `0.1.0` (초기 개발 기획)
- 작성일: 2026-10-19
- 상태: 설계 제안서 — 아직 구현·테스트가 완료된 제품이 아님
- 주요 진로 연계: Cloud Engineer / SRE / FinOps / Cloud Automation
- 배포 방향: Public GitHub repository, OSS license, CLI, Docker Compose, 선택적 웹 UI

---

# Part A. 제품 개발 계획서 (PRD + Technical Design)

## 1. 비전과 문제 정의

AWS에는 비용을 절약할 여지가 있는 리소스가 존재해도 이를 안전하게 제거·중지할 수 있는지 판단하기 어렵다. CPU가 낮은 EC2는 중요한 배치·대기 서버일 수 있고, 분리된 EBS 볼륨은 복구에 필요한 데이터일 수 있다. 비용 최적화를 **낭비 후보 발견 → 증거 확인 → 비용 시뮬레이션 → 위험 평가 → 사람의 결정 → 실행 후 검증**으로 연결하는 것이 CloudSaver의 핵심이다.

CloudSaver는 기존 모니터링 도구(Zabbix/Grafana), AWS 비용 콘솔, Cloud Custodian을 대체하는 서비스가 아니다. **비용 절감 의사결정을 설명 가능하고 재현 가능하게 만드는 독립 실행형 오픈소스**를 지향한다.

### 제품 목표

1. 개인 개발자가 자신이 통제하는 환경에 설치하고 자신의 AWS 계정을 조회한다.
2. 명확한 근거를 제공하는 최적화 후보와 비용 추정치를 확인한다.
3. CLI에서 JSON 출력을 제공하여 CI 및 자동화에 쉽게 연결한다.
4. 실수로 운영 리소스를 변경하는 것을 방지한다.
5. 후속 버전에서 Cloud Custodian 평가, 승인 및 제한된 실행을 제공한다.
6. 웹 대시보드는 핵심 엔진의 **선택적 인터페이스**이며 초기 출시를 가로막지 않는다.

### 비목표 (초기 버전)

- 클라우드 사업자의 완전한 청구 시스템 대체
- AWS 모든 리소스의 종합 지원
- AI가 독자적으로 프로덕션 리소스를 변경하거나 삭제하는 기능
- 실제 애플리케이션 의존성의 완전한 자동 발견
- Kubernetes, Azure, GCP 동시 지원
- 중앙 SaaS 및 사용자 AWS 자격 증명 수집

## 2. 대상 사용자와 대표 흐름

- **개인 개발자:** 사용하지 않는 실습용 EC2/EBS 비용을 파악하고 싶다.
- **소규모 운영팀:** 운영 중인 리소스의 절감 후보를 검토하되 서비스 장애는 피하고 싶다.
- **DevOps/SRE:** 정기 스캔 결과를 CI·운영 자동화와 연동하고 감사 가능한 결과를 얻고 싶다.

대표 흐름:

```text
사용자 설치 / 로컬 자격 증명 준비
       ↓
cloudsaver scan --profile dev --regions ap-northeast-2
       ↓
AWS 메타데이터 / CloudWatch / 허용된 비용 데이터 수집
       ↓
근거 기반 후보 탐지 및 위험도 평가
       ↓
예상 절감액 + 산식 + 제외 비용 + 신뢰도 표시
       ↓
CLI / JSON / (선택) 웹 대시보드에서 검토
       ↓
[후속 단계] 승인된 작업만 명시적으로 실행
       ↓
감사 기록과 실제 절감 효과 검증
```

## 3. 기존 도구와의 관계

| 도구 | 강점 | CloudSaver의 역할 |
|---|---|---|
| Cloud Custodian | 선언형 정책으로 리소스 필터링 및 조치 실행 | 정책 평가 및 후속 실행 어댑터로 활용 |
| AWS Cost Explorer | 청구 데이터 분석 | 비용 데이터의 출처 중 하나 |
| CloudWatch | 리소스 메트릭 | 유휴 상태 판단의 관찰 자료 |
| Zabbix / Grafana | 모니터링·시각화 | 중복 기능 최소화; 필요 시 연동 |
| CloudSaver | 위험·비용·근거·승인 의사결정 | 여러 데이터 소스를 결합하고 실행을 안전하게 통제 |

**차별화는 ‘새 필터 엔진’이 아니라 ‘판단의 품질’에 둔다.** 기존 도구에도 부분적으로 유사 기능이 있을 수 있다. 이를 독점적 기능이라고 주장하지 않는다.

## 4. 배포 및 사용자 경험 전략

### 4.1 CLI-first

초기 핵심 기능은 Python 기반 CLI로 개발하는 것을 우선 검토한다. Cloud Custodian과 같은 Python 생태계에서 정책 어댑터를 구현하기 편하고, 서버·컨테이너·CI 실행에 유리하다. 웹 UI가 필요한 단계에서 별도 API/프론트엔드를 도입한다. 기존 제안의 Next.js + NestJS 모노레포를 초기부터 강제하지 않는다.

목표 UX(아래 명령은 **아직 구현되지 않은 예정 인터페이스**):

```bash
cloudsaver --help
cloudsaver demo scan
cloudsaver scan --profile dev --regions ap-northeast-2
cloudsaver opportunities --format table
cloudsaver opportunities --format json > opportunities.json
cloudsaver explain <finding-id>
cloudsaver estimate <finding-id>
cloudsaver report --format json
```

`demo scan`은 AWS 자격 증명이나 실제 AWS 호출 없이 구동해야 한다. `scan`은 읽기 전용 API만 호출한다. 초기에는 `apply`, `delete`, `stop` 등의 쓰기 명령을 제공하지 않는다.

### 4.2 설치 방식

- **로컬 CLI:** 공식 지원 Python 버전에서 `pipx` 또는 `uv tool` 등으로 설치(패키지 배포 시점에 확정).
- **Docker:** Docker 이미지에서 CLI 실행. 호스트 AWS 프로필은 사용자의 명시적 마운트 또는 실행 역할로 연결; 자격 증명 이미지 내 포함 금지.
- **Docker Compose:** 초기에는 반복 스캔 및 선택적 API/웹 UI 배포를 위한 구성으로 제공. 단순 CLI 실행에 PostgreSQL이나 대시보드 설치를 강제하지 않는다.
- **추후:** GitHub Releases, 멀티 아키텍처 이미지(`linux/amd64`, `linux/arm64`), Helm Chart.

컨테이너는 **사용자 환경에서 실행**한다. 개발자의 중앙 서버에 자격 증명과 비용 데이터가 전송되지 않도록 설계한다.

### 4.3 공개 저장소 기본 구성

```text
cloudsaver/
├── src/cloudsaver/
│   ├── cli/                 # CLI 엔트리포인트
│   ├── providers/aws/       # AWS 수집 및 인증
│   ├── policies/            # 탐지 규칙
│   ├── analysis/            # 절감액 및 위험도 평가
│   ├── reports/             # 테이블/JSON 출력
│   ├── domain/              # 명확한 도메인 모델
│   └── storage/             # 필요할 때만 영속성 추상화
├── integrations/custodian/  # Cloud Custodian 어댑터(후속)
├── apps/web/                # 선택적 UI(후속)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── examples/
├── docs/
│   ├── architecture.md
│   ├── installation.md
│   ├── aws-permissions.md
│   ├── policies.md
│   ├── threat-model.md
│   └── roadmap.md
├── .github/workflows/
├── pyproject.toml
├── Dockerfile
├── compose.yaml            # 필요 단계에서 활성화
├── LICENSE
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
└── CHANGELOG.md
```

실제 초기 저장소에서는 빈 디렉터리와 미래 기능용 스켈레톤을 무분별하게 만들지 않는다.

## 5. 기술 스택 제안

| 영역 | 초기 권장 | 이유 / 대안 |
|---|---|---|
| 언어 | Python 3 (검증된 지원 버전) | AWS SDK, 정책 엔진과 연동 |
| CLI | Typer 또는 Click | 도움말, 파라미터 검증, 배포 용이 |
| AWS | boto3 / botocore | 공식 AWS API 접근 |
| 설정 및 모델 | Pydantic | 입력·출력 검증 |
| 저장 | 초기 파일 기반 JSON; 필요 시 SQLite | CLI 단독 구동을 가볍게 유지 |
| 정책 | Cloud Custodian (후속) | 필터·정책 실행 연동 |
| 테스트 | pytest, botocore Stubber 등 | 실제 유료 AWS 호출 없는 반복 테스트 |
| 품질 | Ruff, mypy 등 | 린트·타입 검증 |
| 배포 | Python package + Docker | 셀프호스팅 및 CI |
| 웹 UI (후속) | Next.js/React/TypeScript + shadcn/ui | 선택적 관리 화면 |
| API (후속) | FastAPI 또는 NestJS — ADR로 결정 | Python 엔진 재사용성/복잡도 비교 |
| DB (후속) | SQLite → 필요 시 PostgreSQL | 범위에 맞는 단계적 확장 |

**기술 선택은 고정 명령이 아니라 검증 대상이다.** 기존 저장소가 이미 있다면 우선 분석하고 대체 필요성을 문서화한다. 최신 안정 버전 및 호환성은 구현 시 공식 문서로 확인한다.

## 6. 기능 요구사항과 완료 조건

### F01. Demo Mode (P0)

- `cloudsaver demo scan`은 네트워크·자격 증명 없이 실행 가능해야 한다.
- 유휴 의심 개발 EC2, 보호된 프로덕션 EC2, 분리된 EBS, 미사용 IPv4, 판단 자료 부족 사례를 포함한다.
- 출력에 **DEMO DATA**를 명확히 표시한다.
- 데모 실행은 어떠한 AWS 쓰기 API도 호출하지 않는다.

### F02. Read-only AWS Discovery (P0)

- AWS SDK의 표준 자격 증명 체인 사용: Profile, IAM Role, 임시 자격 증명 등.
- EC2, EBS, Elastic IP / 공인 IPv4 중 API로 확인 가능한 범위를 우선 지원한다.
- 자격 증명 없음, AccessDenied, 잘못된 리전, throttling, 페이지네이션, 부분 수집 실패를 처리한다.
- 실패한 수집을 0건 발견으로 표시하지 않는다.
- 리소스 ID·리전·계정 식별 및 수집 시각을 유지한다(민감 정보는 출력 제어).

### F03. Opportunity Detection (P0)

- `unattached_ebs`, `low_utilization_ec2`, `potential_unused_public_ipv4`, `missing_cost_tag` 등 정책을 **가설적 탐지**로 제공한다.
- 탐지 조건, 관찰 기간, 사용 메트릭, 판단 근거를 각각 보관한다.
- 낮은 CPU만으로 중지 권고를 확정하지 않는다.
- 데이터가 부족하면 `INSUFFICIENT_DATA`를 남긴다.

### F04. Savings Estimation (P1)

- 각 제안에 현재 비용, 변경 후 비용, 예상 절감액, 통화, 기간, 산식, 데이터 출처, 신뢰도를 기록한다.
- 실제 가격 데이터 부재 시 금액은 `UNKNOWN`으로 반환한다. 임의의 숫자 금지.
- EC2 중지 시 컴퓨트 비용과 남는 EBS·공인 IPv4 등의 비용을 분리한다.
- SP/RI, 프리티어, 크레딧, 지역별 가격, 청구 반영 지연을 명시한다.
- Cost Explorer의 리소스별 비용 귀속 한계를 설명한다. 필요시 AWS Pricing 데이터와 사용 시간으로 추정하되 청구액으로 단정하지 않는다.

### F05. Explainable Risk Assessment (P1)

- 위험 등급: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `UNKNOWN`.
- 환경 태그, 중요도 태그, 보호 태그, 로드밸런서 등록, ASG 소속, 볼륨 데이터 위험, 관찰 자료의 완전성 등을 평가한다.
- `prod`, `critical`, `protected`는 정책에 따라 기본적으로 고위험/실행 제외 처리한다.
- 태그가 없다는 사실을 ‘개발 환경’으로 가정하지 않는다.
- 근거 부족은 `UNKNOWN`으로 분류하고, 이 등급을 자동 실행 가능 대상으로 취급하지 않는다.

### F06. Explain/Report (P1)

- 사람이 읽을 수 있는 표와 기계가 읽을 수 있는 JSON 출력.
- 같은 입력으로 같은 결과를 내는 결정적 규칙; 시간과 관찰 범위를 명시한다.
- 스키마 버전을 포함하고 오류를 표준 종료 코드로 구분한다.
- AWS 전체 계정 ID, 민감한 태그, 인증 정보가 기본 로그에 노출되지 않게 주의한다.

### F07. Cloud Custodian Integration (P2)

- Cloud Custodian의 정책 검증 및 **비파괴적 평가** 기능부터 연동한다.
- Cloud Custodian의 모든 정책이 기본적으로 안전한 것은 아니다. `actions` 존재 시 실행하지 않도록 검사하고, 코드 검증만 믿지 말고 최소 권한 IAM으로 이중 제한한다.
- CLI에서의 탐지 결과와 Custodian 평가 결과를 명시적으로 구분한다.
- 버전별 CLI/API 옵션을 구현 시 공식 문서와 실제 환경에서 검증한다.

### F08. 승인 기반 실행 (P3, 별도 승인 후)

- 초기 릴리스는 **읽기 전용**. 실제 클라우드 변경 엔진은 기본 비활성화.
- 후속 단계에 구현할 경우: 사용자 인증, 역할별 권한, 특정 계정/리전/리소스 허용 목록, 이중 확인, 변경 직전 재조회, idempotency key, 만료된 승인 차단, 감사 로그를 갖춘다.
- 프로덕션 변경 및 삭제는 기본 차단. 추가 설계 검토 없이는 구현 범위에 포함하지 않는다.
- 자동 롤백을 약속하지 않는다. EC2 stop/start 등은 상태·IP·작업 중단 위험이 있어 별도 검증이 필요하다.

### F09. 선택적 Web UI (P3)

- CLI/핵심 엔진과 UI를 분리한다.
- 비용·탐지 후보·위험 이유·실행 이력 조회. 쓰기 기능을 제공하는 경우 인증 및 권한 검증 필수.
- 기본 배포는 loopback 바인딩. 인터넷 공개를 기본값으로 하지 않는다.

## 7. 주요 도메인 모델 (초안)

```text
ResourceSnapshot
- provider, account_ref, region, resource_id, type, tags, observed_at

Evidence
- source, metric, period_start, period_end, value, unit, quality

Finding
- finding_id, resource_ref, policy_id, detected_at, evidences, status

SavingsEstimate
- finding_id, currency, period, baseline, optimized, potential_savings
- assumptions, excluded_costs, confidence, data_sources

RiskAssessment
- finding_id, level, reasons, unknown_factors, evaluated_at

ActionProposal [future]
- finding_id, action_type, target, preconditions, status

AuditEvent [future]
- event_id, actor_ref, request_id, timestamp, outcome
```

출력용 모델에는 `schema_version`을 반드시 포함한다. 경계(API/CLI/저장)에선 타입 및 필드 검증을 수행한다.

## 8. 최소 권한 및 운영 안전성

1. **Read-only by design:** 첫 버전은 AWS 조회 API만 사용한다. IAM에서도 변경 권한을 부여하지 않는다.
2. AWS 키를 소스·이미지·로그·샘플에 포함하지 않는다. 가능하면 역할/임시 자격 증명을 사용한다.
3. Cloud Custodian을 실행하는 계정에도 쓰기 권한을 부여하지 않는다(평가 단계).
4. 실제 비용이 발생하는 Cost Explorer API, Pricing 조회, 저장소·데이터베이스·클라우드 리소스 등에 대한 비용을 문서화한다.
5. AWS의 `AccessDenied`와 데이터 없음, 메트릭 결측과 0 사용량을 명확히 구분한다.
6. CI는 실제 AWS 계정에 기본 접근하지 않고 Stub/Fixture를 사용한다.
7. 친구 집 Raspberry Pi는 공유 장비이므로 자원 소비·설치·서비스 등록은 사전 동의를 받는다.
8. NightShift/Codex 원격 터미널 접근은 실제 명령 실행 권한이므로 Tailscale 접근 제어, 개별 사용자 권한, 비밀정보 관리가 필요하다.
9. 오픈소스 종속성 라이선스와 보안 업데이트를 확인한다.
10. 절감액은 `estimated`, `observed`, `verified` 등의 상태로 구분하고 과장된 수치를 표시하지 않는다.

## 9. 실행 환경 / Raspberry Pi 고려사항

- 개발 대상 후보: Debian 13 / aarch64 / Raspberry Pi / Tailscale / NightShift / Codex CLI.
- **CLI는 Mac/Linux(amd64/arm64) 지원을 목표**로 하되, 실제 테스트를 거치기 전에는 호환성을 확정하지 않는다.
- Python 기반 CLI 자체는 가볍게 유지한다. PostgreSQL, 다중 컨테이너, 웹 UI는 선택 설치한다.
- Raspberry Pi에서 실행 시 메모리/디스크/아키텍처 호환성을 확인하고 리소스 제한을 적용한다.
- 실제 개발 계정과 AWS 계정에 대한 권한은 소유자가 승인한 범위에서만 사용한다.

## 10. 단계별 로드맵 및 게이트

| 단계 | 목표 | 핵심 산출물 | 완료 게이트 |
|---|---|---|---|
| **Phase 0** | 기획·위험 분석 | PRD, 아키텍처 ADR, CLI 계약, 보안 모델, 실행 계획 | 사용자 설계 승인 |
| **Phase 1** | CLI 기초 + Demo | 패키지, `--help`, `demo scan`, fixture, JSON 출력, 테스트 | AWS 없이 데모 전부 성공 |
| **Phase 2** | AWS 읽기 전용 수집 | 프로필 연결, EC2/EBS/IPv4, 오류 처리 | 실제 조회는 명시적 허락 후 / 모킹 테스트 필수 |
| **Phase 3** | 낭비 탐지 | 최소 정책 3개, 근거·상태 | 유휴 의심·보호·데이터 부족 테스트 |
| **Phase 4** | 비용 추정 및 위험도 | 계산 엔진, `explain`, 등급화 | 계산 테스트·UNKNOWN 처리 검증 |
| **Phase 5** | Cloud Custodian 연동 | 정책 검사, 읽기 전용 평가 | 쓰기 정책·권한 차단 테스트 |
| **Phase 6** | 오픈소스 배포 | 문서, 라이선스, Docker, 릴리스, CI | 신규 환경 설치 재현 |
| **Phase 7** | 선택적 웹 UI | 읽기 전용 대시보드 | CLI와 같은 엔진 활용 |
| **Phase 8** | 승인 기반 자동화 | 승인 엔진, 감사 로그, 엄격한 가드레일 | 별도 보안 리뷰·사용자 승인 필수 |

**MVP 출시 기준:** Phase 1~4 + 최소 공개 배포 문서. Cloud Custodian 연동은 정식 기능 범위 확장 시 적용해도 된다.

## 11. 필수 테스트 시나리오

- 데모: AWS 자격 증명이 아예 없고 네트워크를 차단해도 결과 출력.
- 유휴 의심 EC2: CPU 낮지만 중요 태그가 있으면 자동 조치 대상이 아님.
- 결측 메트릭: 0으로 치환하지 않고 `INSUFFICIENT_DATA` 반환.
- EBS: 분리 상태라도 보존 태그가 있으면 위험 표시.
- 권한 부족: 적절한 에러 코드, 실패 수집건 구분.
- 리전별 가격/통화/청구 데이터 부재: 절감액 `UNKNOWN`, 산식 근거 유지.
- AWS API 페이지네이션, 스로틀링, 재시도/백오프.
- JSON 출력의 안정된 스키마와 CLI exit code 검증.
- Cloud Custodian 정책에 쓰기 액션이 포함되면 평가 실행 차단.
- (후속) 승인 만료, 중복 실행, 리소스 상태 변경, 인증 실패 시 무조건 차단.

## 12. 오픈소스 품질 및 커뮤니티

- `README.md`: 가치 제안, 5분 데모, CLI 사용법, 요구 환경, 비용/보안 경고, 로드맵.
- `LICENSE`: Apache-2.0 또는 MIT를 검토하되 실제 선택은 저작권자 결정; 종속성 라이선스 확인.
- `CONTRIBUTING.md`: 개발 환경, 테스트, PR 형식, 커밋/이슈 규칙.
- `SECURITY.md`: 취약점 비공개 신고, 지원 버전, 인증 정보 처리 방침.
- `CODE_OF_CONDUCT.md`: 기여자 행동 강령.
- `docs/architecture.md`: 도메인 경계, 의존 방향, 보안 경계.
- GitHub Actions: 린트/테스트/타입 검사, 보안 점검, 패키지 빌드.
- 공개 저장소에 데모 AWS 자격 증명이나 실제 사용자의 리소스 데이터가 포함되지 않도록 검사.
- 공개 릴리스에는 라이선스·서드파티 고지·지원 OS/아키텍처·변경 이력 포함.

## 13. 구현 우선순위 결론

**첫 목표는 “AWS 계정 없이도 실행되고, 결과에 판단 근거가 담긴 CLI”다.** 일단 실제 사용자에게 설치 경험을 제공할 수 있어야 한다. 웹 대시보드, AI 요약, 고급 의존성 그래프, 자동 중지는 핵심 엔진 검증 이후에 도입한다.

---

# Part B. Codex 마스터 프롬프트 (아래 전체 블록을 복사해 전달)

> **사용법:** 아래 코드블록 전체를 Codex 대화에 전달한다. 이 문서 전체를 Codex가 읽을 수 있는 저장소에 두었다면 파일을 읽도록 지시해도 된다. **이번 첫 실행은 Phase 0만 수행**한다.

````text
너는 Senior Cloud Engineer, SRE, FinOps Architect, Python OSS Maintainer이자 보안 중심 소프트웨어 아키텍트다.

우리는 CloudSaver라는 설치형 오픈소스 프로젝트를 개발한다.
사용자는 클라우드/SRE를 공부하는 초급 개발자이므로 설명과 작업 보고는 항상 한국어로, 이해하기 쉬운 용어로 작성한다.

[제품 정의]
CloudSaver는 사용자가 자기 환경에 직접 설치하는 CLI-first, self-hosted AWS FinOps 도구다.
핵심은 AWS 비용 절감 후보를 찾는 것에서 끝나지 않고,
예상 절감액, 계산 근거, 운영 위험, 데이터의 불확실성을 함께 설명하여
안전한 의사결정을 돕는 것이다.
Cloud Custodian을 대체하지 않고 정책 평가·연동에 활용한다.
웹 대시보드는 핵심 CLI가 작동한 뒤 선택적으로 제공한다.
중앙 SaaS, 사용자 AWS 키 업로드, AI에 의한 자동 리소스 삭제는 초기 범위가 아니다.

[핵심 원칙]
1. Analyze first, change nothing by default.
2. 초기 버전은 AWS 읽기 전용이며, 실제 AWS 생성·수정·삭제·중지 호출을 구현하거나 실행하지 않는다.
3. 사용자의 명시적 허락 없이 공유 Raspberry Pi의 전역 설정, 서비스, 네트워크, 기존 파일을 수정하지 않는다.
4. 기존 저장소의 변경사항과 사용자 작업 내용을 보존한다. 관련 없는 파일을 수정하지 않는다.
5. AWS 자격 증명/계정 식별 정보/비용 세부 정보는 로그·커밋에 포함하지 않는다.
6. 모르는 사항은 임의 추정하지 말고 검증하거나 미확인이라고 표기한다.
7. 데이터 부족은 사용량 0이나 저위험으로 처리하지 않는다.
8. 금액은 실제 조회한 가격·요금 데이터 및 계산 가정이 있을 때만 계산한다. 없으면 UNKNOWN.
9. 테스트를 실행하지 않았다면 통과했다고 보고하지 않는다.
10. 설계 승인과 실제 AWS 변경 승인을 분리한다.

[프로젝트 형태]
- GitHub Public Repo를 목표로 하는 오픈소스
- CLI-first: `cloudsaver demo scan`, `cloudsaver scan`, `cloudsaver opportunities`, `cloudsaver explain`, `cloudsaver report`
- 읽기 전용 AWS API 수집 (EC2, EBS, Public IPv4), CloudWatch, 선택적 Cost Explorer
- 정책 기반 낭비 의심 탐지
- 예상 절감액·위험도·근거·신뢰도 설명
- JSON 출력 및 CI 친화적 exit code
- Cloud Custodian 정책 평가 통합은 후속 단계
- 웹 UI/승인 기반 실제 실행은 더 후속 단계
- 배포: Python 패키지, Docker, 추후 Docker Compose 및 Helm
- 개발·배포 시 linux/amd64 및 linux/arm64 호환성 검토

[설계 우선 제안]
Python CLI(예: Typer), boto3, 명시적인 도메인 모델(Pydantic 등), pytest 기반으로
독립 실행 가능한 코어 엔진을 설계한다.
처음부터 Next.js/NestJS/PostgreSQL/Redis 등을 모두 설치하지 않는다.
영속성 요구가 분명해질 때 SQLite 또는 PostgreSQL 도입을 검토한다.
Cloud Custodian은 정책 엔진이지 안전을 자동 보장하는 도구가 아니므로
비파괴적 평가와 읽기 전용 IAM 통제를 모두 적용한다.
버전·라이브러리·라이선스는 공식 문서 확인 후 확정한다.

[초기 기능 범위]
P0: Demo Mode, AWS 읽기 전용 리소스 발견, 기본 후보 탐지, 표/JSON 출력
P1: 근거 기반 절감액 추정, 운영 위험도, 상세 설명, 테스트 강화
P2: Cloud Custodian 비파괴적 정책 평가
P3: 선택적 웹 UI 및 승인 워크플로 (실제 AWS 변경은 별도 승인 없이는 금지)

[위험도 판단]
LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN을 지원할 계획이다.
Production/critical/protected 태그는 안전 우선으로 처리한다.
태그가 없다고 개발용으로 단정하지 않는다.
네트워크 및 애플리케이션 의존성을 AWS API만으로 완전히 알 수 없음을 명시한다.
근거가 부족하면 UNKNOWN 및 추가 검토를 권고한다.

[절감액 계산]
EC2 중지 시 컴퓨팅 시간 절감과 계속 발생하는 EBS 등 비용을 구분한다.
Savings Plans, Reserved Instances, 프리티어, 크레딧, 청구 반영 지연,
Cost Explorer 리소스 귀속 제한 등을 문서화한다.
추정 절감액을 실제 절감액으로 표현하지 않는다.

[문서 및 오픈소스 준비]
README, PRD, ARCHITECTURE, DEVELOPMENT_PLAN, SECURITY,
CONTRIBUTING, CODE_OF_CONDUCT, LICENSE 후보, 테스트 전략,
실행/설치 가이드를 준비한다.
라이선스 파일은 저작권자 승인 없이 임의 확정하지 않는다.
오픈소스 기여자 친화적 모듈 구조와 재현 가능한 개발 환경을 우선한다.

[개발 단계]
Phase 0: 기획, ADR, CLI 계약, 보안 경계, 모듈 설계
Phase 1: Python CLI 기반 및 Demo Mode
Phase 2: AWS 읽기 전용 수집
Phase 3: 비용 최적화 후보 탐지
Phase 4: 비용 추정 및 위험도 평가
Phase 5: Cloud Custodian 연동
Phase 6: 패키징, Docker, 문서, CI, 오픈소스 공개 준비
Phase 7: 선택적 웹 대시보드
Phase 8: 별도 승인 하에 안전한 실행 승인 시스템 검토

[개발 시 행동 규칙]
- 명령 실행 전 현재 작업 경로, Git 상태, 기존 파일 및 환경을 확인한다.
- 사용자 지정 프로젝트 위치를 확인하기 전 기존 다른 저장소에 파일을 작성하지 않는다.
- 설계 작업과 코드 구현 단계를 명확히 구분한다.
- 꼭 필요한 것만 변경하고 영향을 설명한다.
- 외부 비용을 발생시킬 수 있는 AWS API/리소스 생성/배포는 승인 후 진행한다.
- 테스트는 fixture/mock 중심으로 만들고 CI에서 실 AWS 계정을 요구하지 않는다.
- 폴더와 기능 구조는 과도하게 세분화하지 않는다.
- 미완료 항목은 미완료로 표시한다.
- 비밀정보 유출 위험이나 보안 우회가 발견되면 즉시 보고하고 중단한다.
- 내부 추론 전체를 설명할 필요는 없지만, 선택지와 근거/트레이드오프는 간결히 문서화한다.

[이번 요청: 반드시 Phase 0만]
1. 현재 디렉터리와 Git/프로젝트 상태를 읽기 전용으로 확인한다.
2. 기존 CloudSaver 관련 문서가 있으면 먼저 읽고 충돌사항을 보고한다.
3. 이 계획의 문제점과 기술적 불확실성(비용 API 요금, AWS 권한, ARM64,
   Cloud Custodian 통합, CLI 패키징, 데이터 보존, OSS 라이선스)을 정리한다.
4. CLI-first 아키텍처, 모듈 경계, 데이터 모델, CLI 명령 계약, 리스크 모델,
   오류/종료 코드, 테스트·보안 전략을 설계한다.
5. 최소 MVP의 완료 기준과 Phase 1 작업을 명확히 정의한다.
6. 사용자가 허락한 범위에서만 docs 문서를 작성한다. 프로젝트 위치가 확정되지
   않았다면 파일 생성 전 위치를 한 번 질문한다.
7. Phase 1 코드 생성, 패키지 설치, Docker 서비스 실행, AWS API 호출,
   Git push, 친구 서버의 전역 설정 변경은 이번 요청에서 절대 수행하지 않는다.
8. 한국어로 산출물 목록, 핵심 설계 결정, 확인 필요한 질문, Phase 1 제안을 보고한다.

먼저 저장소 상태를 확인하고 Phase 0 개발 계획부터 진행하라.
````

---

# Part C. Codex에 단계별로 보내는 후속 프롬프트

## Phase 1 시작 (Phase 0 승인 후)

```text
CloudSaver Phase 0 산출물을 먼저 읽고, 확정된 설계에 따라 Phase 1만 구현해 줘.
목표는 AWS 자격 증명 없이 실행되는 Python CLI와 Demo Mode다.
`cloudsaver --help`, `cloudsaver demo scan`, JSON 결과 출력, fixture,
단위 테스트, 린트/타입 검사와 README의 로컬 실행 가이드를 구현해.
기존 코드를 먼저 확인하고 관련 파일만 변경해.
실제 AWS API 호출, AWS 쓰기 작업, Docker 상시 실행, Git push는 하지 마.
작업 후 실행한 명령, 테스트 결과, 미완료 사항을 한국어로 알려줘.
```

## Phase 2 시작 (Phase 1 검증 후)

```text
CloudSaver Phase 1 코드를 검토하고 Phase 2인 AWS 읽기 전용 수집만 구현해 줘.
EC2/EBS/Public IPv4를 대상으로 자격 증명 체인, 리전, 페이지네이션,
AccessDenied, 부분 실패, throttling, 타임아웃을 처리해.
테스트는 AWS Stub/Mock로 먼저 진행하고 실제 AWS 호출은 승인 전 하지 마.
메트릭 결측·수집 실패를 유휴 상태로 판단하지 않도록 보장해.
변경된 파일, 새 IAM 읽기 권한 요구사항, 테스트 결과를 정리해.
```

## 공개 배포 준비 (Phase 6 승인 후)

```text
현재 CloudSaver 구현과 테스트 상태를 읽기 전용으로 먼저 검토해.
실제로 제공하는 기능만 README와 릴리스 노트에 기재하고,
Docker 및 Python 패키지 설치 방법을 재현 가능한 수준으로 문서화해.
라이선스 호환성, 비밀정보 검사, 보안 정책, linux/amd64와 linux/arm64
빌드/테스트 결과를 확인해.
GitHub 공개, 태그, 릴리스 게시, 외부 레지스트리 Push는 최종 승인 후 진행해.
```

---

# Part D. 시작 전 체크리스트

- [ ] CloudSaver 프로젝트 전용 **새 디렉터리/저장소** 선택 (기존 캡스톤 저장소와 분리)
- [ ] Public GitHub 공개 여부와 라이선스 확정은 코드/종속성 검토 후 결정
- [ ] 친구의 Raspberry Pi에서 개발하는 경우 소유자 허락 및 사용 가능한 RAM/디스크 확인
- [ ] AWS 계정 연동 전 개인 실습 계정, 최소 권한 IAM, 예상 API 호출비 확인
- [ ] Phase 0 문서 검토 및 승인
- [ ] AWS 없이 Demo Mode 구현 및 자동 테스트
- [ ] 이후 실제 AWS **읽기 전용** 검증

**성공 지표(향후 실측):** Demo Mode 설치 성공률, 스캔 시간, 정책 탐지 정확도(오탐·미탐), 금액 추정 오차, UNKNOWN 처리 적합성, 공개 저장소의 기여/재현성. 절감액은 **추정치**와 **실측 청구 비용 절감**을 구분하여 보고한다.

---

*이 문서는 CloudSaver 개발의 기준안이며, 구현 전에는 최신 AWS 요금·API·IAM·Cloud Custodian 공식 문서와 라이선스를 확인해야 한다.*
