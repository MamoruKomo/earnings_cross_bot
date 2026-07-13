#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

try:
    import certifi  # type: ignore
except Exception:  # pragma: no cover
    certifi = None


KABUTAN_DISCLOSURES_URL = "https://kabutan.jp/disclosures/"
TDNET_LIST_BASE_URL = "https://www.release.tdnet.info/inbs/"
TDNET_PDF_BASE_URL = "https://www.release.tdnet.info/inbs/"
DEFAULT_SLACK_CHANNEL_ID = "C0ASFHVU94L"
JST = ZoneInfo("Asia/Tokyo")
MAX_SEEN_IDS = 5000
MAX_STORED_ITEMS = 500
MAX_TDNET_PAGES = 20
ALERT_ENGINE = "official_tdnet_v2"

CODE_ONLY_RE = re.compile(r"^\d{3,4}[A-Z]?$")
KABUTAN_LIST_DT_RE = re.compile(
    r"(?P<yy>\d{2})/(?P<mon>\d{2})/(?P<day>\d{2})\s+(?P<hour>\d{2}):(?P<minute>\d{2})"
)
TDNET_DOC_ID_RE = re.compile(r"(?P<id>\d{18})")


class FetchUnavailable(RuntimeError):
    pass


class SlackPostError(RuntimeError):
    pass


@dataclass(frozen=True)
class Disclosure:
    id: str
    code: str
    company: str
    datetime_jst: str
    title: str
    pdf_url: str
    source_url: str


@dataclass(frozen=True)
class KabutanListRow:
    code: str
    company: str
    date_jst: str
    title: str
    doc_id: str
    source_url: str


@dataclass(frozen=True)
class TdnetListRow:
    time_jst: str
    code: str
    company: str
    title: str
    pdf_url: str
    source_url: str
    xbrl_url: str = ""


def normalize_spaces(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def has_japanese(text: str) -> bool:
    return re.search(r"[一-龯ぁ-んァ-ン]", normalize_spaces(text)) is not None


def normalize_security_code(code: str) -> str:
    s = normalize_spaces(code)
    if len(s) == 5 and s.endswith("0"):
        return s[:4]
    return s


def extract_tdnet_doc_id(value: str) -> str:
    s = normalize_spaces(value)
    m = re.search(r"/(?P<id>\d{18})\.pdf", s)
    if m:
        return m.group("id")
    m = re.search(r"/pdf/\d{8}/(?P<id>\d{18})/?", s)
    if m:
        return m.group("id")
    m = TDNET_DOC_ID_RE.search(s)
    return m.group("id") if m else ""


def build_tdnet_pdf_url(doc_id_or_url: str) -> str:
    doc_id = extract_tdnet_doc_id(doc_id_or_url)
    if not doc_id:
        return ""
    return f"{TDNET_PDF_BASE_URL}{doc_id}.pdf"


def absolutize_tdnet_url(value: str) -> str:
    s = normalize_spaces(value)
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return TDNET_LIST_BASE_URL + s.lstrip("./")


def parse_kabutan_datetime_jst(text: str) -> str:
    m = KABUTAN_LIST_DT_RE.search(normalize_spaces(text))
    if not m:
        return ""
    year = 2000 + int(m.group("yy"))
    return (
        f"{year:04d}-{int(m.group('mon')):02d}-{int(m.group('day')):02d} "
        f"{int(m.group('hour')):02d}:{int(m.group('minute')):02d} JST"
    )


def disclosure_family_id(code: str, doc_id: str) -> str:
    family = normalize_spaces(doc_id)[:16]
    return f"kabutan:{normalize_spaces(code)}:{family}"


class TdnetListParser(HTMLParser):
    def __init__(self, date_yyyymmdd: str) -> None:
        super().__init__()
        self.date_yyyymmdd = date_yyyymmdd
        self.rows: list[TdnetListRow] = []
        self._in_tr = False
        self._in_cell = False
        self._cell_kind = ""
        self._cell_text: list[str] = []
        self._cell_href = ""
        self._current: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._in_tr = True
            self._current = {}
            return
        if not self._in_tr:
            return
        if tag == "td":
            classes = set(normalize_spaces(attrs_dict.get("class") or "").split())
            kind = ""
            for candidate in ("kjTime", "kjCode", "kjName", "kjTitle", "kjXbrl"):
                if candidate in classes:
                    kind = candidate
                    break
            if kind:
                self._in_cell = True
                self._cell_kind = kind
                self._cell_text = []
                self._cell_href = ""
            return
        if tag == "a" and self._in_cell:
            href = normalize_spaces(attrs_dict.get("href") or "")
            if href:
                self._cell_href = absolutize_tdnet_url(href)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_cell:
            text = normalize_spaces(" ".join(self._cell_text))
            if self._cell_kind == "kjTitle":
                self._current["title"] = text
                self._current["pdf_url"] = self._cell_href
            elif self._cell_kind == "kjXbrl":
                self._current["xbrl_url"] = self._cell_href
            elif self._cell_kind:
                self._current[self._cell_kind] = text
            self._in_cell = False
            self._cell_kind = ""
            self._cell_text = []
            self._cell_href = ""
            return

        if tag == "tr" and self._in_tr:
            self._in_tr = False
            self._flush_row()
            self._current = {}

    def _flush_row(self) -> None:
        raw_code = normalize_spaces(self._current.get("kjCode") or "")
        code = normalize_security_code(raw_code)
        company = normalize_spaces(self._current.get("kjName") or "")
        time_jst = normalize_spaces(self._current.get("kjTime") or "")
        title = normalize_spaces(self._current.get("title") or "")
        pdf_url = normalize_spaces(self._current.get("pdf_url") or "")
        if not (code and company and time_jst and title and pdf_url):
            return

        self.rows.append(
            TdnetListRow(
                time_jst=time_jst,
                code=code,
                company=company,
                title=title,
                pdf_url=pdf_url,
                source_url=pdf_url,
                xbrl_url=normalize_spaces(self._current.get("xbrl_url") or ""),
            )
        )


def parse_tdnet_disclosures(html: str, date_yyyymmdd: str) -> list[Disclosure]:
    parser = TdnetListParser(date_yyyymmdd)
    parser.feed(html)

    date_display = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:8]}"
    disclosures: list[Disclosure] = []
    for row in parser.rows:
        doc_id = extract_tdnet_doc_id(row.pdf_url)
        if not doc_id:
            continue
        disclosures.append(
            Disclosure(
                id=f"tdnet:{row.code}:{doc_id}",
                code=row.code,
                company=row.company,
                datetime_jst=f"{date_display} {row.time_jst} JST",
                title=row.title,
                pdf_url=row.pdf_url,
                source_url=row.source_url,
            )
        )

    disclosures.sort(key=lambda d: (d.datetime_jst, d.id), reverse=True)
    return disclosures


class KabutanDisclosuresTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[KabutanListRow] = []
        self._in_tr = False
        self._in_td = False
        self._in_a = False
        self._a_href = ""
        self._a_text: list[str] = []
        self._td_text: list[str] = []
        self._td_links: list[tuple[str, str]] = []
        self._cells: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._in_tr = True
            self._cells = []
            return
        if not self._in_tr:
            return
        if tag in {"td", "th"}:
            self._in_td = True
            self._td_text = []
            self._td_links = []
            return
        if tag == "a" and self._in_td:
            href = dict(attrs).get("href") or ""
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://kabutan.jp" + href
            self._in_a = True
            self._a_href = href
            self._a_text = []

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._td_text.append(data)
        if self._in_a:
            self._a_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_a:
            text = normalize_spaces(" ".join(self._a_text))
            href = normalize_spaces(self._a_href)
            if href and text:
                self._td_links.append((href, text))
            self._in_a = False
            self._a_href = ""
            self._a_text = []
            return

        if tag in {"td", "th"} and self._in_td:
            self._cells.append(
                {"text": normalize_spaces(" ".join(self._td_text)), "links": list(self._td_links)}
            )
            self._in_td = False
            self._td_text = []
            self._td_links = []
            return

        if tag == "tr" and self._in_tr:
            self._in_tr = False
            self._flush_row()
            self._cells = []

    def _flush_row(self) -> None:
        if not self._cells:
            return

        code = ""
        code_cell_idx: int | None = None
        title = ""
        disclosure_href = ""
        date_text = ""

        for idx, cell in enumerate(self._cells):
            cell_text = normalize_spaces(cell.get("text") or "")
            if not date_text and KABUTAN_LIST_DT_RE.search(cell_text):
                date_text = cell_text

            for href, text in cell.get("links") or []:
                if "stock/?code=" in href and CODE_ONLY_RE.match(text):
                    code = text
                    code_cell_idx = idx
                if "/disclosures/pdf/" in href:
                    title = text
                    disclosure_href = href

        if code_cell_idx is None:
            return
        company = ""
        if len(self._cells) > code_cell_idx + 1:
            company = normalize_spaces(self._cells[code_cell_idx + 1].get("text") or "")

        doc_id = extract_tdnet_doc_id(disclosure_href)
        date_jst = parse_kabutan_datetime_jst(date_text)
        if not (code and company and title and doc_id and date_jst):
            return

        self.rows.append(
            KabutanListRow(
                code=code,
                company=company,
                date_jst=date_jst,
                title=title,
                doc_id=doc_id,
                source_url=disclosure_href,
            )
        )


