# Phase 2 AWS 읽기 권한과 호출 범위

Phase 5 Custodian 평가는 별도 IAM 역할을 사용한다. 해당 역할과 세션 정책의 API 허용 목록은 [Custodian 연동 문서](custodian.md)에 있다. 아래 목록은 `cloudsaver scan` 전용이다.

`cloudsaver scan`의 구현은 다음 API만 호출한다. 이 문서는 **모킹 테스트 기준**이며 실제 계정 조회는 아직 검증하지 않았다.

| API | 용도 | 호출 방식 |
|---|---|---|
| `sts:GetCallerIdentity` | 현재 계정 식별. 출력에는 전체 계정 ID를 숨김 | 스캔당 1회 |
| `ec2:DescribeInstances` | 인스턴스 상태·태그 | 리전별 페이지네이션 |
| `ec2:DescribeVolumes` | EBS 상태·태그 | 리전별 페이지네이션 |
| `ec2:DescribeAddresses` | Elastic IP 연결 상태 | 리전별 1회. 일반 공인 IPv4 전체를 포괄하지 않음 |
| `cloudwatch:GetMetricData` | 실행 중인 EC2의 최근 14일 CPU 관찰값 | 실행 중인 인스턴스당 1개 메트릭, 결과 페이지네이션 |

정책 예시(계정 관리자가 리전 및 조직 정책에 맞게 검토해야 함):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudSaverReadOnlyDiscovery",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeAddresses",
        "cloudwatch:GetMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

`GetCallerIdentity`에는 별도 허용 권한이 필요하지 않다. [AWS STS 문서](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html) EC2와 CloudWatch 작업의 권한 이름 및 분류는 [EC2 서비스 승인 참조](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ec2.html)와 [CloudWatch 서비스 승인 참조](https://docs.aws.amazon.com/service-authorization/latest/reference/list_cloudwatch.html)에 근거한다. 이 정책은 쓰기 작업을 허용하지 않는다.

SDK 표준 자격 증명 체인을 사용하며 `--profile`을 지정하면 해당 프로필을 사용한다. 리전 인수를 반드시 지정한다. 서비스별 수집이 실패하면 해당 범위를 실패로 기록하고, 실패한 페이지 앞의 부분 데이터도 그 범위의 성공 결과로 내보내지 않는다. CloudWatch 값이 없으면 `MISSING`, API 오류면 `ERROR`이며 둘 다 CPU 0으로 바꾸지 않는다.

Botocore 표준 재시도 설정은 총 3회 시도(초기 요청 포함), 연결 타임아웃 5초, 읽기 타임아웃 15초다. 스로틀링이 남으면 문제 범주 `THROTTLED`와 부분/전체 실패 종료 코드를 반환한다. [AWS SDK 재시도 문서](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html)

CloudWatch `GetMetricData`는 사용량에 따른 비용이 발생할 수 있다. 계정 규모와 호출 빈도를 확인한 뒤 실행해야 한다. [AWS CloudWatch 비용 안내](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_billing.html) Cost Explorer·Pricing API는 이 단계에서 호출하지 않는다.
