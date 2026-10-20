# Phase 3 탐지 정책

이 규칙은 비용 절감 **검토 후보**만 만든다. AWS 변경 작업은 없으며, 가격·청구 자료가 없어 절감액은 항상 `UNKNOWN`이다. 탐지 상태와 운영 위험은 별도 필드다. 실제 AWS 계정 조회는 아직 검증하지 않았다.

| 정책 | 대상 및 조건 | 근거 | 보류·제외 |
|---|---|---|---|
| `unattached_ebs` | `available` EBS 볼륨 | `DescribeVolumes`의 상태 | 보존 목적은 미확인. 보호·보존 태그가 있으면 `EXCLUDED` |
| `low_utilization_ec2` | 실행 중 EC2, 14일 관찰 구간, CPU 일별 평균 샘플 7개 이상, 샘플 평균 5% 이하 | CloudWatch `CPUUtilization.average`, 샘플 수, 기간 | 메트릭 결측·오류·불충분한 샘플/기간은 `INSUFFICIENT_DATA`. 보호 태그는 `EXCLUDED` |
| `potential_unused_public_ipv4` | 연결되지 않은 Elastic IP | `DescribeAddresses`의 연결 상태 | 연결되지 않았다는 사실만으로 해제하지 않음. 보호 태그는 `EXCLUDED` |

CPU의 5%와 샘플 7개는 프로젝트의 **보수적 검토용 휴리스틱**이다. CPU 샘플은 CloudWatch에서 14일 기간을 하루 단위로 요청한다. 샘플 7개가 14일 내 연속 사용량을 보증하지는 않는다. 네트워크·디스크·스케줄 작업, ASG/로드밸런서, 예약 할인, EBS 및 공인 IPv4 잔존 비용은 평가하지 않는다. 따라서 EC2 후보는 중지 권고가 아니다.

태그 키·값은 대소문자와 앞뒤 공백을 정규화한다. `protected=true|yes|1`, `critical=true|yes|1`, `environment=prod|production`은 `EXCLUDED`다. EBS의 `retain`, `retention`, `do-not-delete`가 참이면 보존 대상으로 제외한다. 태그가 없으면 개발 환경으로 추정하지 않고 위험을 `UNKNOWN`으로 둔다. 위험 등급은 초기 태그 기반 신호이며, 전체 위험 평가는 Phase 4에서 확장한다. 태그 원문은 보고서에 내보내지 않는다.

`finding_id`는 공급자·정책·리전·리소스 ID로 구성하며 정렬 순서는 결정적이다. `analysis_status`는 전체 수집 성공일 때 `COMPLETE`, 일부 수집 실패일 때 `PARTIAL`, 평가할 수집 범위가 없을 때 `NOT_EVALUATED`다. 실패한 범위의 미발견을 리소스 0건으로 해석하지 않는다. `missing_cost_tag`는 조직의 필수 태그 설정이 없으므로 구현을 보류했다.