def parse_kabutan_disclosures(html: str) -> list[Disclosure]:
    parser = KabutanDisclosuresTableParser()
    parser.feed(html)

    grouped: dict[tuple[str, str], list[KabutanListRow]] = {}
    for row in parser.rows:
        family = row.doc_id[:16]
        grouped.setdefault((row.code, family), []).append(row)

    disclosures: list[Disclosure] = []
    for (code, family), rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: r.doc_id)
        jp_row = next((row for row in rows_sorted if has_japanese(row.title)), None)
        primary = jp_row or rows_sorted[0]
        disclosures.append(
            Disclosure(
                id=f"kabutan:{code}:{family}",
                code=code,
                company=primary.company,
                datetime_jst=primary.date_jst,
                title=primary.title,
                pdf_url=build_tdnet_pdf_url(primary.doc_id),
                source_url=primary.source_url,
            )
        )

    disclosures.sort(key=lambda d: (d.datetime_jst, d.id), reverse=True)
    return disclosures


def parse_disclosures(html: str) -> list[Disclosure]:
    return parse_kabutan_disclosures(html)


def fetch_html(url: str) -> str:
    context = None
    if certifi is not None:
        try:
            context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            context = None
    if context is None:
        context = ssl.create_default_context()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
        "Referer": "https://www.release.tdnet.info/inbs/I_main_00.html",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {403, 405, 429, 500, 502, 503, 504}:
                raise
        except URLError as exc:
            last_error = exc

        if attempt < 2:
            time.sleep(2 * (attempt + 1))

    raise FetchUnavailable(f"failed to fetch {url}: {last_error}")


def fetch_tdnet_disclosures(date_yyyymmdd: str) -> list[Disclosure]:
    disclosures: list[Disclosure] = []
    for page in range(1, MAX_TDNET_PAGES + 1):
        url = f"{TDNET_LIST_BASE_URL}I_list_{page:03d}_{date_yyyymmdd}.html"
        try:
            html = fetch_html(url)
        except HTTPError as exc:
            if exc.code == 404:
                break
            raise
        page_items = parse_tdnet_disclosures(html, date_yyyymmdd)
        if not page_items:
            if page == 1:
                return []
            break
        disclosures.extend(page_items)
    disclosures.sort(key=lambda d: (d.datetime_jst, d.id), reverse=True)
    return disclosures


def fetch_kabutan_disclosures() -> list[Disclosure]:
    return parse_kabutan_disclosures(fetch_html(KABUTAN_DISCLOSURES_URL))


