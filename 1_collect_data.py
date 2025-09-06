import json
import re
from typing import List
import requests
from bs4 import BeautifulSoup


def fetch_episode(link: str) -> List[dict]:

    """위키피디아의 에피소드 데이터 수집하기"""
    season = int(re.search(r"season_(\d+)", link).group(1))
    print(f"Fetching Season {season} from: {link}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(link, headers=headers)
    
    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.select_one("table.wikitable.plainrowheaders.wikiepisodetable")

    episodes = []
    rows = table.select("tr.vevent.module-episode-list-row")

    for i, row in enumerate(rows, start=1):
        synopsis = None
        synopsis_row = row.find_next_sibling("tr", class_="expand-child")
        if synopsis_row:
            synopsis_cell = synopsis_row.select_one("td.description div.shortSummaryText")

            synopsis = synopsis_cell.get_text(strip=True) if synopsis_cell else None

        episodes.append({
            "season": season,
            "episode_in_season": i,
            "synopsis": synopsis,
        })
    
    return episodes


def main() -> None:
    """여러 시즌의 에피소드를 가져와서 하나의 JSON 파일로 데이터 수집"""
    episode_links = [
        "https://en.wikipedia.org/wiki/Attack_on_Titan_season_1",
        # "https://en.wikipedia.org/wiki/Attack_on_Titan_season_2",
        # "https://en.wikipedia.org/wiki/Attack_on_Titan_season_3",
        # "https://en.wikipedia.org/wiki/Attack_on_Titan_season_4",
    ]
    
    all_episodes = []
    for link in episode_links:
        episodes = fetch_episode(link)
        all_episodes.extend(episodes)
    
    output_file = "output/1_원본데이터.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_episodes, f, indent=2, ensure_ascii=False)
    
    print ("데이터 수집이 완료되었습니다")


if __name__ == "__main__":
    main()
