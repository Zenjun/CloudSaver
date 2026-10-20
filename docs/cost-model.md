# Phase 4 비용 계산과 위험 평가

기본 스캔에는 가격·청구 조회가 없다. 모든 절감액은 `UNKNOWN`이다. `cloudsaver report`, `explain`, `opportunities`는 저장된 CloudSaver JSON 보고서를 로컬에서 읽으며 AWS에 접속하지 않는다. `--cost-input`을 명시하면 사용자가 제공한 **월별 비용 항목**으로 가상 시나리오를 계산한다. 출처의 진위, 실제 요금 적용 여부, 청구 절감은 검증하지 않으므로 `confidence: CONDITIONAL`이다. 이 계산은 AWS 변경 명령이 아니다.

## 비용 입력

입력 파일은 UTF-8 JSON이다. 최상위에 `schema_version: "1.0.0"`과 `scenarios` 배열이 필요하다. 각 시나리오에는 저장된 보고서의 `finding_id`, 해당 finding과 일치하는 AWS `region`, 3자리 대문자 `currency`, `source` (`AWS_PRICING` 또는 `AWS_COST_EXPORT`), 시간대가 포함된 `as_of`, `components`가 필요하다. 각 항목은 `kind`, `baseline`, `optimized`를 가진다. 금액은 0 이상이고 소수점 둘째 자리까지의 **문자열**이어야 한다. 출처 표기는 사용자가 옮긴 자료의 주장일 뿐 CloudSaver가 원본을 조회하거나 검증했다는 뜻이 아니다.

예를 들어 데모 EC2 finding에 적용할 파일의 구조는 다음과 같다. `REPLACE_...` 값은 실제 월별 비용 문자열(예: 소수점 둘째 자리)로 바꿔야 하며 이 예시는 그대로 실행할 수 없다.

```json
{
  "schema_version": "1.0.0",
  "scenarios": [{
    "finding_id": "demo:low_utilization_ec2:ap-northeast-2:i-demo-dev",
    "region": "ap-northeast-2",
    "currency": "USD",
    "source": "AWS_PRICING",
    "as_of": "2026-10-01T00:00:00Z",
    "components": [
      {"kind": "compute", "baseline": "REPLACE_COMPUTE", "optimized": "0.00"},
      {"kind": "ebs", "baseline": "REPLACE_EBS", "optimized": "REPLACE_EBS"},
      {"kind": "ipv4", "baseline": "REPLACE_IPV4", "optimized": "REPLACE_IPV4"}
    ]
  }]
}
```

| 정책 | 필요한 `kind` | 계산 가정 |
|---|---|---|
| `low_utilization_ec2` | `compute`, `ebs`, `ipv4` | 컴퓨트 변경 후 비용은 0, EBS와 IPv4 비용은 그대로 유지 |
| `unattached_ebs` | `ebs` | 볼륨 제거 시 해당 볼륨 비용 0; 데이터 보존 검토 필수 |
| `potential_unused_public_ipv4` | `ipv4` | 주소 해제 시 해당 주소 비용 0; 향후 사용 검토 필수 |

세 구성요소는 중복하거나 빠질 수 없다. 해당 비용이 없다면 명시적으로 `"0.00"`을 넣어야 한다. 계산식은 `sum(components.baseline) - sum(components.optimized)`이며 월 기준이다. EC2 비용에서 EBS·IPv4는 **잔존 비용**으로 계산해 변경 후 총비용에 남긴다. 세금, 데이터 전송, 스냅샷과 입력되지 않은 항목은 제외한다. Savings Plans/RI, 프리티어, 크레딧, 지역별 가격, 청구 반영 지연, Cost Explorer의 리소스별 귀속 한계 때문에 실제 청구 절감과 다를 수 있다.

AWS 문서도 EC2 비용 견적에서 [리전·결제 방식·EBS·데이터 전송·Elastic IP를 별도 입력](https://docs.aws.amazon.com/pricing-calculator/latest/userguide/ec2-estimates.html)으로 다루며, [Cost Explorer 세분화는 기능별 범위와 활성화 조건](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-granular-data.html)이 있다. 따라서 CloudSaver는 사용자가 옮긴 월별 금액을 청구 원장이나 검증된 리소스별 비용으로 표현하지 않는다.

`EXCLUDED` 또는 `INSUFFICIENT_DATA` finding에는 비용 시나리오를 적용할 수 없다. 비용 입력이 없거나 일부 finding에 입력되지 않았으면 해당 금액은 계속 `UNKNOWN`이다. 저장된 Phase 3 보고서(`schema_version: 1.0.0`)도 읽을 수 있으며, Phase 4 보고서는 `1.1.0`으로 출력된다.

## 위험 평가

`protected`·`critical` 참값은 `CRITICAL`, `environment=prod|production`, `importance=high|critical`, EC2의 ASG 소속 태그, EBS 보존 태그는 `HIGH`로 평가하고 후보에서 제외한다. 태그 키·값은 대소문자와 앞뒤 공백을 정규화하며, 서로 충돌하는 태그가 있으면 보호 신호가 우선한다. EC2의 로드밸런서 등록 여부와 네트워크·디스크 사용량은 현재 수집하지 않아 `unknown_factors`에 남긴다. EBS의 데이터 보존 목적도 미확인이다. 관찰 자료가 부족하면 보호 신호가 없는 한 `UNKNOWN`이며, 태그가 없다는 사실만으로 개발 환경이나 저위험이라고 판단하지 않는다. `LOW`는 현재 자동 부여하지 않는다.