def fetch_latest_disclosures(date_yyyymmdd: str) -> tuple[list[Disclosure], str]:
    try:
        tdnet_items = fetch_tdnet_disclosures(date_yyyymmdd)
        if tdnet_items:
            return tdnet_items, "tdnet"
    except (FetchUnavailable, HTTPError, URLError) as exc:
        print(f"[tdnet-slack-alert] TDnet official unavailable; trying Kabutan fallback: {exc}", file=sys.stderr)
    return fetch_kabutan_disclosures(), "kabutan_fallback"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "alert_engine": None, "seen_ids": [], "items": [], "last_checked_jst": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "alert_engine": None, "seen_ids": [], "items": [], "last_checked_jst": None}
    if not isinstance(data, dict):
        return {"version": 1, "alert_engine": None, "seen_ids": [], "items": [], "last_checked_jst": None}
    seen_ids = data.get("seen_ids")
    if not isinstance(seen_ids, list):
        seen_ids = data.get("seen")
    if not isinstance(seen_ids, list):
        seen_ids = []
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    migrated_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = normalize_spaces(item.get("id") or "")
        code = normalize_security_code(normalize_spaces(item.get("code") or ""))
        doc_id = extract_tdnet_doc_id(
            normalize_spaces(
                item.get("pdf_url_tdnet")
                or item.get("pdf_url_ja")
                or item.get("pdf_url")
                or item.get("doc_id_ja")
                or item.get("doc_id_en")
                or raw_id
            )
        )
        if raw_id:
            migrated_ids.append(raw_id)
        if code and doc_id:
            migrated_ids.append(f"tdnet:{code}:{doc_id}")
            migrated_ids.append(disclosure_family_id(code, doc_id))
    seen_ids = list(dict.fromkeys([*seen_ids, *migrated_ids]))
    return {
        "version": int(data.get("version") or 1),
        "alert_engine": normalize_spaces(data.get("alert_engine") or "") or None,
        "seen_ids": [normalize_spaces(x) for x in seen_ids if normalize_spaces(x)],
        "items": [x for x in items if isinstance(x, dict)],
        "last_checked_jst": data.get("last_checked_jst"),
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_next_state(current: dict[str, Any], latest: list[Disclosure]) -> dict[str, Any]:
    existing_seen = [normalize_spaces(x) for x in current.get("seen_ids", []) if normalize_spaces(x)]
    latest_ids = [d.id for d in latest]

    seen_ids: list[str] = []
    seen_set: set[str] = set()
    for item_id in latest_ids + existing_seen:
        if item_id and item_id not in seen_set:
            seen_ids.append(item_id)
            seen_set.add(item_id)

    return {
        "version": 1,
        "alert_engine": ALERT_ENGINE,
        "last_checked_jst": datetime.now(JST).isoformat(timespec="seconds"),
        "seen_ids": seen_ids[:MAX_SEEN_IDS],
        "items": [asdict(d) for d in latest[:MAX_STORED_ITEMS]],
    }


def build_slack_message(disclosures: list[Disclosure]) -> str:
    blocks: list[str] = []
    for disclosure in disclosures:
        blocks.append(
            "\n".join(
                [
                    f"証券コード: {disclosure.code}",
                    f"銘柄名: {disclosure.company}",
                    f"日付: {disclosure.datetime_jst}",
                    f"たいとる: {disclosure.title}",
                    f"PDFのりんく: {disclosure.pdf_url}",
                ]
            )
        )
    return "\n---\n".join(blocks)


def post_to_slack(message: str, channel_id: str, bot_token: str, webhook_url: str) -> None:
    if bot_token:
        payload = {
            "channel": channel_id,
            "text": message,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=data,
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body)
        if not result.get("ok"):
            raise SlackPostError(f"Slack chat.postMessage failed: {result}")
        return

    if webhook_url:
        payload = {"text": message, "unfurl_links": False, "unfurl_media": False}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        return

    raise SlackPostError("Set SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL before sending notifications.")


def append_github_output(values: dict[str, str], output_path: str) -> None:
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value:
                marker = "EOF"
                handle.write(f"{key}<<{marker}\n{value.rstrip()}\n{marker}\n")
            else:
                handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send new TDnet disclosures to Slack.")
    parser.add_argument("--state", default="data/tdnet_state.json", help="Path to the JSON state file")
    parser.add_argument("--max-notify", type=int, default=30, help="Maximum disclosures to send per run")
    parser.add_argument("--date", default=datetime.now(JST).strftime("%Y%m%d"), help="TDnet date as YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print without posting or saving state")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = load_state(state_path)

    latest, source = fetch_latest_disclosures(args.date)
    existing_ids = set(state["seen_ids"])
    is_bootstrap = state.get("alert_engine") != ALERT_ENGINE or not existing_ids
    new_items = [item for item in latest if item.id not in existing_ids]

    message = build_slack_message(new_items[: args.max_notify]) if new_items and not is_bootstrap else ""
    result = {
        "latest_count": str(len(latest)),
        "new_count": str(len(new_items)),
        "bootstrapped": "true" if is_bootstrap and bool(latest) else "false",
        "source": source,
        "state_changed": "false",
        "message": message,
    }

    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if message:
            print(message)
        return 0

    if is_bootstrap:
        if latest:
            save_state(state_path, build_next_state(state, latest))
            result["state_changed"] = "true"
        append_github_output(result, os.environ.get("GITHUB_OUTPUT", ""))
        print(json.dumps({k: v for k, v in result.items() if k != "message"}, ensure_ascii=False))
        return 0

    if new_items:
        channel_id = normalize_spaces(os.environ.get("SLACK_CHANNEL_ID") or DEFAULT_SLACK_CHANNEL_ID)
        bot_token = normalize_spaces(os.environ.get("SLACK_BOT_TOKEN") or "")
        webhook_url = normalize_spaces(os.environ.get("SLACK_WEBHOOK_URL") or "")
        post_to_slack(message, channel_id=channel_id, bot_token=bot_token, webhook_url=webhook_url)
        save_state(state_path, build_next_state(state, latest))
        result["state_changed"] = "true"

    append_github_output(result, os.environ.get("GITHUB_OUTPUT", ""))
    print(json.dumps({k: v for k, v in result.items() if k != "message"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FetchUnavailable as exc:
        print(f"[tdnet-slack-alert] source unavailable: {exc}", file=sys.stderr)
        raise SystemExit(0)
    except SlackPostError as exc:
        print(f"[tdnet-slack-alert] {exc}", file=sys.stderr)
        raise SystemExit(1)
