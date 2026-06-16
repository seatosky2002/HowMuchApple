from __future__ import annotations

from dataclasses import dataclass
from itertools import chain


@dataclass(frozen=True)
class CrawlTarget:
    category: str
    model: str
    released_year: int
    primary_keyword: str
    aliases: tuple[str, ...] = ()

    @property
    def keywords(self) -> tuple[str, ...]:
        return (self.primary_keyword, *self.aliases)


# 2022년 출시 모델을 포함한다. 각 target은 별도 검색 단위로 실행한다.
CRAWL_TARGETS: tuple[CrawlTarget, ...] = (
    # iPhone
    CrawlTarget("iPhone", "iPhone SE 3rd generation", 2022, "아이폰 SE 3세대", ("아이폰SE3", "iPhone SE 3", "iPhone SE 2022")),
    CrawlTarget("iPhone", "iPhone 14", 2022, "아이폰 14", ("아이폰14", "iPhone 14")),
    CrawlTarget("iPhone", "iPhone 14 Plus", 2022, "아이폰 14 플러스", ("아이폰14플러스", "아이폰14+", "iPhone 14 Plus")),
    CrawlTarget("iPhone", "iPhone 14 Pro", 2022, "아이폰 14 프로", ("아이폰14프로", "iPhone 14 Pro")),
    CrawlTarget("iPhone", "iPhone 14 Pro Max", 2022, "아이폰 14 프로맥스", ("아이폰14프로맥스", "아이폰 14 프로 맥스", "iPhone 14 Pro Max")),
    CrawlTarget("iPhone", "iPhone 15", 2023, "아이폰 15", ("아이폰15", "iPhone 15")),
    CrawlTarget("iPhone", "iPhone 15 Plus", 2023, "아이폰 15 플러스", ("아이폰15플러스", "아이폰15+", "iPhone 15 Plus")),
    CrawlTarget("iPhone", "iPhone 15 Pro", 2023, "아이폰 15 프로", ("아이폰15프로", "iPhone 15 Pro")),
    CrawlTarget("iPhone", "iPhone 15 Pro Max", 2023, "아이폰 15 프로맥스", ("아이폰15프로맥스", "아이폰 15 프로 맥스", "iPhone 15 Pro Max")),
    CrawlTarget("iPhone", "iPhone 16", 2024, "아이폰 16", ("아이폰16", "iPhone 16")),
    CrawlTarget("iPhone", "iPhone 16 Plus", 2024, "아이폰 16 플러스", ("아이폰16플러스", "아이폰16+", "iPhone 16 Plus")),
    CrawlTarget("iPhone", "iPhone 16 Pro", 2024, "아이폰 16 프로", ("아이폰16프로", "iPhone 16 Pro")),
    CrawlTarget("iPhone", "iPhone 16 Pro Max", 2024, "아이폰 16 프로맥스", ("아이폰16프로맥스", "아이폰 16 프로 맥스", "iPhone 16 Pro Max")),
    CrawlTarget("iPhone", "iPhone 16e", 2025, "아이폰 16e", ("아이폰16e", "iPhone 16e")),
    CrawlTarget("iPhone", "iPhone 17", 2025, "아이폰 17", ("아이폰17", "iPhone 17")),
    CrawlTarget("iPhone", "iPhone Air", 2025, "아이폰 에어", ("아이폰Air", "iPhone Air")),
    CrawlTarget("iPhone", "iPhone 17 Pro", 2025, "아이폰 17 프로", ("아이폰17프로", "iPhone 17 Pro")),
    CrawlTarget("iPhone", "iPhone 17 Pro Max", 2025, "아이폰 17 프로맥스", ("아이폰17프로맥스", "아이폰 17 프로 맥스", "iPhone 17 Pro Max")),
    CrawlTarget("iPhone", "iPhone 17e", 2026, "아이폰 17e", ("아이폰17e", "iPhone 17e")),

    # iPad
    CrawlTarget("iPad", "iPad Air 5th generation", 2022, "아이패드 에어 5세대", ("아이패드에어5", "iPad Air 5", "iPad Air M1")),
    CrawlTarget("iPad", "iPad 10th generation", 2022, "아이패드 10세대", ("아이패드10세대", "iPad 10th", "iPad 10세대")),
    CrawlTarget("iPad", "iPad Pro 11-inch 4th generation", 2022, "아이패드 프로 11 4세대", ("아이패드프로11 4세대", "iPad Pro 11 M2")),
    CrawlTarget("iPad", "iPad Pro 12.9-inch 6th generation", 2022, "아이패드 프로 12.9 6세대", ("아이패드프로12.9 6세대", "iPad Pro 12.9 M2")),
    CrawlTarget("iPad", "iPad Air 11-inch M2", 2024, "아이패드 에어 11 M2", ("아이패드에어11 M2", "iPad Air 11 M2")),
    CrawlTarget("iPad", "iPad Air 13-inch M2", 2024, "아이패드 에어 13 M2", ("아이패드에어13 M2", "iPad Air 13 M2")),
    CrawlTarget("iPad", "iPad Pro 11-inch M4", 2024, "아이패드 프로 11 M4", ("아이패드프로11 M4", "iPad Pro 11 M4")),
    CrawlTarget("iPad", "iPad Pro 13-inch M4", 2024, "아이패드 프로 13 M4", ("아이패드프로13 M4", "iPad Pro 13 M4")),
    CrawlTarget("iPad", "iPad mini A17 Pro", 2024, "아이패드 미니 A17Pro", ("아이패드미니 A17Pro", "아이패드 미니 7", "iPad mini A17 Pro")),
    CrawlTarget("iPad", "iPad A16", 2025, "아이패드 A16", ("아이패드 11세대", "iPad A16", "iPad 11th")),
    CrawlTarget("iPad", "iPad Air 11-inch M3", 2025, "아이패드 에어 11 M3", ("아이패드에어11 M3", "iPad Air 11 M3")),
    CrawlTarget("iPad", "iPad Air 13-inch M3", 2025, "아이패드 에어 13 M3", ("아이패드에어13 M3", "iPad Air 13 M3")),

    # MacBook
    CrawlTarget("MacBook", "MacBook Air 13-inch M2", 2022, "맥북 에어 M2 13인치", ("맥북에어 M2 13", "MacBook Air M2 13")),
    CrawlTarget("MacBook", "MacBook Pro 13-inch M2", 2022, "맥북 프로 M2 13인치", ("맥북프로 M2 13", "MacBook Pro M2 13")),
    CrawlTarget("MacBook", "MacBook Air 15-inch M2", 2023, "맥북 에어 M2 15인치", ("맥북에어 M2 15", "MacBook Air M2 15")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M2 Pro", 2023, "맥북 프로 14 M2 Pro", ("맥북프로14 M2 Pro", "MacBook Pro 14 M2 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M2 Pro", 2023, "맥북 프로 16 M2 Pro", ("맥북프로16 M2 Pro", "MacBook Pro 16 M2 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M2 Max", 2023, "맥북 프로 14 M2 Max", ("맥북프로14 M2 Max", "MacBook Pro 14 M2 Max")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M2 Max", 2023, "맥북 프로 16 M2 Max", ("맥북프로16 M2 Max", "MacBook Pro 16 M2 Max")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M3", 2023, "맥북 프로 14 M3", ("맥북프로14 M3", "MacBook Pro 14 M3")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M3 Pro", 2023, "맥북 프로 14 M3 Pro", ("맥북프로14 M3 Pro", "MacBook Pro 14 M3 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M3 Pro", 2023, "맥북 프로 16 M3 Pro", ("맥북프로16 M3 Pro", "MacBook Pro 16 M3 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M3 Max", 2023, "맥북 프로 14 M3 Max", ("맥북프로14 M3 Max", "MacBook Pro 14 M3 Max")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M3 Max", 2023, "맥북 프로 16 M3 Max", ("맥북프로16 M3 Max", "MacBook Pro 16 M3 Max")),
    CrawlTarget("MacBook", "MacBook Air 13-inch M3", 2024, "맥북 에어 M3 13인치", ("맥북에어 M3 13", "MacBook Air M3 13")),
    CrawlTarget("MacBook", "MacBook Air 15-inch M3", 2024, "맥북 에어 M3 15인치", ("맥북에어 M3 15", "MacBook Air M3 15")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M4", 2024, "맥북 프로 14 M4", ("맥북프로14 M4", "MacBook Pro 14 M4")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M4 Pro", 2024, "맥북 프로 14 M4 Pro", ("맥북프로14 M4 Pro", "MacBook Pro 14 M4 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M4 Pro", 2024, "맥북 프로 16 M4 Pro", ("맥북프로16 M4 Pro", "MacBook Pro 16 M4 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M4 Max", 2024, "맥북 프로 14 M4 Max", ("맥북프로14 M4 Max", "MacBook Pro 14 M4 Max")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M4 Max", 2024, "맥북 프로 16 M4 Max", ("맥북프로16 M4 Max", "MacBook Pro 16 M4 Max")),
    CrawlTarget("MacBook", "MacBook Air 13-inch M4", 2025, "맥북 에어 M4 13인치", ("맥북에어 M4 13", "MacBook Air M4 13")),
    CrawlTarget("MacBook", "MacBook Air 15-inch M4", 2025, "맥북 에어 M4 15인치", ("맥북에어 M4 15", "MacBook Air M4 15")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M5", 2026, "맥북 프로 14 M5", ("맥북프로14 M5", "MacBook Pro 14 M5")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M5 Pro", 2026, "맥북 프로 14 M5 Pro", ("맥북프로14 M5 Pro", "MacBook Pro 14 M5 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M5 Pro", 2026, "맥북 프로 16 M5 Pro", ("맥북프로16 M5 Pro", "MacBook Pro 16 M5 Pro")),
    CrawlTarget("MacBook", "MacBook Pro 14-inch M5 Max", 2026, "맥북 프로 14 M5 Max", ("맥북프로14 M5 Max", "MacBook Pro 14 M5 Max")),
    CrawlTarget("MacBook", "MacBook Pro 16-inch M5 Max", 2026, "맥북 프로 16 M5 Max", ("맥북프로16 M5 Max", "MacBook Pro 16 M5 Max")),

    # Apple Watch
    CrawlTarget("AppleWatch", "Apple Watch Series 8", 2022, "애플워치 8", ("애플워치8", "Apple Watch Series 8")),
    CrawlTarget("AppleWatch", "Apple Watch SE 2nd generation", 2022, "애플워치 SE2", ("애플워치 SE 2세대", "Apple Watch SE 2")),
    CrawlTarget("AppleWatch", "Apple Watch Ultra", 2022, "애플워치 울트라", ("Apple Watch Ultra",)),
    CrawlTarget("AppleWatch", "Apple Watch Series 9", 2023, "애플워치 9", ("애플워치9", "Apple Watch Series 9")),
    CrawlTarget("AppleWatch", "Apple Watch Ultra 2", 2023, "애플워치 울트라2", ("애플워치 울트라 2", "Apple Watch Ultra 2")),
    CrawlTarget("AppleWatch", "Apple Watch Series 10", 2024, "애플워치 10", ("애플워치10", "Apple Watch Series 10")),
    CrawlTarget("AppleWatch", "Apple Watch Series 11", 2025, "애플워치 11", ("애플워치11", "Apple Watch Series 11")),
    CrawlTarget("AppleWatch", "Apple Watch SE 3rd generation", 2025, "애플워치 SE3", ("애플워치 SE 3세대", "Apple Watch SE 3")),
    CrawlTarget("AppleWatch", "Apple Watch Ultra 3", 2025, "애플워치 울트라3", ("애플워치 울트라 3", "Apple Watch Ultra 3")),

    # AirPods
    CrawlTarget("AirPods", "AirPods Pro 2nd generation", 2022, "에어팟 프로 2세대", ("에어팟프로2", "AirPods Pro 2")),
    CrawlTarget("AirPods", "AirPods Pro 2nd generation USB-C", 2023, "에어팟 프로 2세대 C타입", ("에어팟프로2 C타입", "AirPods Pro 2 USB-C")),
    CrawlTarget("AirPods", "AirPods 4", 2024, "에어팟 4세대", ("에어팟4", "AirPods 4")),
    CrawlTarget("AirPods", "AirPods 4 ANC", 2024, "에어팟 4세대 노이즈캔슬링", ("에어팟4 ANC", "AirPods 4 ANC")),
    CrawlTarget("AirPods", "AirPods Max USB-C", 2024, "에어팟 맥스 USB-C", ("에어팟맥스 C타입", "AirPods Max USB-C")),
    CrawlTarget("AirPods", "AirPods Pro 3rd generation", 2025, "에어팟 프로 3세대", ("에어팟프로3", "AirPods Pro 3")),
)


def targets_for_category(category: str) -> tuple[CrawlTarget, ...]:
    return tuple(target for target in CRAWL_TARGETS if target.category == category)


def all_primary_keywords() -> tuple[str, ...]:
    return tuple(target.primary_keyword for target in CRAWL_TARGETS)


def all_search_keywords() -> tuple[str, ...]:
    return tuple(dict.fromkeys(chain.from_iterable(target.keywords for target in CRAWL_TARGETS)))


def target_counts_by_category() -> dict[str, int]:
    counts: dict[str, int] = {}
    for target in CRAWL_TARGETS:
        counts[target.category] = counts.get(target.category, 0) + 1
    return counts
