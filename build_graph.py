# --- 0. 필요한 라이브러리 가져오기 ---
import os
import requests
import wikipediaapi
from neo4j import GraphDatabase
from dotenv import load_dotenv
# 파이썬 3.9 이상 버전에서 UTC 시간대를 올바르게 처리하기 위해 timezone을 import 합니다.
from datetime import datetime, timedelta, timezone

# --- 1. 설정 및 초기화 ---

# .env 파일에서 환경 변수(DB 비밀번호 등)를 로드합니다.
load_dotenv()

# 위키피디아에 요청 시 사용할 User-Agent를 상수로 정의합니다. (신원증 역할)
USER_AGENT = "HereStoryGo/1.0 (PythonApp; https://herestorygo.com)"

# 주 언어(프랑스어)와 보조 언어(영어) API 인스턴스를 각각 생성합니다.
# 모든 인자를 키워드(language=, user_agent=)로 명시하여 TypeError를 방지합니다.
wiki_api_fr = wikipediaapi.Wikipedia(
    language='fr',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT
)
wiki_api_en = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT
)

# 위키미디어 페이지뷰 API의 기본 주소를 정의합니다.
PAGEVIEWS_ENDPOINT = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}"
# 각 문서에서 탐색할 최대 링크 수를 제한하여 프로그램이 너무 오래 실행되는 것을 방지합니다.
MAX_LINKS_PER_NODE = 15

# --- 2. 헬퍼(도우미) 함수 ---

def get_monthly_pageviews(page_title: str, lang: str) -> int:
    """지정된 언어의 위키피디아 문서 최근 30일 조회수를 가져옵니다."""
    # 시간대 정보를 포함한 현재 UTC 시간을 가져옵니다. (Python 3.9+ 호환)
    today = datetime.now(timezone.utc)
    last_month = today - timedelta(days=30)
    start_date = last_month.strftime('%Y%m%d00')
    end_date = today.strftime('%Y%m%d00')
    try:
        title_formatted = page_title.replace(" ", "_")
        project_url = f"{lang}.wikipedia.org"
        # API 주소의 빈칸({ })을 실제 값으로 채웁니다.
        url = PAGEVIEWS_ENDPOINT.format(
            project=project_url, access="all-access", agent="user",
            article=title_formatted, granularity="daily", start=start_date, end=end_date
        )
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers)
        response.raise_for_status() # HTTP 오류가 발생하면 예외를 일으킵니다.
        data = response.json()
        total_views = sum(item['views'] for item in data.get('items', []))
        return total_views
    except requests.RequestException:
        return 0 # API 요청 실패 시 0을 반환합니다.

# --- 3. 핵심 로직: Wikipedia 그래프 빌더 클래스 ---

