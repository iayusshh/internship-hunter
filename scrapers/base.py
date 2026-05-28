from typing import TypedDict, Literal, Optional
from abc import ABC, abstractmethod

JobType = Literal["internship", "full_time_remote", "hackathon"]


class JobDict(TypedDict, total=False):
    title:       str
    company:     str
    location:    str
    url:         str
    source:      str
    job_type:    JobType
    stipend:     str
    salary:      str
    min_amount:  Optional[float]
    max_amount:  Optional[float]
    currency:    str
    date_posted: str
    paid:        Optional[bool]
    is_remote:   Optional[bool]


class BaseScraper(ABC):
    SOURCE_NAME: str = ""

    @abstractmethod
    def scrape(self) -> list[JobDict]: ...
