# 읽기 전용 HTML 대시보드

Phase 7 대시보드는 CloudSaver가 저장한 JSON 보고서를 독립 HTML 파일로 변환한다. 탐지·위험·비용 계산 로직은 CLI와 동일하며, HTML 생성 과정에서 AWS나 외부 서버에 접속하지 않는다. 웹 서버, 데이터베이스, JavaScript, 별도 프론트엔드 설치도 필요하지 않다.

```bash
cloudsaver demo scan --format json --output demo-report.json
cloudsaver dashboard --input demo-report.json --output dashboard.html
# 선택: 이미 준비한 비용 시나리오 적용
cloudsaver dashboard --input demo-report.json --cost-input costs.json --output priced-dashboard.html
```

생성된 HTML을 로컬 브라우저에서 열면 후보·제외·자료 부족 건수, 개별 탐지의 위험 근거와 미확인 요소, 관찰 자료, 비용 가정·출처, 수집 실패 범위를 볼 수 있다. 비용 자료가 없으면 `UNKNOWN`을 유지한다. 조건부 시나리오의 금액은 실제 청구 절감액이 아니다. 서로 다른 조건부 금액을 합산하여 총 절감액으로 표시하지 않는다.

입력은 `schema_version`을 검사하는 기존 저장 보고서 로더를 통과한다. 보고서의 문자열은 HTML 이스케이프하며, 결과물에는 외부 스크립트·폰트·이미지·네트워크 요청이 없다. 출력은 새 파일에만 `0600` 권한으로 작성한다. 브라우저에서 열 때에도 파일을 공유하거나 공개 웹 서버에 올리면 보고서 내용이 노출될 수 있다.

현재 화면은 저장 당시의 스냅샷이며 자동 새로고침이나 실시간 AWS 조회는 없다. 실행 명령과 실행 이력도 제공하지 않는다. 수집이 `PARTIAL` 또는 `FAILED`이면 수집 범위와 문제를 함께 표시하므로 빈 후보 목록을 낭비 없음으로 해석하지 않는다.
