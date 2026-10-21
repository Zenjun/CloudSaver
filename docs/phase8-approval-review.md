# Phase 8 실행 승인 시스템 보안 검토

Phase 8의 현재 산출물은 **오프라인 안전 검토**다. `action-review`는 저장된 CloudSaver 보고서의 한 탐지 건에 대해 가정한 작업과 차단 사유를 출력한다. 결과는 항상 `BLOCKED`, `execution_ready: false`다. 승인자 인증, 승인 저장소, AWS 변경 API, 실행 어댑터는 구현하지 않았다.

```bash
cloudsaver action-review \
  demo:low_utilization_ec2:ap-northeast-2:i-demo-dev \
  --input demo-report.json --format json
```

`--output review.json`으로 새 파일에 저장할 수 있다. 이 파일은 소유자 전용 권한으로 생성되지만 **승인서나 변조 방지 감사 로그가 아니다**. 출력 내용을 바꾸거나 복사해도 실행 권한은 생기지 않는다.

## 현재 차단 조건

`action-review`는 저장 보고서 로더의 스키마 검사와 마스킹을 거친 입력만 받는다. 데모, 부분 수집·분석 실패, 후보 아님, 높거나 알 수 없는 위험, 확인되지 않은 의존성, 누락된 근거, 미지원 작업, EBS 삭제·Elastic IP 해제 가능성을 별도 코드로 표시한다. 어떤 입력에서도 다음 네 조건 때문에 실행은 차단된다.

| 차단 코드 | 현재 이유 |
|---|---|
| `TRUSTED_IDENTITY_UNAVAILABLE` | CLI에 검증된 사람/역할 인증이 없다. 문자열로 입력받은 이름은 승인자 증명이 될 수 없다. |
| `ACCOUNT_TARGET_UNBOUND` | 공개 보고서는 계정 ID를 마스킹하며, 특정 계정·리전·리소스를 변경 대상으로 안전하게 고정할 내부 기록이 없다. |
| `LIVE_STATE_NOT_RECHECKED` | 승인 직전과 실행 직전에 현재 AWS 상태·태그·연결 관계를 다시 확인하지 않는다. |
| `EXECUTION_DISABLED` | 변경 권한, 변경 API, 실행 명령을 제공하지 않는다. |

현재 후보 정책과 대응되는 작업명은 설명용이다. `STOP_EC2`, `DELETE_EBS`, `RELEASE_ELASTIC_IP`를 출력해도 해당 작업은 수행되지 않는다. 특히 EBS 삭제와 주소 해제는 첫 실행 범위에서 제외한다. EC2 중지도 작업 중단, 임시 데이터 손실, 공인 IP 변경 가능성이 있으므로 단순히 되돌릴 수 있는 작업으로 취급하면 안 된다. [AWS EC2 중지·시작 설명](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)

## 실제 실행 시스템의 필수 경계

| 단계 | 요구 조건 | 실패 시 동작 |
|---|---|---|
| 제안 생성 | 신뢰 가능한 계정·리전·리소스 ID·작업 종류와 보고서 해시를 묶고, 완전한 최신 수집과 위험 근거를 요구 | 제안 거부 |
| 인증·권한 | 요청자·승인자·실행자 역할을 검증된 인증 체계에서 가져오고 서로 분리. 요청마다 대상별 권한 재검사 | 접근 거부 |
| 승인 | 구체적 대상과 예상 영향, 만료 시각을 보여주고 서로 다른 승인자의 명시적 확인을 기록. 변경된 제안은 재승인 | 승인 무효 |
| 실행 직전 | 계정·리전·리소스 ID·상태·태그·ASG/로드밸런서 등 보호 조건을 재조회하고 승인된 스냅샷과 비교 | 실행 중단 |
| 중복·동시성 | 하나의 승인에 단일 idempotency key, 원자적 상태 전이, 재시도 범위 제한 | 중복 실행 거부 |
| 권한·감사 | 전용 최소 권한 역할과 좁은 세션 정책, 결과/실패/요청 ID를 독립 보관소에 기록. 감사 실패 시 실행 중단 | 실행 중단 |

허용 규칙이 없을 때는 거부하고 매 요청마다 권한을 검사해야 한다는 기준은 [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)에 따른다. AWS 권한은 작업에 필요한 최소 범위여야 하며, 여러 IAM 정책 유형의 평가 결과를 함께 고려해야 한다. [AWS 최소 권한 지침](https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started-reduce-permissions.html), [AWS 정책 평가](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html)

제안 상태는 `DRAFT → PENDING → APPROVED → PRECHECKED → EXECUTED`로 설계하고, 어느 단계에서나 `REJECTED`, `EXPIRED`, `BLOCKED`로 종료할 수 있어야 한다. 만료 후 승인, 승인자와 요청자가 같은 경우, 보호 태그·리소스 상태 변화, 대상 계정 변경, 중복 실행은 테스트에서 모두 거부해야 한다. `APPROVED`는 작업 완료를 뜻하지 않는다.

감사 이벤트에는 시각, 검증된 행위자, 제안 ID, 대상 참조, 작업, 결정, 차단 이유, 요청 상관 ID와 AWS 요청 ID를 포함한다. 자격 증명, 원시 태그, 전체 SDK 응답, 비용 세부 자료는 기록하지 않는다. 로컬 JSON 파일은 사용자가 수정할 수 있으므로 실제 실행 감사에는 독립 저장소와 무결성 검증이 필요하다. 이벤트 설계와 민감정보 배제는 [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)를 참고한다. AWS API 이력에는 CloudTrail을 사용할 수 있으나, 로그 파일 무결성 기능은 활성화와 별도의 **검증**이 필요하다. [AWS CloudTrail 무결성 검증](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-log-file-validation-intro.html)

## 구현 전 결정과 검증

1. 인증 공급자와 승인자 역할의 소유권, 실행 서비스를 둘 환경을 정한다. 로컬 CLI의 임의 사용자명은 신뢰하지 않는다.
2. 처음 허용할 계정·리전·비프로덕션 리소스 범위와 작업을 구체적으로 정한다. EBS 삭제·IP 해제 및 프로덕션 변경은 별도 설계·승인 대상으로 둔다.
3. 승인 유효기간, 재승인 조건, 감사 보존기간, 비상 정지 방법을 정한다.
4. 신뢰 가능한 대상 식별·최신 상태 재조회·IAM 역할 경계와 실패 시 동작을 Stub/격리 환경에서 시험한다.
5. 실제 AWS 변경 코드와 계정 검증은 그 작업 범위에 대한 별도 명시적 승인과 보안 검토 후 진행한다.
