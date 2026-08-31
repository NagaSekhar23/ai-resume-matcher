from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .text_processing import normalize_text, split_sentences


@dataclass(frozen=True)
class SkillDefinition:
    canonical: str
    category: str
    aliases: tuple[str, ...]
    related: tuple[str, ...] = ()


SKILL_DEFINITIONS: tuple[SkillDefinition, ...] = (
    SkillDefinition("python", "programming_language", ("python", "py")),
    SkillDefinition("javascript", "programming_language", ("javascript", "js", "node.js", "nodejs"), ("typescript",)),
    SkillDefinition("typescript", "programming_language", ("typescript", "ts"), ("javascript",)),
    SkillDefinition("java", "programming_language", ("java",)),
    SkillDefinition("go", "programming_language", ("go", "golang")),
    SkillDefinition("c++", "programming_language", ("c++", "cpp")),
    SkillDefinition("sql", "programming_language", ("sql",)),
    SkillDefinition("react", "framework", ("react", "react.js", "reactjs", "next.js", "nextjs")),
    SkillDefinition("next.js", "framework", ("next.js", "nextjs")),
    SkillDefinition("fastapi", "framework", ("fastapi",)),
    SkillDefinition("django", "framework", ("django",)),
    SkillDefinition("flask", "framework", ("flask",)),
    SkillDefinition("node.js", "framework", ("node.js", "nodejs", "node")),
    SkillDefinition("express", "framework", ("express", "express.js")),
    SkillDefinition("spring boot", "framework", ("spring boot", "spring")),
    SkillDefinition("postgresql", "database", ("postgresql", "postgres", "psql")),
    SkillDefinition("mysql", "database", ("mysql",)),
    SkillDefinition("sqlite", "database", ("sqlite", "sqlite3")),
    SkillDefinition("mongodb", "database", ("mongodb", "mongo")),
    SkillDefinition("redis", "database", ("redis",)),
    SkillDefinition("aws", "cloud", ("aws", "amazon web services")),
    SkillDefinition("gcp", "cloud", ("gcp", "google cloud", "google cloud platform")),
    SkillDefinition("azure", "cloud", ("azure", "microsoft azure")),
    SkillDefinition("docker", "technology", ("docker", "containers", "containerization")),
    SkillDefinition("kubernetes", "technology", ("kubernetes", "k8s")),
    SkillDefinition("rest api", "technology", ("rest api", "restful api", "restful services", "rest services", "apis")),
    SkillDefinition("graphql", "technology", ("graphql",)),
    SkillDefinition("microservices", "technology", ("microservices", "microservice architecture")),
    SkillDefinition("git", "technology", ("git", "github", "gitlab")),
    SkillDefinition("ci/cd", "technology", ("ci/cd", "ci cd", "continuous integration", "continuous delivery")),
    SkillDefinition("machine learning", "technology", ("machine learning", "ml")),
    SkillDefinition("nlp", "technology", ("nlp", "natural language processing")),
    SkillDefinition("tailwind css", "framework", ("tailwind", "tailwind css")),
    SkillDefinition("html", "technology", ("html", "html5")),
    SkillDefinition("css", "technology", ("css", "css3")),
    SkillDefinition("testing", "technology", ("testing", "pytest", "unit tests", "integration tests", "jest", "vitest")),
)

SKILLS_BY_CANONICAL = {skill.canonical: skill for skill in SKILL_DEFINITIONS}
ALIAS_TO_SKILL: Dict[str, SkillDefinition] = {}
for definition in SKILL_DEFINITIONS:
    for alias in definition.aliases:
        ALIAS_TO_SKILL[normalize_text(alias)] = definition

REQUIRED_MARKERS = (
    "required",
    "must have",
    "must-have",
    "requirements",
    "minimum qualifications",
    "you have",
    "need",
)
PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "plus",
    "desired",
)


@dataclass(frozen=True)
class SkillMention:
    canonical: str
    category: str
    evidence: str
    section: str
    alias: str


