# Phase 5 Cloud Custodian 연동

CloudSaver는 Cloud Custodian 0.9.53의 CLI를 별도 프로세스로 호출한다. 정책 검증은 로컬에서 실행하며, 평가는 AWS 읽기 호출을 한다. 이 어댑터는 CloudSaver의 비용 후보 탐지와 독립적이다. 결과 JSON의 `data_kind`는 `CUSTODIAN`이며 `findings`나 예상 절감액을 생성하지 않는다.

## 정책 범위

YAML 최상위에는 `policies`만 허용한다. 정책은 1~10개이고 각각 `name`, `resource`, `filters`, 선택적 `description`만 허용한다. `actions`는 빈 목록이어도 거부하며 `mode`도 거부한다. 지원 리소스와 필터는 다음과 같다.

| 리소스 | 허용 필터 키 | 결과 식별자 |
|---|---|---|
| `aws.ec2` | `State.Name` | `InstanceId` |
| `aws.ebs` | `State` | `VolumeId` |
| `aws.elastic-ip` | `AssociationId` | `AllocationId` |

필터는 `type: value`, `op: eq`(생략 가능), 스칼라 `value`만 허용한다. 다른 Custodian 필터, `value_from`, 실행 모드, 사용자 쿼리, 임의 정책 필드는 거부한다. 중복 YAML 키와 1MB를 넘는 파일도 거부한다. 허용된 필드로 정책을 새로 작성해 Custodian에 전달한다.

```yaml
policies:
  - name: detached-ebs
    resource: aws.ebs
    filters:
      - type: value
        key: State
        value: available
```

## 실행과 권한

```bash
cloudsaver custodian validate --policy policy.yml --format json
cloudsaver custodian evaluate --policy policy.yml --region ap-northeast-2 --assume-role arn:aws:iam::123456789012:role/CloudSaverReadOnly --format json
```

`validate`는 Custodian의 정책 스키마 검사를 한다. `evaluate`는 검증 후 `custodian run --dryrun`을 실행한다. 역할 전환(`--assume`)과 `--session-policy`는 필수다. 세션 정책은 `ec2:DescribeAddresses`, `ec2:DescribeInstances`, `ec2:DescribeRegions`, `ec2:DescribeTags`, `ec2:DescribeVolumes`, `sts:GetCallerIdentity`만 허용한다. 이 역할에도 해당 읽기 권한만 부여하고, 호출 주체에는 그 역할의 `sts:AssumeRole`만 허용해야 한다. 역할의 신뢰 정책도 호출 주체로 제한해야 한다. 필요한 API가 거부되면 실패로 처리하며 권한 범위를 자동 확대하지 않는다.

원본 Custodian 리소스 출력과 캐시는 임시 디렉터리에 저장하고 명령 종료 시 제거한다. CloudSaver 결과에는 정책명, 리소스 종류, 일치 개수, 형식이 검증된 리소스 ID만 포함한다. 태그 값, 계정 ID, 공개 IP와 Custodian 원문 오류는 출력하지 않는다. `--output`은 새 파일만 생성하고 권한은 소유자 읽기/쓰기로 제한한다.

실패한 검증·평가를 빈 결과로 표현하지 않는다. 잘못된 정책·옵션 또는 미설치 의존성은 종료 코드 2, Custodian 명령 실패는 5다. 실제 계정 평가와 IAM 허용 목록의 완전성은 아직 검증하지 않았다.

CLI와 안전성 근거: [Cloud Custodian 개요](https://cloudcustodian.io/docs/overview.html), [Custodian CLI 구현](https://github.com/cloud-custodian/cloud-custodian/blob/main/c7n/cli.py), [자격 증명 구현](https://github.com/cloud-custodian/cloud-custodian/blob/main/c7n/credentials.py), [AWS EC2 리소스](https://cloudcustodian.io/docs/aws/resources/group-ec2.html).
