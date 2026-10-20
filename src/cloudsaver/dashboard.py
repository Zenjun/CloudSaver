"""Self-contained, read-only HTML view of a validated CloudSaver report."""

from html import escape
from importlib import resources
from typing import Any


def _text(value: object) -> str:
    return escape("—" if value is None else str(value), quote=True)


def _items(values: list[str]) -> str:
    if not values:
        return '<span class="muted">기록 없음</span>'
    return "<ul>" + "".join(f"<li>{_text(value)}</li>" for value in values) + "</ul>"


def _evidence(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">수집된 근거가 없습니다.</p>'
    rows = []
    for item in items:
        value = "자료 없음" if item["value"] is None else str(item["value"])
        period = " ~ ".join(
            str(item[key]) for key in ("period_start", "period_end") if item[key] is not None
        )
        rows.append(
            "<tr>"
            f"<th scope='row'>{_text(item['metric'])}</th>"
            f"<td>{_text(value)} {_text(item['unit'] or '')}</td>"
            f"<td>{_text(item['quality'])}</td>"
            f"<td>{_text(period or '—')}</td>"
            f"<td>{_text(item['source'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-scroll"><table><thead><tr><th>지표</th><th>값</th>'
        "<th>품질</th><th>관찰 기간</th><th>출처</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _finding(item: dict[str, Any], number: int) -> str:
    status = item["status"]
    risk = item["risk"]
    savings = item["savings"]
    amount = savings["potential_savings"]
    amount_label = "금액 미확인" if amount == "UNKNOWN" else f"{amount} {savings['currency']} / 월"
    return f"""
<article class="finding" id="finding-{number}">
  <div class="finding-top">
    <div><p class="eyebrow">{_text(item["policy_id"])}</p>
      <h3>{_text(item["resource"]["ref"])}</h3>
      <p class="muted">{_text(item["resource"]["type"])} · {_text(item["finding_id"])}</p></div>
    <div class="badges"><span class="badge status-{status.lower()}">{_text(status)}</span>
      <span class="badge risk-{risk["level"].lower()}">위험 {_text(risk["level"])}</span></div>
  </div>
  <p class="finding-explanation">{_text(item["explanation"])}</p>
  <div class="finding-metrics">
    <div><span>예상 절감액</span><strong>{_text(amount_label)}</strong></div>
    <div><span>추정 신뢰도</span><strong>{_text(savings["confidence"])}</strong></div>
    <div><span>기준 / 변경 후</span>
      <strong>{_text(savings["baseline"])} / {_text(savings["optimized"])}</strong></div>
  </div>
  <details><summary>근거와 판단 제한 보기</summary>
    <div class="details-grid">
      <section><h4>운영 위험 근거</h4>{_items(risk["reasons"])}</section>
      <section><h4>확인되지 않은 요소</h4>{_items(risk["unknown_factors"])}</section>
      <section><h4>비용 가정</h4>{_items(savings["assumptions"])}</section>
      <section><h4>제외된 비용</h4>{_items(savings["excluded_costs"])}</section>
    </div>
    <h4>관찰 자료</h4>{_evidence(item["evidence"])}
    <div class="details-grid">
      <section><h4>계산식</h4><p>{_text(savings["formula"])}</p></section>
      <section><h4>비용 자료 출처</h4>{_items(savings["data_sources"])}</section>
    </div>
  </details>
</article>"""


def _issues(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">기록된 수집 문제가 없습니다.</p>'
    return "".join(
        '<article class="issue">'
        f"<strong>{_text(item['category'])}</strong> · {_text(item['scope'])}"
        f"<p>{_text(item['operation'])} · 재시도 가능: "
        f"{'예' if item['retryable'] else '아니요'}"
        f" · 리소스: {_text(item['resource_ref'])}</p></article>"
        for item in items
    )


def render_dashboard(saved: dict[str, Any]) -> str:
    """Render a sanitized report from ``read_report`` or ``apply_scenarios``."""
    findings = saved["findings"]
    counts = {
        status: sum(item["status"] == status for item in findings)
        for status in ("CANDIDATE", "EXCLUDED", "INSUFFICIENT_DATA")
    }
    unknown_risk = sum(item["risk"]["level"] == "UNKNOWN" for item in findings)
    scope = saved["scope"]
    css = resources.files("cloudsaver").joinpath("data/dashboard.css").read_text(encoding="utf-8")
    demo = saved["data_kind"] == "DEMO"
    notice = '<div class="demo-notice">DEMO DATA · 가상 리소스</div>' if demo else ""
    analysis = (
        f"<span>분석 상태: {_text(saved['analysis_status'])}</span>"
        if "analysis_status" in saved
        else ""
    )
    cards = "".join(_finding(item, index) for index, item in enumerate(findings, 1))
    if not cards:
        cards = (
            '<p class="empty">표시할 탐지 결과가 없습니다. 수집 상태와 실패 범위를 확인하세요.</p>'
        )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
  <title>CloudSaver · 읽기 전용 대시보드</title>
  <style>{css}</style>
</head>
<body>
  <div class="shell">
    <header class="masthead">
      <div class="brand"><span class="brand-mark">C</span><span>CloudSaver</span></div>
      <span class="read-only">읽기 전용 · 로컬 보고서</span>
    </header>
    <main>
      {notice}
      <section class="hero" aria-labelledby="page-title">
        <p class="eyebrow">비용 절감 후보 검토</p>
        <h1 id="page-title">절감 가능성과 운영 위험을 함께 확인하세요.</h1>
        <p>이 화면은 저장된 보고서를 보여줍니다. 후보를 자동으로 중지하거나 삭제하지 않습니다.</p>
        <div class="meta"><span>{_text(saved["data_kind"])} 보고서</span>
          <span>수집 상태: {_text(saved["status"])}</span>{analysis}
          <span>관찰 시각: {_text(saved["scanned_at"])}</span></div>
      </section>
      <section aria-labelledby="overview-title">
        <div class="section-heading"><div><p class="eyebrow">01 · 전체 개요</p>
          <h2 id="overview-title">판단 현황</h2></div>
          <span class="section-note">총 {len(findings)}건의 판단</span></div>
        <div class="stats">
          <div class="stat"><span>검토 후보</span><strong>{counts["CANDIDATE"]}</strong>
            <small>사람의 추가 검토 필요</small></div>
          <div class="stat"><span>제외</span><strong>{counts["EXCLUDED"]}</strong>
            <small>보호 신호 등으로 제외</small></div>
          <div class="stat"><span>자료 부족</span><strong>{counts["INSUFFICIENT_DATA"]}</strong>
            <small>사용량 0으로 간주하지 않음</small></div>
          <div class="stat"><span>위험 미확인</span><strong>{unknown_risk}</strong>
            <small>안전하다고 판단하지 않음</small></div>
        </div>
        <p class="caution">절감액은 자료가 없으면 UNKNOWN입니다.
          조건부 금액은 실제 청구 절감액이 아닙니다.</p>
      </section>
      <section aria-labelledby="findings-title">
        <div class="section-heading"><div><p class="eyebrow">02 · 탐지 결과</p>
          <h2 id="findings-title">후보와 근거</h2></div>
          <span class="section-note">각 항목을 열어 관찰 자료를 확인하세요</span></div>
        <div class="findings">{cards}</div>
      </section>
      <section aria-labelledby="collection-title">
        <div class="section-heading"><div><p class="eyebrow">03 · 데이터 범위</p>
          <h2 id="collection-title">수집 범위와 문제</h2></div></div>
        <div class="scope-grid">
          <div><h3>요청 범위</h3>{_items(scope["requested"])}</div>
          <div><h3>완료 범위</h3>{_items(scope["completed"])}</div>
          <div><h3>실패 범위</h3>{_items(scope["failed"])}</div>
        </div>
        <div class="issues"><h3>수집 문제 · {len(saved["collection_issues"])}건</h3>
          {_issues(saved["collection_issues"])}</div>
      </section>
    </main>
    <footer>CloudSaver · 저장된 보고서의 읽기 전용 화면 ·
      실행 이력은 아직 제공하지 않습니다.</footer>
  </div>
</body>
</html>
"""