@dataclass(frozen=True)
class ParsedJobDescription:
    title: Optional[str]
    description: str
    required_skills: list[str]
    preferred_skills: list[str]
    technologies: list[str]
    programming_languages: list[str]
    frameworks: list[str]
    databases: list[str]
    cloud_technologies: list[str]
    responsibilities: list[str]
    education_requirements: list[str]
    experience_requirements: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "technologies": self.technologies,
            "programming_languages": self.programming_languages,
            "frameworks": self.frameworks,
            "databases": self.databases,
            "cloud_technologies": self.cloud_technologies,
            "responsibilities": self.responsibilities,
            "education_requirements": self.education_requirements,
            "experience_requirements": self.experience_requirements,
        }


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(normalize_text(term))
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")


def find_skill_mentions(text: str, section: str = "general") -> List[SkillMention]:
    normalized_text = normalize_text(text)
    sentences = split_sentences(text) or [text]
    found: dict[str, SkillMention] = {}

    for alias, definition in sorted(ALIAS_TO_SKILL.items(), key=lambda item: len(item[0]), reverse=True):
        if not _term_pattern(alias).search(normalized_text):
            continue
        evidence = next((sentence for sentence in sentences if _term_pattern(alias).search(normalize_text(sentence))), text[:240])
        found.setdefault(
            definition.canonical,
            SkillMention(
                canonical=definition.canonical,
                category=definition.category,
                evidence=evidence,
                section=section,
                alias=alias,
            ),
        )
    return list(found.values())


def normalize_skill_name(value: str) -> str:
    normalized = normalize_text(value)
    if normalized in ALIAS_TO_SKILL:
        return ALIAS_TO_SKILL[normalized].canonical
    return normalized


def aliases_for_skill(skill_name: str) -> tuple[str, ...]:
    definition = SKILLS_BY_CANONICAL.get(normalize_skill_name(skill_name))
    return definition.aliases if definition else (skill_name,)


def categorize_skills(skills: Iterable[str]) -> dict[str, list[str]]:
    buckets = {
        "technologies": [],
        "programming_languages": [],
        "frameworks": [],
        "databases": [],
        "cloud_technologies": [],
    }
    for skill_name in skills:
        definition = SKILLS_BY_CANONICAL.get(skill_name)
        if not definition:
            continue
        if definition.category == "programming_language":
            buckets["programming_languages"].append(skill_name)
        elif definition.category == "framework":
            buckets["frameworks"].append(skill_name)
        elif definition.category == "database":
            buckets["databases"].append(skill_name)
        elif definition.category == "cloud":
            buckets["cloud_technologies"].append(skill_name)
        else:
            buckets["technologies"].append(skill_name)
    return {key: sorted(set(value)) for key, value in buckets.items()}


def parse_job_description(description: str, title: Optional[str] = None) -> ParsedJobDescription:
    cleaned = description.strip()
    if not cleaned:
        raise ValueError("Job description is required.")
    if len(cleaned.split()) < 8:
        raise ValueError("Job description is too short to analyze reliably.")

    sentences = split_sentences(cleaned)
    required: set[str] = set()
    preferred: set[str] = set()
    all_skills: set[str] = set()
    responsibilities: list[str] = []
    education: list[str] = []
    experience: list[str] = []

    for sentence in sentences:
        normalized = normalize_text(sentence)
        mentions = find_skill_mentions(sentence)
        sentence_skills = {mention.canonical for mention in mentions}
        all_skills.update(sentence_skills)

        is_preferred = any(marker in normalized for marker in PREFERRED_MARKERS)
        is_required = any(marker in normalized for marker in REQUIRED_MARKERS) or not is_preferred
        if is_preferred:
            preferred.update(sentence_skills)
        elif is_required:
            required.update(sentence_skills)

        if any(term in normalized for term in ("build", "design", "develop", "own", "collaborate", "maintain", "lead", "implement")):
            responsibilities.append(sentence)
        if any(term in normalized for term in ("degree", "bachelor", "master", "phd", "computer science", "education")):
            education.append(sentence)
        if re.search(r"\b\d+\+?\s*(years|yrs)\b", normalized) or "experience" in normalized:
            experience.append(sentence)

    preferred.difference_update(required)
    buckets = categorize_skills(all_skills)

    return ParsedJobDescription(
        title=title.strip() if title and title.strip() else None,
        description=cleaned,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        responsibilities=responsibilities[:12],
        education_requirements=education[:8],
        experience_requirements=experience[:8],
        **buckets,
    )


def related_skills(skill_name: str) -> tuple[str, ...]:
    definition = SKILLS_BY_CANONICAL.get(skill_name)
    return definition.related if definition else ()
