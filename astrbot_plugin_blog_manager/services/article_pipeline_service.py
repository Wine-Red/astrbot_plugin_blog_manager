"""Deterministic article generation pipeline checks."""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

from ..models import (
    ArticlePipelineResult,
    ArticleRequestSpec,
    AstroArticleDraft,
    BlogGenerateRequest,
    EvidenceItem,
    ImageCandidate,
    SourceRecord,
    ValidationIssue,
)
from ..utils.markdown import extract_image_urls, extract_markdown_links, extract_urls


SUSPICIOUS_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "test.com",
    "test.org",
    "invalid.com",
}

OFFICIAL_AI_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.google.dev",
    "googleblog.com",
    "meta.com",
    "mistral.ai",
    "deepseek.com",
    "qwenlm.github.io",
    "alibabacloud.com",
    "x.ai",
}


class ArticlePipelineService:
    """Normalize article inputs and enforce non-LLM quality gates."""

    def __init__(self, *, allow_generated_sources: bool = False):
        self.allow_generated_sources = allow_generated_sources

    def process(
        self,
        request: BlogGenerateRequest,
        draft: AstroArticleDraft,
    ) -> ArticlePipelineResult:
        spec = self.build_request_spec(request)
        sources = self.collect_sources(request, draft)
        evidence = self.build_evidence(sources)
        images = self.collect_images(draft)
        issues = self.validate_sources(spec, sources)
        issues.extend(self.validate_images(spec, images))
        warnings = self.quality_warnings(spec, draft, sources, images)
        return ArticlePipelineResult(
            request_spec=spec,
            sources=sources,
            evidence=evidence,
            images=images,
            issues=issues,
            warnings=warnings,
        )

    def build_request_spec(self, request: BlogGenerateRequest) -> ArticleRequestSpec:
        text = f"{request.topic} {request.instructions}".lower()
        article_type = "deep_analysis"
        if any(keyword in text for keyword in ("教程", "how to", "指南", "实战")):
            article_type = "tutorial"
        elif any(keyword in text for keyword in ("评测", "review", "对比")):
            article_type = "review"
        elif any(keyword in text for keyword in ("新闻", "日报", "最新", "发布", "today")):
            article_type = "news_explain"
        elif any(keyword in text for keyword in ("系列", "连载", "series")):
            article_type = "series"

        source_policy = "required" if self._needs_sources(text) else "optional"
        image_policy = "required" if request.image_preference != "none" else "none"
        return ArticleRequestSpec(
            topic=request.topic,
            article_type=article_type,
            audience=request.audience,
            source_policy=source_policy,
            image_policy=image_policy,
        )

    def collect_sources(
        self,
        request: BlogGenerateRequest,
        draft: AstroArticleDraft,
    ) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        seen: set[str] = set()
        source_candidates: list[tuple[str, str, str]] = []
        source_candidates.extend(
            (label, url, "user")
            for label, url in extract_markdown_links(request.instructions)
            if self._is_source_like(label, url)
        )
        source_candidates.extend(("用户提供链接", url, "user") for url in extract_urls(request.instructions))
        source_candidates.extend(
            (label, url, "draft")
            for label, url in extract_markdown_links(draft.body)
            if self._is_source_like(label, url)
        )

        for title, url, origin in source_candidates:
            normalized_url = self._normalize_url(url)
            if not normalized_url or normalized_url in seen:
                continue
            seen.add(normalized_url)
            records.append(self._source_record(title, normalized_url, origin))
        return records

    def build_evidence(self, sources: Iterable[SourceRecord]) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for source in sources:
            if not source.accepted:
                continue
            confidence = "high" if source.reliability >= 80 else "medium"
            if source.reliability < 50:
                confidence = "low"
            evidence.append(
                EvidenceItem(
                    claim=f"可引用来源：{source.title}",
                    source_url=source.url,
                    source_title=source.title,
                    quote_or_summary=f"{source.domain} 提供的公开来源。",
                    confidence=confidence,
                )
            )
        return evidence

    def collect_images(self, draft: AstroArticleDraft) -> list[ImageCandidate]:
        candidates: list[ImageCandidate] = []
        seen: set[str] = set()
        if draft.frontmatter.get("image"):
            candidates.append(
                self._image_candidate(
                    str(draft.frontmatter["image"]),
                    f"{draft.title} 封面",
                    "cover",
                )
            )
            seen.add(str(draft.frontmatter["image"]).strip())
        for asset in draft.images:
            if asset.source_url in seen:
                continue
            seen.add(asset.source_url)
            candidates.append(
                self._image_candidate(asset.source_url, asset.alt_text, "section")
            )
        for url in extract_image_urls(draft.body):
            if url in seen:
                continue
            seen.add(url)
            candidates.append(self._image_candidate(url, draft.title, "section"))
        return [candidate for candidate in candidates if candidate.url]

    def validate_sources(
        self,
        spec: ArticleRequestSpec,
        sources: list[SourceRecord],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        accepted_sources = [source for source in sources if source.accepted]
        if spec.source_policy == "required" and not accepted_sources:
            issues.append(
                ValidationIssue(
                    "source",
                    "该主题需要可靠来源，但没有用户提供或工具确认的可核验来源链接。",
                )
            )
        for source in sources:
            if not source.accepted:
                issues.append(
                    ValidationIssue(
                        "source",
                        f"来源链接不可接受: {source.url}；原因: {source.reject_reason}",
                    )
                )
        return issues

    def validate_images(
        self,
        spec: ArticleRequestSpec,
        images: list[ImageCandidate],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if spec.image_policy == "required" and not images:
            issues.append(
                ValidationIssue(
                    "image",
                    "默认需要至少 1 张封面或正文配图；如确实不需要图片，请将 image_preference 设为 none。",
                )
            )
        for image in images:
            if self._is_suspicious_url(image.url):
                issues.append(
                    ValidationIssue(
                        "image",
                        f"图片链接疑似占位或伪造，请替换为真实可核验图片: {image.url}",
                    )
                )
        return issues

    def quality_warnings(
        self,
        spec: ArticleRequestSpec,
        draft: AstroArticleDraft,
        sources: list[SourceRecord],
        images: list[ImageCandidate],
    ) -> list[str]:
        warnings: list[str] = []
        body = draft.body or ""
        if self._chinese_length(body) < 800:
            warnings.append("正文偏短，建议补充背景、案例、实践建议和风险局限。")
        if len(re.findall(r"^##\s+", body, flags=re.MULTILINE)) < 4:
            warnings.append("二级标题少于 4 个，文章结构可能不够稳定。")
        if "|" not in body:
            warnings.append("正文缺少 Markdown 表格。")
        if ">" not in body:
            warnings.append("正文缺少引用块。")
        if spec.source_policy == "required" and sources:
            low_quality = [source.url for source in sources if source.reliability < 50]
            if low_quality:
                warnings.append("存在低可信度来源，建议替换为官方、文档、论文或可信媒体来源。")
        return warnings

    def _source_record(self, title: str, url: str, origin: str) -> SourceRecord:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        source_type = self._source_type(domain, parsed.path)
        reliability = self._source_reliability(domain, source_type)
        accepted = not self._is_suspicious_url(url)
        reject_reason = ""
        if not accepted:
            reject_reason = "疑似占位、测试或本地链接"
        elif origin == "draft" and not self.allow_generated_sources:
            accepted = False
            reject_reason = "正文中的来源链接未出现在用户输入中，插件无法确认不是模型编造"
        return SourceRecord(
            title=title or domain,
            url=url,
            domain=domain,
            origin=origin,
            source_type=source_type,
            reliability=reliability,
            relevance=60,
            accepted=accepted,
            reject_reason=reject_reason,
        )

    def _image_candidate(self, url: str, alt: str, image_type: str) -> ImageCandidate:
        url = self._normalize_url(url)
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        reliability = 70
        if self._is_official_domain(domain):
            reliability = 90
        elif self._is_suspicious_url(url):
            reliability = 0
        return ImageCandidate(
            url=url,
            alt=alt.strip() or "文章配图",
            source_url=url,
            image_type=image_type,
            reliability=reliability,
        )

    def _source_type(self, domain: str, path: str) -> str:
        if domain == "github.com":
            return "github"
        if "arxiv.org" in domain or "paper" in path:
            return "paper"
        if any(part in domain for part in ("docs.", "developer.", "dev.")):
            return "docs"
        if self._is_official_domain(domain):
            return "official"
        if any(part in domain for part in ("news", "theverge", "techcrunch", "wired")):
            return "media"
        return "web"

    def _source_reliability(self, domain: str, source_type: str) -> int:
        if self._is_suspicious_domain(domain):
            return 0
        scores = {
            "official": 90,
            "docs": 90,
            "paper": 85,
            "github": 80,
            "media": 65,
            "web": 50,
        }
        return scores.get(source_type, 50)

    def _needs_sources(self, text: str) -> bool:
        keywords = (
            "新闻",
            "日报",
            "最新",
            "发布",
            "价格",
            "榜单",
            "模型",
            "产品",
            "agent",
            "api",
            "today",
            "release",
        )
        return any(keyword in text for keyword in keywords)

    def _is_source_like(self, label: str, url: str) -> bool:
        text = f"{label} {url}".lower()
        markers = ("来源", "参考", "原文", "官方", "报道", "source", "reference")
        return any(marker in text for marker in markers)

    def _is_official_domain(self, domain: str) -> bool:
        return domain in OFFICIAL_AI_DOMAINS or any(
            domain.endswith("." + official) for official in OFFICIAL_AI_DOMAINS
        )

    def _is_suspicious_url(self, url: str) -> bool:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return self._is_suspicious_domain(domain)

    def _is_suspicious_domain(self, domain: str) -> bool:
        return domain in SUSPICIOUS_DOMAINS or ".invalid" in domain or domain.endswith(".test")

    def _normalize_url(self, url: str) -> str:
        return url.strip().strip("<>").rstrip(".,;，。；")

    def _chinese_length(self, text: str) -> int:
        return len(re.sub(r"\s+", "", text))
