# 종속성 라이선스 검토

2026-10-20 로컬 설치본의 패키지 메타데이터 기준이다. CloudSaver 자체 라이선스는 [Apache-2.0](../LICENSE)이며 아래 표는 법률 판단이 아닌 배포 점검 기록이다. 패키지 버전 범위를 사용하므로 정식 배포 전에 실제 해결된 버전의 메타데이터와 라이선스 파일을 다시 확인한다.

| 패키지 | 사용 위치 | 확인된 버전 | 메타데이터 라이선스 |
|---|---|---|---|
| boto3 | AWS 선택 설치 | 1.43.103 | Apache-2.0 |
| botocore | boto3 의존성 | 1.43.114 | Apache-2.0 |
| s3transfer | boto3 의존성 | 0.19.2 | Apache-2.0 |
| jmespath | boto3 의존성 | 1.1.0 | MIT |
| c7n | Custodian 선택 설치 | 0.9.53 | Apache-2.0 |
| PyYAML | c7n 의존성 | 6.0.3 | MIT |
| cryptography | c7n 의존성 | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| argcomplete | c7n 의존성 | 3.7.2 | Apache Software License |
| attrs | c7n 전이 의존성 | 26.1.0 | MIT |
| cffi | c7n 전이 의존성 | 2.1.1 | MIT-0 |
| jsonschema | c7n 의존성 | 4.26.0 | MIT |
| jsonschema-specifications | jsonschema 의존성 | 2025.9.1 | MIT |
| pycparser | cffi 의존성 | 3.11 | BSD-3-Clause |
| python-dateutil | c7n 의존성 | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause 이중 라이선스 |
| referencing | jsonschema 의존성 | 0.37.0 | MIT |
| rpds-py | referencing 의존성 | 2026.9.1 | MIT |
| six | python-dateutil 의존성 | 1.17.0 | MIT |
| tabulate | c7n 의존성 | 0.10.0 | MIT |
| urllib3 | botocore 및 c7n 의존성 | 2.8.0 | MIT |

위 항목은 현재 확인된 런타임 의존성 전체다. `pip install`로 별도 설치되는 패키지를 CloudSaver 휠에 포함하지는 않는다. Docker 빌드에서 해결된 botocore·s3transfer 버전은 각각 1.43.115·0.19.3으로 로컬 환경과 달랐다. 따라서 배포 시 해결된 버전 기준으로 고지 파일을 다시 작성해야 한다. 컨테이너 이미지에는 Python 및 Debian 구성 요소도 들어가므로 이미지 배포 전 별도 SBOM/고지 검토가 필요하다. [Python 패키지 라이선스 메타데이터 형식](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#license-and-license-files)을 참고한다.
