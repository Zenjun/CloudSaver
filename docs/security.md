# 보안 경계와 AWS 권한 — Phase 0

## 신뢰 경계

CloudSaver는 사용자의 장비에서 실행한다. 자격 증명은 AWS SDK의 표준 공급자 체인에서 얻고 저장하거나 출력하지 않는다. 데모 경로는 자격 증명 탐색, 인스턴스 메타데이터 접근, 네트워크 호출을 모두 피해야 한다. AWS 수집 경로도 리소스 변경 API를 포함하지 않는다. 프로필 이름과 리전만 CLI 인수로 받고 비밀 키 인수는 만들지 않는다.

보고서에는 비용, 태그, 계정/리소스 식별자 등 민감할 수 있는 자료가 있다. 기본 표·JSON·오류·로그에서 자격 증명, 전체 계정 ID, 태그 값, 공개 IP 주소를 숨긴다. 명시적 출력 파일은 사용자 계정만 읽도록 만들며 기존 파일을 조용히 덮어쓰지 않는다. 디버그 로그에도 SDK 응답 전체를 기록하지 않는다. 출력 파일의 보존과 삭제는 사용자 책임임을 설치 문서에 명시한다. 원격 서버 전송 기능은 초기 범위에 없다.

## 권한과 호출 범위

Phase 2 구현의 API 호출과 IAM 정책 예시는 [`aws-permissions.md`](aws-permissions.md)에 정리했다. 계정 식별에는 STS `GetCallerIdentity`를 사용한다. 읽기 전용 IAM 역할을 사용하고 삭제·중지·태그 수정 권한은 주지 않는다. `AccessDenied`는 그 범위의 수집 실패로 기록한다.

`DescribeAddresses`는 Elastic IP 범위다. 일반 공인 IPv4 전부를 확인하려면 별도의 IPAM 기능과 권한·비용 검토가 필요하다. AWS 문서도 Public IP Insights와 Elastic IP를 구분한다. [AWS Public IP Insights](https://docs.aws.amazon.com/vpc/latest/ipam/view-public-ip-insights.html)

Cost Explorer API는 호출별 요금이 발생할 수 있고, 리소스별 데이터는 별도 활성화와 세부 범위 제한이 있다. 기본 스캔에서 호출하지 않는다. 도입 시 호출 수 상한, 예상 비용, 사용자 명시 옵션, 페이지네이션 처리, 청구 지연을 문서화한다. 가격 데이터가 없으면 절감액은 `UNKNOWN`이다. [AWS Cost Explorer 가격](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/), [리소스별 세분화](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-granular-data.html)

## 위협과 통제

| 위험 | 초기 통제 | 검증 |
|---|---|---|
| 예상치 못한 AWS 변경 | SDK 사용 위치를 수집기에 한정, 쓰기 API 없는 IAM 역할 | 허용 API 호출 목록을 모킹 테스트로 검사 |
| 데모에서 자격 증명 또는 네트워크 접근 | 데모 조립에서 AWS 모듈 초기화 금지 | AWS 환경 변수 제거·소켓 차단 테스트 |
| 누락/권한 오류를 0 사용량으로 해석 | `CollectionIssue`와 Evidence 품질을 필수로 유지 | 부분 실패 및 결측 fixture 테스트 |
| 비밀 또는 계정 정보 노출 | 출력 직렬화 허용 목록, 마스킹, 원시 예외 제거 | 스냅샷 및 비밀 문자열 회귀 테스트 |
| 과장된 절감액 | 가격/사용량/가정이 없으면 `UNKNOWN`; EC2 컴퓨트와 잔존 EBS/IP 비용 분리 | 비용 계산·부재 사례 테스트 |
| 권한 높은 Custodian 정책 실행 | `actions`·`mode` 및 임의 필터 차단, 역할 전환과 읽기 전용 세션 정책 | 정책 거부·명령 인수·세션 정책 모의 테스트 |

AWS API, CloudWatch, Cost Explorer의 요청 요금과 할당량은 서비스·리전에 따라 재확인한다. 본 설계 과정에서 실제 AWS 호출은 하지 않았다. Raspberry Pi 전역 설정, 상시 서비스, Docker 실행도 하지 않는다.
