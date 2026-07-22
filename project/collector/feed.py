# -*- coding: utf-8 -*-
"""환경 변수로 등록한 RSS/Atom 뉴스와 기관 공고 피드를 수집한다."""

from __future__ import annotations

import os
import re
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from .base import BaseCollector, clean_text


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _tag_name(child.tag) in names:
            if _tag_name(child.tag) == "link" and child.attrib.get("href"):
                return clean_text(child.attrib["href"])
            return clean_text("".join(child.itertext()))
    return ""


def _feed_specs(value: str) -> List[Tuple[str, str]]:
    specs: List[Tuple[str, str]] = []
    for token in re.split(r"[\n,;]+", value or ""):
        token = token.strip()
        if not token:
            continue
        label, separator, url = token.partition("|")
        if not separator:
            url, label = label, "RSS"
        if url.strip().startswith(("https://", "http://")):
            specs.append((clean_text(label) or "RSS", url.strip()))
    return specs


def _date_only(value: str) -> Optional[str]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        match = re.search(r"(20\d{2})[-/.]?(\d{2})[-/.]?(\d{2})", value)
        return "-".join(match.groups()) if match else None


class ConfiguredFeedCollector(BaseCollector):
    feed_env_name = "NEWS_RSS_FEEDS"

    async def collect(self, seed_projects: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for configured_name, feed_url in _feed_specs(os.getenv(self.feed_env_name, "")):
            response = await self._http_get(feed_url, {})
            try:
                root = ET.fromstring(response.text.lstrip("\ufeff"))
            except ET.ParseError:
                continue
            channel_title = ""
            for node in root.iter():
                if _tag_name(node.tag) in {"channel", "feed"}:
                    channel_title = _child_text(node, {"title"})
                    if channel_title:
                        break
            publisher = channel_title or configured_name
            for node in root.iter():
                if _tag_name(node.tag) not in {"item", "entry"}:
                    continue
                title = _child_text(node, {"title"})
                link = _child_text(node, {"link", "guid", "id"}) or feed_url
                summary = _child_text(node, {"description", "summary", "content", "encoded"})
                published = _child_text(node, {"pubdate", "published", "updated", "date"})
                project = self.clean_item(
                    "feed",
                    {"title": title, "publisher": publisher, "description": summary, "pubDate": published, "link": link},
                    title=title,
                    publisher=publisher,
                    source_url=link,
                    registered_at=_date_only(published),
                )
                if project:
                    results.append(project)
                if len(results) >= self.max_items:
                    return results
        return results


class NewsCollector(ConfiguredFeedCollector):
    name = "NewsRSS"
    source_type = "NEWS"
    feed_env_name = "NEWS_RSS_FEEDS"


class PublicNoticeCollector(ConfiguredFeedCollector):
    name = "PublicNoticeRSS"
    source_type = "PUBLIC_NOTICE"
    feed_env_name = "PUBLIC_NOTICE_RSS_FEEDS"
