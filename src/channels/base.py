from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChannelData:
    name: str
    url: str
    logo: str = ""
    group: str = "General"
    country_code: str = ""
    epg_id: Optional[str] = None
    chno: Optional[str] = None


@dataclass
class CountryGroup:
    name: str
    code: str
    channels: List[ChannelData] = field(default_factory=list)


@dataclass
class CategoryGroup:
    name: str
    channels: List[ChannelData] = field(default_factory=list)