class WikipediaGraphBuilder:
    def __init__(self, driver):
        """클래스가 생성될 때 DB 드라이버를 저장하고, 처리된 노드 목록을 초기화합니다."""
        self.driver = driver
        self.processed_nodes = set() # 이번 실행에서 이미 처리한 노드를 기록하는 메모장

    def _get_or_create_node_with_stats(self, tx, title, lang):
        """
        노드를 생성/찾고, 통계 정보를 가져와 :Stats 노드를 연결합니다.
        """
        # MERGE를 사용하여 이미 노드가 존재하면 생성하지 않고 찾기만 합니다.
        tx.run("""
            MERGE (a:Article {title: $title, lang: $lang})
            ON CREATE SET a.createdAt = timestamp()
        """, title=title, lang=lang)
        
        node_key = f"{title}_{lang}"
        if node_key in self.processed_nodes:
            return # 메모장에 이미 있으면 API 호출을 건너뜁니다.

        print(f"  - Fetching stats for: {title} ({lang})")
        page_views = get_monthly_pageviews(title, lang=lang)
        
        # 통계 정보를 담을 :Stats 노드를 생성하고 :HAS_STATS 관계로 연결합니다.
        tx.run("""
            MATCH (a:Article {title: $title, lang: $lang})
            MERGE (a)-[r:HAS_STATS]->(s:Stats)
            SET s.wiki_pageviews_30day = $views,
                s.last_updated = timestamp()
        """, title=title, lang=lang, views=page_views)
        
        self.processed_nodes.add(node_key) # 메모장에 처리했다고 기록합니다.

    def _create_relationship(self, tx, from_title, from_lang, to_title, to_lang):
        """두 노드 사이에 :LINKS_TO 관계를 생성합니다."""
        tx.run("""
            MATCH (a:Article {title: $from_title, lang: $from_lang})
            MATCH (b:Article {title: $to_title, lang: $to_lang})
            MERGE (a)-[:LINKS_TO]->(b)
        """, from_title=from_title, from_lang=from_lang, to_title=to_title, to_lang=to_lang)

    def _get_wiki_api_instance(self, lang):
        """언어 코드에 맞는 wikipediaapi 인스턴스를 반환합니다."""
        return wiki_api_fr if lang == 'fr' else wiki_api_en

    def explore_forwards(self, start_title, start_lang, max_depth=2):
        """A -> B -> C (나아가는 관계)를 탐색합니다."""
        print(f"\n--- Starting Forward Exploration (out-going) from '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)] # (제목, 언어, 깊이)
        visited = {(start_title, start_lang)}

        with self.driver.session() as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)

                if depth >= max_depth: continue

                print(f"\nExploring [Depth {depth+1}] from '{current_title}' ({current_lang})")
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)

                wiki_api = self._get_wiki_api_instance(current_lang)
                page = wiki_api.page(current_title)

                if not page.exists():
                    print(f"  !! Page '{current_title}' ({current_lang}) not found. Skipping links.")
                    continue

                links_to_process = list(page.links.keys())[:MAX_LINKS_PER_NODE]
                print(f"  -> Found {len(links_to_process)} links ({current_lang}) to explore...")

                for link_title in links_to_process:
                    link_lang = current_lang # 단순화를 위해 같은 언어로 가정
                    if (link_title, link_lang) not in visited:
                        session.execute_write(self._get_or_create_node_with_stats, link_title, link_lang)
                        session.execute_write(self._create_relationship, current_title, current_lang, link_title, link_lang)
                        queue.append((link_title, link_lang, depth + 1))
                        visited.add((link_title, link_lang))

    def explore_backwards(self, start_title, start_lang, max_depth=2):
        """D -> A (들어오는 관계)를 탐색합니다."""
        print(f"\n--- Starting Backward Exploration (in-coming) to '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)]
        visited = {(start_title, start_lang)}
        
        with self.driver.session() as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)

                if depth >= max_depth: continue

                print(f"\nExploring backlinks [Depth {-depth-1}] to '{current_title}' ({current_lang})")
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)

                api_url = f"https://{current_lang}.wikipedia.org/w/api.php"
                try:
                    params = {
                        "action": "query", "format": "json", "list": "backlinks",
                        "bltitle": current_title, "bllimit": MAX_LINKS_PER_NODE,
                    }
                    headers = {'User-Agent': USER_AGENT}
                    response = requests.get(api_url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    backlinks = [item['title'] for item in data.get('query', {}).get('backlinks', [])]

                    print(f"  -> Found {len(backlinks)} backlinks ({current_lang}) to explore...")

                    for backlink_title in backlinks:
                        backlink_lang = current_lang
                        if (backlink_title, backlink_lang) not in visited:
                            session.execute_write(self._get_or_create_node_with_stats, backlink_title, backlink_lang)
                            # 관계 방향: (Backlink) -> (Current)
                            session.execute_write(self._create_relationship, backlink_title, backlink_lang, current_title, current_lang)
                            queue.append((backlink_title, backlink_lang, depth + 1))
                            visited.add((backlink_title, backlink_lang))
                except requests.RequestException as e:
                    print(f"  !! Could not fetch backlinks for '{current_title}' ({current_lang}): {e}")

# --- 4. 메인 실행 블록 ---
if __name__ == "__main__":
    URI = os.getenv("NEO4J_URI")
    AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    driver = None
    try:
        # DB 드라이버 생성 및 연결 확인
        driver = GraphDatabase.driver(URI, auth=AUTH)
        driver.verify_connectivity()
        print("Successfully connected to Neo4j AuraDB.")

        builder = WikipediaGraphBuilder(driver)

        # ❗ 시작 노드를 내용이 풍부한 프랑스어("fr") 페이지로 명확히 지정
        start_node_title = "Parc des Bastions"
        start_node_lang = "fr"
        # 탐색 깊이 (0->1->2차, 0->-1->-2차 이므로 2로 설정)
        exploration_depth = 2

        # 1. 프랑스어 페이지에서 뻗어나가는 탐색 시작
        builder.explore_forwards(start_node_title, start_node_lang, exploration_depth)

        # 2. 프랑스어 페이지로 들어오는 탐색 시작
        builder.explore_backwards(start_node_title, start_node_lang, exploration_depth)

        print("\nGraph construction complete!")
        print("Check your Neo4j AuraDB Browser to see the results.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 모든 작업이 끝나면 DB 연결을 안전하게 닫습니다.
        if driver:
            driver.close()
            print("\nNeo4j connection closed.")