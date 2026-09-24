#!/usr/bin/env python3
"""카탈로그 정합성 검사. 오류가 있으면 exit 1.

사용: python3 production-plan/v7/tools/validate_catalog.py [catalog.json] [plan.md]
기본값은 v7 카탈로그와 v7 기획서. v6 원본에 돌리면 v6의 결함이 그대로 보고된다.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

V7 = Path(__file__).resolve().parents[1]
cat_path = Path(sys.argv[1]) if len(sys.argv) > 1 else V7 / "production-catalog-v7.json"
md_path = Path(sys.argv[2]) if len(sys.argv) > 2 else V7 / "85편_총괄제작기획_v7.md"

cat = json.loads(cat_path.read_text(encoding="utf-8"))
vs = cat["videos"]
by = {v["id"]: v for v in vs}
errors, warns = [], []

# 1. 편수
cnt = Counter(v["type"] for v in vs)
if cnt != Counter({"본편": 40, "쇼츠": 40, "특별편": 4, "예고": 1}):
    errors.append(f"편수 불일치: {dict(cnt)}")
if len(by) != len(vs):
    errors.append("ID 중복")

main = [v for v in vs if v["type"] == "본편"]

# 2. 쇼츠-본편 연결
for v in vs:
    if v["type"] == "쇼츠":
        p = by.get(v["parent"])
        if not p:
            errors.append(f"{v['id']}: 부모 본편 없음")
        elif p["week"] != v["week"]:
            errors.append(f"{v['id']}: 부모와 주차 다름")

# 3. 주차 충돌 (같은 주·같은 요일)
slots = Counter((v["week"], v["day"]) for v in vs)
for s, n in slots.items():
    if n > 1:
        errors.append(f"슬롯 충돌 W{s[0]} {s[1]} ×{n}")

# 4. 이론명 표기 일관성
names = {}
for v in main:
    names.setdefault(v["theory"], set()).add(v["theory_name"])
for code, ns in names.items():
    if len(ns) > 1:
        errors.append(f"이론 {code} 표기 불일치: {sorted(ns)}")

# 5. 참고문헌 참조
ids = {i for v in vs for i in v.get("reference_ids", [])}
reg = cat.get("reference_registry", {})
missing_ids = sorted(i for i in ids if str(i) not in reg.get("entries", {}))
if missing_ids:
    errors.append(f"reference_ids {missing_ids}가 가리키는 참고문헌 항목이 카탈로그에 없음")
elif ids and "추정" in reg.get("status", ""):
    warns.append(f"참고문헌 {sorted(ids)}는 사용 패턴으로 추정 복원한 것 — 원문 확인 필요")

# 6. 기획축 커버리지
blob = json.dumps(cat, ensure_ascii=False)
if "민파" not in blob:
    errors.append("민파/패파가 카탈로그에 한 번도 등장하지 않음(기획서는 주요 기획축이라 함)")
elif "[신규" not in json.dumps(cat.get("minpa_paepa", {}), ensure_ascii=False):
    warns.append("민파/패파가 강령에 없는 개념인데 [신규] 표시가 없음(CLAUDE.md 7절)")
if not any(v.get("mito_link") for v in vs):
    errors.append("미토가 어느 회차에도 연결되지 않음")

# 6b. 용어 고정(CLAUDE.md 6절)과 9대이론 정식 명칭(사이론 v0.37 부록 G)
for bad, why in [("集擊", "집격=集格만"), ("마음사상", "Simup Sasang"), ("ULRP", "ULRP→ULBP"),
                 ("집격이론", "9대이론 정식 명칭은 집격론"), ("기준점원칙(ULBP)", "정식 명칭은 상위레벨 기준점(ULBP)")]:
    n = blob.count(bad)
    if n:
        errors.append(f"용어 '{bad}' {n}회 — {why}")

# 7. 대표 학자
missing = [v["id"] for v in main if "primary_scholar" not in v]
if missing:
    warns.append(f"대표 학자 미지정 {len(missing)}편(렌즈 학자 3–4명을 60초에 소화해야 함)")
dup = Counter(json.dumps(v["critical_scholar_lens"], ensure_ascii=False) for v in main).most_common(1)[0][1]
if dup > 1 and not all("primary_scholar" in v for v in main):
    warns.append(f"동일 학자 렌즈 문구가 최대 {dup}회 복제됨")

# 8. 시즌 정의·기획서 시즌표 대조
seasons = {s["season"]: s for s in cat.get("seasons", [])}
if not seasons:
    warns.append("카탈로그에 시즌 정의 없음")
if md_path.exists():
    md = md_path.read_text(encoding="utf-8")
    for s, spec in seasons.items():
        lo, hi = [int(x[1:]) for x in spec["episodes"].split("–")]
        actual = sorted(int(v["id"][1:]) for v in main if v["season"] == s)
        if actual != list(range(lo, hi + 1)):
            errors.append(f"{s}: 정의 {spec['episodes']} ≠ 실제 {actual}")
        if not re.search(rf"^\| {s} \| {re.escape(spec['episodes'])} \|", md, re.M):
            errors.append(f"기획서 시즌표에 {s} {spec['episodes']} 행이 없음")
    # 기획서 본편표 ↔ 카탈로그
    sec = re.search(r"^# 5\..*?(?=^# )", md, re.M | re.S)
    rows = re.findall(r"^\| (V\d\d) \| (.*?) \| (.*?) \|", sec.group(0) if sec else "", re.M)
    if len(rows) != 40:
        errors.append(f"기획서 5장 본편표 행 수 {len(rows)} ≠ 40")
    for vid, title, theory in rows:
        v = by.get(vid)
        if not v:
            continue
        if title != v.get("public_title"):
            errors.append(f"기획서 {vid} 제목 불일치")
        if theory != v["theory_name"]:
            errors.append(f"기획서 {vid} 이론 불일치: {theory} ≠ {v['theory_name']}")

for v in main:
    if not v.get("public_title"):
        errors.append(f"{v['id']}: public_title 없음")

print(f"검사 대상: {cat_path.name} / {md_path.name if md_path.exists() else '(기획서 없음)'}")
for e in errors:
    print("  [오류]", e)
for w in warns:
    print("  [주의]", w)
print(f"결과: 오류 {len(errors)} · 주의 {len(warns)}")
sys.exit(1 if errors else 0)
