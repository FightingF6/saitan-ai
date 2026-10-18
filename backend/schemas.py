from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Filters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    major: str = Field('', max_length=80)
    grade: str = Field('大一', max_length=20)
    category: str = Field('人工智能', max_length=60)
    participation: str = Field('不限', max_length=30)
    region: str = Field('全国', max_length=60)
    status: str = Field('报名中优先', max_length=30)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(min_length=5, max_length=1500)
    filters: Filters = Field(default_factory=Filters)


class Evidence(BaseModel):
    field: str = Field(max_length=60)
    quote: str = Field(min_length=2, max_length=1000)
    source_url: HttpUrl


class Candidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=200, description='Exact contiguous competition name copied from the page and name evidence quote. Do not append a track, parentheses, or explanation.')
    edition: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=80)
    description: str | None = Field(None, max_length=1000, description='Short verbatim excerpt from the page, not a paraphrase. Null if unavailable.')
    organizer: str | None = Field(None, max_length=200)
    eligible_grades: str | None = Field(None, max_length=300, description='Exact eligibility wording from the page. Never add inferred eligibility such as freshmen allowed.')
    eligible_majors: str | None = Field(None, max_length=300)
    participation_type: str | None = Field(None, max_length=100)
    team_size: str | None = Field(None, max_length=100)
    registration_start: date | None = None
    registration_deadline: date | None = None
    official_url: HttpUrl | None = None
    source_urls: list[HttpUrl] = Field(min_length=1, max_length=8)
    source_published_at: date | None = None
    evidence: list[Evidence] = Field(min_length=1, max_length=30)


class AgentResult(BaseModel):
    competitions: list[Candidate] = Field(default_factory=list, max_length=20)
