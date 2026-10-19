# 아키텍처 — Phase 0 설계안

상태: Phase 0 설계안. Phase 1 데모 CLI가 구현되었고, 후속 단계의 구조는 제안이다. 상위 요구사항은 [`agent.md`](../agent.md)에 있다.

## 결정 기록

| ID | 결정 | 이유와 범위 |
|---|---|---|
| ADR-001 | Python 패키지의 CLI를 먼저 만든다 | 단독 설치와 CI 실행을 우선한다. 최소 Python 버전과 Typer/Click 선택은 Phase 1 호환성 시험 후 고정한다. |
| ADR-002 | 도메인/탐지/평가 코어는 AWS SDK 및 CLI 프레임워크를 직접 참조하지 않는다 | 같은 fixture로 데모와 AWS 결과를 평가하고, 나중에 UI가 코어를 재사용할 수 있게 한다. |
| ADR-003 | Demo 입력과 AWS 수집 결과를 같은 정규화 모델로 변환한다 | 데모가 실제 판단 규칙을 검증하도록 한다. 데모 경로에서 AWS 클라이언트나 자격 증명 탐색은 초기화하지 않는다. |
| ADR-004 | 스캔은 메모리에서 수행하고 저장은 명시적 출력 파일로 시작한다 | 데이터 보관과 로컬 권한 문제를 줄인다. `opportunities`/`explain`은 저장된 보고서 입력을 받는다. |
| ADR-005 | 기본 AWS 경로는 읽기 전용, Cost Explorer/Pricing 조회는 별도 명시 옵션으로 둔다 | 비용이 발생할 수 있는 API를 조용히 호출하지 않는다. 가격 자료가 없으면 금액은 `UNKNOWN`이다. |
| ADR-006 | Cloud Custodian은 후속 평가 어댑터로 분리한다 | 정책의 `actions`와 권한 위험을 독립적으로 검증한 뒤 도입한다. |

## 모듈 경계와 데이터 흐름

```text
CLI 인수/출력
   ↓
스캔 조정자 ── Demo fixture 또는 AWS 읽기 전용 수집기
   ↓                ↓
정규화 ResourceSnapshot + Evidence + CollectionIssue
   ↓
정책 탐지 → 위험 평가 → 비용 추정 → Report
   ↓
표 / JSON 렌더러, 명시적 파일 저장
```

예정 디렉터리는 `src/cloudsaver/{cli,domain,providers/aws,policies,analysis,reports}`와 `tests/{unit,fixtures}`다. 실제 코드가 필요할 때만 생성한다. `storage`는 파일 기반 보고서 요구가 구체화될 때 추가한다. 의존 방향은 `cli`와 `providers/aws`에서 `domain`을 향하고, 도메인 코드는 외부 라이브러리의 응답 객체를 받아들이지 않는다.

## 데이터 모델 초안

- `ResourceSnapshot`: 공급자, 계정 참조(출력 시 마스킹), 리전, 리소스 ID, 유형, 허용된 태그, 수집 시각, 수집 완전성.
- `Evidence`: 출처, 메트릭/관찰명, 시작·끝 시각, 값 또는 결측, 단위, 품질(`COMPLETE`, `PARTIAL`, `MISSING`, `ERROR`). 결측과 0을 구별한다.
- `CollectionIssue`: 서비스·리전·작업, 범주, 재시도 가능 여부, 공개 가능한 메시지. 실패한 범위는 발견 0건으로 기록하지 않는다.
- `Finding`: 결정적 ID, 정책 ID·버전, 리소스 참조, 탐지 시각, 상태(`CANDIDATE`, `INSUFFICIENT_DATA`, `EXCLUDED`), 근거와 관찰 범위.
- `RiskAssessment`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `UNKNOWN`, 이유, 알 수 없는 요소, 평가 시각. 위험도는 데이터의 충분성과 별개다.
- `SavingsEstimate`: 통화·기간, 기준 비용·변경 후 비용·절감 가능액(각각 숫자 또는 `UNKNOWN`), 산식, 출처, 가정, 제외 비용, 신뢰도. 숫자는 입력 가격과 사용량 및 적용 범위가 검증된 경우에만 기록한다.
- `Report`: 스키마 버전, 데이터 종류(`DEMO`/`AWS`), 스캔 시각, 요청/완료/실패 범위, 후보, 수집 문제, 전체 상태.

`Finding` ID는 정책 버전과 리소스 참조를 정규화한 값에서 만든다. 시각이나 출력 순서가 바뀌어도 같은 후보를 식별할 수 있어야 한다. 보고서 직렬화에서 태그 값, 전체 계정 ID, 공개 IP 주소 등은 기본적으로 숨긴다. 내부 식별과 외부 표시를 분리한다.

## 탐지 및 위험의 최소 규칙

1. `unattached_ebs`: 분리 상태는 후보 근거다. 데이터 보존 태그 또는 스냅샷/업무 맥락의 결측은 삭제 안전성으로 해석하지 않는다.
2. `low_utilization_ec2`: 지정 관찰 기간의 CPU 자료와 샘플 수를 요구한다. 낮은 CPU만으로 중지 권고를 확정하지 않으며 네트워크/디스크·ASG·로드밸런서 맥락을 표시한다.
3. `potential_unused_public_ipv4`: 먼저 연결되지 않은 Elastic IP를 대상으로 한다. 일반 공인 IPv4 전체를 `DescribeAddresses` 결과로 대표하지 않는다.
4. `missing_cost_tag`: 조직이 정한 필수 태그 설정이 있을 때만 후보를 낸다. 태그 없음은 개발 환경을 뜻하지 않는다.

`prod`/`critical`/`protected` 표시는 고위험 또는 제외 근거다. 보호 신호가 없다는 것만으로 `LOW`를 주지 않는다. 평가에 필요한 사실이 부족하면 `UNKNOWN`을 반환한다. 탐지 상태, 운영 위험, 비용 확신도는 각각 독립적으로 표시한다.

## 보류한 설계

API/웹 UI, 데이터베이스, 승인/실행 엔진은 범위 밖이다. 정책 임계값과 최소 관찰 일수는 데모 fixture 및 오탐 시험을 바탕으로 Phase 3에 고정한다. AWS 계정 전체 검색 범위와 멀티 계정 방식도 실제 권한 설계 후 결정한다.
