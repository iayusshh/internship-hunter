from scrapers.jobspy_scraper import scrape_jobspy_internships, scrape_jobspy_fulltime_remote
from scrapers.internshala_scraper import scrape_internshala
from scrapers.unstop_scraper import scrape_unstop
from scrapers.yc_scraper import scrape_yc
from scrapers.wellfound_scraper import scrape_wellfound
from scrapers.turing_scraper import scrape_turing
from scrapers.mercor_scraper import scrape_mercor

__all__ = [
    "scrape_jobspy_internships",
    "scrape_jobspy_fulltime_remote",
    "scrape_internshala",
    "scrape_unstop",
    "scrape_yc",
    "scrape_wellfound",
    "scrape_turing",
    "scrape_mercor",
]
