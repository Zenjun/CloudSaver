# 공개 배포 준비 점검

Phase 6는 설치 가능한 소스/휠, 로컬 Docker 이미지, 자동 테스트 및 문서를 준비하는 단계다. GitHub 저장소는 이미 공개되어 있으나, PyPI 게시·이미지 레지스트리 푸시·태그/릴리스 생성은 아직 하지 않았다.

## 라이선스

저작권자 요청에 따라 CloudSaver에 [Apache License 2.0](../LICENSE)을 적용했다. [NOTICE](../NOTICE)에 저작권 고지를 두고, `pyproject.toml`의 SPDX 표현식과 패키지에 포함할 라이선스 파일도 지정했다. 재배포 시 라이선스 본문과 적용되는 고지를 유지한다. 현재 확인된 Python 런타임 의존성은 Apache/MIT/BSD 계열이다. 원문: [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.html).

## 배포 전 게이트

1. [종속성 라이선스 기록](third-party-licenses.md)을 확인하고, 포함된 배포물의 고지 요건을 다시 점검한다. CI의 취약점 검사가 통과해야 한다.
2. GitHub Actions의 Python 3.11–3.13, Linux amd64/arm64 및 macOS 검사를 통과시킨다. CI는 AWS 자격 증명을 받지 않는다.
3. 휠과 sdist를 새 가상환경에 설치해 데모를 실행하고, 두 아키텍처에서 Docker 이미지를 빌드·실행한다.
4. 코드·Git 이력·배포 산출물의 비밀정보를 검토한다. 이미 공개된 비밀이 발견되면 폐기·교체한다. 저장소의 비공개 취약점 신고 기능은 현재 비활성화되어 있으므로 공개 배포 전에 활성화하거나 대체 비공개 연락 채널을 마련한다.
5. README, 설치·권한·보안 문서와 변경 이력이 실제 기능과 일치하는지 검토한다.
6. 태그, GitHub Release, PyPI, 외부 이미지 레지스트리 게시는 사용자 최종 승인 후 수행한다.

`cloudsaver scan`과 Custodian 평가는 실제 AWS 계정에서 아직 검증되지 않았다. 정식 릴리스 설명에서는 이 한계를 유지해야 한다. 자동 실행이나 클라우드 쓰기 기능은 이 단계에 없다.
