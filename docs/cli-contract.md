# CLI 및 보고서 계약 — Phase 0 초안

Phase 1의 `--help`와 `demo scan`, Phase 2–3의 `scan` 수집 및 후보 탐지와 Phase 4의 저장된 보고서 명령이 구현되었다.

| 단계 | 명령 | 의미 |
|---|---|---|
| Phase 1 | `cloudsaver --help` | 설치된 명령과 사용법 표시 |
| Phase 1 | `cloudsaver demo scan [--format table|json] [--output PATH]` | 고정 fixture 분석. 기본 표, AWS/네트워크 사용 없음 |
| Phase 2–3 | `cloudsaver scan --regions REGION[,REGION...] [--profile NAME] [--format table|json] [--output PATH]` | 지정 리전 읽기 전용 수집. 리전 없으면 인수 오류. 가설적 후보 탐지 포함 |
| Phase 4 | `cloudsaver opportunities --input REPORT.json [--cost-input COSTS.json] [--format table|json]` | 기존 보고서의 후보 조회 |
| Phase 4 | `cloudsaver explain FINDING_ID --input REPORT.json [--cost-input COSTS.json] [--format table|json]` | 후보의 근거, 위험, 비용 설명 |
| Phase 4 | `cloudsaver report --input REPORT.json [--cost-input COSTS.json] [--format table|json]` | 수집 문제와 후보를 포함한 전체 보고서 |

`--output`은 명시된 파일에만 쓰며 기존 파일 덮어쓰기는 기본 거부한다. 표와 JSON은 표준 출력, 진단 메시지는 표준 오류로 보낸다. JSON 모드에서 표준 출력은 단일 유효 JSON 문서만 포함한다. 데모 결과에는 표 제목과 JSON `data_kind: "DEMO"` 및 `notice: "DEMO DATA"`를 표시한다. 도움말도 실제 지원하는 명령만 보여준다.

## JSON 구조 예시

필드명과 필수 여부는 Phase 1 스키마 테스트로 고정한다. 아래는 구조 설명용이며 결과 숫자를 암시하지 않는다.

```json
{
  "schema_version": "1.1.0",
  "data_kind": "DEMO",
  "notice": "DEMO DATA",
  "scanned_at": "2026-01-01T00:00:00Z",
  "scope": {"requested": ["demo"], "completed": ["demo"], "failed": []},
  "status": "COMPLETE",
  "findings": [
    {
      "finding_id": "demo:unattached_ebs:ap-northeast-2:vol-example",
      "policy_id": "unattached_ebs",
      "status": "CANDIDATE",
      "resource": {"type": "ebs_volume", "ref": "vol-example"},
      "evidence": [],
      "risk": {"level": "UNKNOWN", "reasons": [], "unknown_factors": ["data_retention"]},
      "savings": {"currency": "UNKNOWN", "period": "MONTH", "baseline": "UNKNOWN", "optimized": "UNKNOWN", "potential_savings": "UNKNOWN", "confidence": "UNKNOWN", "formula": "UNKNOWN", "assumptions": [], "excluded_costs": [], "data_sources": []}
    }
  ],
  "collection_issues": []
}
```

시각은 UTC ISO 8601로 직렬화한다. 같은 fixture와 고정 시각을 주면 결과와 정렬 순서가 같아야 한다. `UNKNOWN`은 가격 미확인의 명시적 상태이며 숫자 0과 다르다. 스캔 전체 실패 시 성공 형태의 빈 `findings`만 출력하지 않는다.

AWS `scan` JSON에는 `data_kind: "AWS"`, `analysis_status`, `resources`, `findings`, `collection_issues`, `scope`가 들어간다. 수집 전체 성공 시 `analysis_status: "COMPLETE"`, 일부 범위 실패 시 `"PARTIAL"`, 평가할 수집 범위가 없으면 `"NOT_EVALUATED"`다. `findings`에는 `CANDIDATE`, `EXCLUDED`, `INSUFFICIENT_DATA`가 구분되어 들어간다. 계정 ID·태그 값·공인 IP 주소는 출력하지 않는다. `resources[].metrics.status`는 `COMPLETE`, `MISSING`, `ERROR`, `NOT_REQUESTED` 중 하나다.

Phase 4의 저장 보고서 명령은 로컬 JSON을 읽으며 AWS를 호출하지 않는다. `opportunities`는 `CANDIDATE`만 표시하고, `explain`은 지정 finding의 근거·위험·계산 가정·출처를 표시한다. `report`는 수집 범위와 문제를 포함한 전체 보고서를 다시 출력한다. `--cost-input`은 명시적으로 제공한 월별 비용 항목에만 적용되며 결과는 `CONDITIONAL`이다. 금액이 없는 finding은 `UNKNOWN`을 유지한다. Phase 3의 `1.0.0` 보고서도 읽지만 새 출력 스키마는 `1.1.0`이다. 입력 형식과 계산 한계는 [비용 계산 문서](cost-model.md)에 있다.

## 종료 코드 제안

| 코드 | 의미 |
|---|---|
| `0` | 요청 범위 전체 성공. 후보 존재 자체는 오류가 아님 |
| `2` | 잘못된 인수/보고서 스키마/찾을 수 없는 finding ID |
| `3` | 자격 증명 없음 또는 인증 실패 |
| `4` | 권한 거부 |
| `5` | 리전, 통신, throttling 등으로 전체 수집 실패 |
| `6` | 일부 범위만 수집된 부분 성공. 보고서 `status: PARTIAL`과 문제 상세 포함 |
| `70` | 예상하지 못한 내부 오류. 민감 정보 없는 진단만 표시 |

재시도 가능한 throttling은 제한된 지수 백오프 후 `5` 또는 `6`으로 마친다. 출력 파일 쓰기 오류의 코드는 Phase 1에서 정한다. 종료 코드와 JSON 스키마의 호환성 변경은 버전 정책으로 관리한다.
