#!/usr/bin/env python3
"""v7 카탈로그로 기획서 표를 채워 .md를 만들고, 같은 내용을 .html로 렌더링한다.

사용: python3 production-plan/v7/tools/build_docs.py  (build_v7.py 다음에 실행)
"""
import html
import json
import re
from pathlib import Path

V7 = Path(__file__).resolve().parents[1]
cat = json.loads((V7 / "production-catalog-v7.json").read_text(encoding="utf-8"))
by = {v["id"]: v for v in cat["videos"]}
main = [v for v in cat["videos"] if v["type"] == "본편"]


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def title(vid):
    v = by[vid]
    return v.get("public_title") or v["title"]


parts = {
    "SEASONS": table(["시즌", "회차", "주차", "핵심 입구", "주요 홍보 이론"],
                     [[s["season"], s["episodes"], s["weeks"], s["entry"], s["theories"]] for s in cat["seasons"]]),
    "EPISODES": table(["ID", "공개 제목 형식", "주홍보이론", "사례·비교·근거", "대표 학자·개념"],
                      [[v["id"], v["public_title"], v["theory_name"], v["case"],
                        f"{v['primary_scholar']['name']} — {v['primary_scholar']['concept']} ({v['primary_scholar']['text']})"]
                       for v in main]),
    "MITO": table(["ID", "제목", "미토 연결 지점"],
                  [[vid, title(vid), by[vid]["mito_link"]] for vid in by if by[vid].get("mito_link")]),
    "MINPA": table(["ID", "제목", "민파/패파 슬롯"],
                   [[vid, title(vid), by[vid]["minpa_slot"]] for vid in by if by[vid].get("minpa_slot")]),
    "TIME": table(["ID", "제목", "재확인 내용"],
                  [[v["id"], title(v["id"]), v["time_sensitive"]]
                   for v in cat["videos"] if v.get("time_sensitive") and v["type"] != "쇼츠"]),
}

tpl = (V7 / "tools" / "plan_template_v7.md").read_text(encoding="utf-8")
md = re.sub(r"\{\{(\w+)\}\}", lambda m: parts[m.group(1)], tpl)
(V7 / "85편_총괄제작기획_v7.md").write_text(md, encoding="utf-8")


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)


def render(md_text, page_title):
    out, lines, i = [], md_text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(html.escape(lines[i], quote=False))
                i += 1
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
            i += 1
            continue
        if ln.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            head, body = block[0], block[2:]
            out.append('<div class="tw"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
                       + "</tbody></table></div>")
            continue
        m = re.match(r"^(#{1,3}) (.*)", ln)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif re.match(r"^(- |\d+\. )", ln):
            tag = "ol" if ln[0].isdigit() else "ul"
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(page_title)}</title>
<style>
:root{{--bg:#f1f2ed;--fg:#1a2029;--accent:#244c5a;--rule:#8f7128;--cell:#fafaf7;--line:#cfd3ca;--head:#e8eae3;--code:#e6e8e1}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#15191e;--fg:#e3e6ea;--accent:#8cc3d4;--rule:#c9a95a;--cell:#1c2127;--line:#343b44;--head:#242a31;--code:#2a3038}}}}
:root[data-theme="dark"]{{--bg:#15191e;--fg:#e3e6ea;--accent:#8cc3d4;--rule:#c9a95a;--cell:#1c2127;--line:#343b44;--head:#242a31;--code:#2a3038}}
body{{font:16px/1.8 "Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:28px 16px}}
main{{max-width:1120px;margin:auto}}
h1{{color:var(--accent);border-top:2px solid var(--rule);padding-top:24px;margin-top:48px;font-size:1.5em}}
h1:first-child{{border:0;margin-top:0;font-size:1.8em}}
h2{{color:var(--accent);margin-top:32px;font-size:1.2em}}
.tw{{overflow-x:auto;margin:20px 0}}
table{{border-collapse:collapse;width:100%;background:var(--cell);font-size:14px}}
th,td{{border:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}}
th{{background:var(--head);white-space:nowrap}}
pre{{background:var(--code);padding:12px;overflow-x:auto;border-radius:4px}}
pre code{{padding:0}}
code{{background:var(--code);padding:1px 5px;border-radius:3px;font-size:.9em}}
li{{margin:4px 0}}
</style></head><body><main>
{chr(10).join(out)}
</main></body></html>
"""


(V7 / "85편_총괄제작기획_v7.html").write_text(render(md, "85편 총괄 제작기획 v7"), encoding="utf-8")
report = V7 / "v6_평가보고서.md"
if report.exists():
    (V7 / "v6_평가보고서.html").write_text(render(report.read_text(encoding="utf-8"), "v6 평가보고서"),
                                         encoding="utf-8")
print("docs built")
