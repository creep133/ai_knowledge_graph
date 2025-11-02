# build_graph_v4.py

# --- 0. 필요한 라이브러리 가져오기 ---
import os
import requests
import wikipediaapi
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import re # 정규표현식 라이브러리 (링크 필터링용)
import json # LLM 응답 파싱용
from typing import List, Dict, Optional
# Pydantic 은 LLM 응답 검증에 유용하지만, 여기서는 단순화를 위해 제외합니다.
# from pydantic import BaseModel, Field
# 사용할 LLM 라이브러리 (Gemini 예시)
import google.generativeai as genai

# --- 1. 설정 및 초기화 ---
load_dotenv()
USER_AGENT = "HereStoryGo/1.0 (PythonApp; https://herestorygo.com)"

# --- LLM 및 API 설정 ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        LLM_MODEL_NAME = "models/gemini-pro-latest" # 유효한 모델 이름 사용
        print(f"Google Generative AI configured with model: {LLM_MODEL_NAME}")
    except Exception as e:
        print(f"Error configuring Google Generative AI: {e}")
        GOOGLE_API_KEY = None # 오류 발생 시 LLM 비활성화
else:
    print("Warning: GOOGLE_API_KEY not found. LLM relationship extraction will be disabled.")

# --- 위키피디아 API 설정 ---
# 모든 인자를 키워드 인자로 명시
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
PAGEVIEWS_ENDPOINT = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}"
# 필터링 전후 고려하여 링크 처리 개수 설정
MAX_LINKS_TO_FETCH = 30 # 필터링 전 가져올 최대 링크 수
MAX_LINKS_PER_NODE = 5 # 필터링 후 실제 처리할 최대 링크 수
MIN_SUMMARY_LENGTH = 50 # LLM 호출을 위한 최소 요약 길이

# --- LLM 호출 함수 ---
def llm_call_json(prompt: str) -> Optional[Dict]:
    """주어진 프롬프트로 LLM을 호출하고 JSON 응답을 파싱합니다."""
    if not GOOGLE_API_KEY: return None
    try:
        model = genai.GenerativeModel(LLM_MODEL_NAME)
        # 참고: 최신 Gemini API는 JSON 모드나 더 나은 출력 제어 옵션을 제공할 수 있습니다.
        # 문서를 확인하여 response.text 대신 구조화된 출력을 얻는 방법을 사용하는 것이 좋습니다.
        response = model.generate_content(prompt)

        # 응답 텍스트에서 JSON 부분 추출 시도 (간단 버전)
        text_response = response.text.strip()
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text_response, re.DOTALL)
        if json_match:
            json_part = json_match.group(1)
        elif text_response.startswith('{') and text_response.endswith('}'): # 마크다운 없을 경우
             json_part = text_response
        else:
            print(f"  !! LLM response did not contain expected JSON format:\n{text_response}")
            return None

        try:
            return json.loads(json_part)
        except json.JSONDecodeError as json_err:
             print(f"  !! LLM response JSON parsing failed: {json_err}\nOriginal text:\n{json_part}")
             return None

    except Exception as e:
        # API 호출 관련 오류 처리 (예: RateLimitError, APIError 등)
        print(f"  !! Error calling LLM API: {type(e).__name__} - {e}")
        return None

# --- 2. 헬퍼 함수 ---
def get_monthly_pageviews(page_title: str, lang: str) -> int:
    """지정된 언어의 위키피디아 문서 최근 30일 조회수를 가져옵니다 (디버깅 추가)."""
    today = datetime.now(timezone.utc)
    last_month = today - timedelta(days=30)
    start_date = last_month.strftime('%Y%m%d') # YYYYMMDD 형식
    end_date = today.strftime('%Y%m%d')       # YYYYMMDD 형식
    total_views = 0
    try:
        import urllib.parse
        title_formatted = page_title.replace(" ", "_")
        title_url_encoded = urllib.parse.quote(title_formatted)
        project_url = f"{lang}.wikipedia.org"
        url = PAGEVIEWS_ENDPOINT.format(
            project=project_url, access="all-access", agent="user",
            article=title_url_encoded, granularity="daily",
            start=start_date, end=end_date
        )
        headers = {'User-Agent': USER_AGENT}
        print(f"    - Requesting pageviews: {url}") # 디버깅
        response = requests.get(url, headers=headers, timeout=10)
        print(f"    - Pageviews API status code: {response.status_code}") # 디버깅
        response.raise_for_status()
        data = response.json()
        total_views = sum(item['views'] for item in data.get('items', []))
        print(f"    - Fetched views: {total_views}") # 디버깅
        return total_views
    except requests.Timeout:
        print(f"    !! Timeout fetching pageviews for '{page_title}' ({lang}). Returning 0.")
        return 0
    except requests.RequestException as e:
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
            print(f"    - Pageviews API returned 404 for '{page_title}' ({lang}). Assuming 0 views.")
            return 0
        else:
            print(f"    !! Error fetching pageviews for '{page_title}' ({lang}): {e}. Returning 0.")
            return 0

# --- 링크 필터링 함수 ---
def is_meaningful_link(title: str) -> bool:
    """단순 연도, 날짜, 일반 목록, 메타 페이지 등 의미 없는 링크인지 판단합니다."""
    title_lower = title.lower()
    # 단순 숫자 (연도) - 4자리 초과 숫자도 제외 (예: 전화번호 등)
    if re.fullmatch(r'\d{1,}', title):
        return False
    # 날짜 패턴 (다양한 언어 고려 필요 - 프랑스어 예시)
    if re.fullmatch(r'\d{1,2}(er)?\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novémbre|décembre)', title_lower):
        return False
    # 'YYYY in X', 'Month YYYY', 'YYYY en X' 등 패턴
    if re.search(r'\b\d{4}\b', title) and (' in ' in title_lower or ' en ' in title_lower or ' siècle' in title_lower):
         return False
    # 목록 페이지
    if title_lower.startswith("list of") or title_lower.startswith("liste de") or title_lower.startswith("index of") or title_lower.startswith("timeline of"):
        return False
    # 위키백과 관리 페이지 (Category는 제외)
    if ':' in title and not title_lower.startswith('category:'):
        # Allow common exceptions like 'COVID-19 pandemic'
        if not re.match(r'^[a-zA-Z]+:', title): # Check if prefix is likely a namespace
             return True # If colon is part of the title itself, allow it for now
        return False
    # 동음이의어 해소 페이지
    if title.endswith("(disambiguation)") or title.endswith("(homonymie)"):
        return False
    # 파일/이미지 페이지
    if title_lower.startswith("file:") or title_lower.startswith("image:") or title_lower.startswith("fichier:"):
        return False
    return True

# --- 3. 핵심 로직: Wikipedia 그래프 빌더 클래스 ---
class WikipediaGraphBuilder:
    def __init__(self, driver):
        self.driver = driver
        # 처리된 노드/관계를 기록하여 중복 작업 방지
        self.processed_nodes = set() # (title, lang) 튜플 저장
        self.processed_relationships = set() # (from_title, from_lang, to_title, to_lang) 튜플 저장

    # DB에 노드 생성/업데이트 및 통계 저장
    def _get_or_create_node_with_stats(self, tx, title, lang):
        node_key = (title, lang)
        if node_key in self.processed_nodes: return

        print(f"  - Processing Node: {title} ({lang})")
        # 노드 생성/확인
        tx.run("MERGE (a:Article {title: $title, lang: $lang}) ON CREATE SET a.createdAt = timestamp()",
               title=title, lang=lang)

        # 통계 정보 가져오기
        page_views = get_monthly_pageviews(title, lang=lang)

        # 통계 노드 생성/업데이트 및 연결
        tx.run("""
            MATCH (a:Article {title: $title, lang: $lang})
            MERGE (a)-[r:HAS_STATS]->(s:Stats)
            SET s.wiki_pageviews_30day = $views, s.last_updated = timestamp()
        """, title=title, lang=lang, views=page_views)

        self.processed_nodes.add(node_key)

    # 기본 관계 생성 함수 (LLM 실패 시 사용)
    def _create_generic_relationship(self, tx, from_title, from_lang, to_title, to_lang, rel_type="LINKS_TO"):
        rel_key = (from_title, from_lang, to_title, to_lang)
        if rel_key in self.processed_relationships: return

        print(f"    - Creating Relationship: '{from_title}' -[:{rel_type}]-> '{to_title}'")
        tx.run(f"""
            MATCH (a:Article {{title: $from_title, lang: $from_lang}})
            MATCH (b:Article {{title: $to_title, lang: $to_lang}})
            MERGE (a)-[:{rel_type}]->(b)
        """, from_title=from_title, from_lang=from_lang, to_title=to_title, to_lang=to_lang)
        self.processed_relationships.add(rel_key)

    # 위키 페이지 요약 가져오기
    def _get_page_summary(self, title, lang):
        try:
            wiki_api = self._get_wiki_api_instance(lang)
            page = wiki_api.page(title)
            return page.summary if page.exists() and len(page.summary) > MIN_SUMMARY_LENGTH else None
        except Exception as e:
            print(f"    !! Error getting summary for '{title}' ({lang}): {e}")
            return None

    # LLM 기반 관계 추출 함수
    def _create_relationship_with_llm(self, tx, from_title, from_lang, to_title, to_lang):
        rel_key = (from_title, from_lang, to_title, to_lang)
        if rel_key in self.processed_relationships: return

        print(f"    - Analyzing relationship: '{from_title}' ({from_lang}) -> '{to_title}' ({to_lang})")
        from_summary = self._get_page_summary(from_title, from_lang)
        to_summary = self._get_page_summary(to_title, to_lang)

        if not from_summary or not to_summary:
            print("      -> Summaries insufficient. Creating generic LINKS_TO.")
            self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, "LINKS_TO")
            return

        # ❗❗ 여기에 이전 채팅에서 정의한 HERE_STORY_GO_RELATIONSHIP_TEMPLATE 문자열이 필요합니다.
        # (길어서 생략. 프롬프트 내용을 여기에 복사하세요.)
        # 프롬프트에 MENTIONS_DATE 관련 지침 포함 확인
        HERE_STORY_GO_RELATIONSHIP_TEMPLATE = """
# ROLE & GOAL
You are a highly intelligent knowledge graph construction algorithm...
... (이전 프롬프트 내용 전체 복사) ...
# Specific Instructions for HereStoryGo:
# - If Entity B is primarily a year (e.g., '1817') or a date (e.g., '1er août'),
#   use the relationship type 'MENTIONS_DATE'.
...
Now, analyze the following context and provide the JSON output:
Context:
- Entity A Title: {entity_A_title} ({entity_A_lang})
- Entity A Summary: {entity_A_summary}
- Entity B Title: {entity_B_title} ({entity_B_lang})
- Entity B Summary: {entity_B_summary}
"""
        # (SCHEMA 부분에도 MENTIONS_DATE: (Any) -> (Article) 정의 필요)
        formatted_prompt = HERE_STORY_GO_RELATIONSHIP_TEMPLATE.format(
            entity_A_title=from_title, entity_A_lang=from_lang, entity_A_summary=from_summary,
            entity_B_title=to_title, entity_B_lang=to_lang, entity_B_summary=to_summary
        )

        rel_type = "LINKS_TO" # 기본 fallback 타입
        try:
            graph_response_dict = llm_call_json(formatted_prompt) # LLM 호출

            if (graph_response_dict and isinstance(graph_response_dict, dict) and
                "relationships" in graph_response_dict and isinstance(graph_response_dict["relationships"], list) and
                len(graph_response_dict["relationships"]) > 0):

                llm_rel = graph_response_dict["relationships"][0]
                llm_rel_type = llm_rel.get("type")

                # SCHEMA에 정의된 유효한 타입 리스트 (MENTIONS_DATE 추가)
                valid_rel_types = ["BORN_IN", "LIVED_IN", "DIED_IN", "FOUNDED", "DESIGNED",
                                   "PARTICIPATED_IN", "LED", "CREATED", "INFLUENCED_BY",
                                   "FEATURES", "IS_LOCATED_IN", "PART_OF", "LED_TO",
                                   "MENTIONS_DATE", # 추가된 타입
                                   "RELATED_TO"] # 일반 타입

                if llm_rel_type and llm_rel_type in valid_rel_types:
                    print(f"      -> LLM identified relationship: {llm_rel_type}")
                    rel_type = llm_rel_type # LLM이 찾은 유효한 타입 사용
                else:
                     print(f"      -> LLM returned invalid type '{llm_rel_type}'. Using LINKS_TO.")
            else:
                 print("      -> LLM response structure invalid. Using LINKS_TO.")

        except Exception as e:
            print(f"      -> Error during LLM process: {e}. Using LINKS_TO.")

        finally:
            # 최종 결정된 타입으로 관계 생성
             self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, rel_type)


    def _get_wiki_api_instance(self, lang):
         return wiki_api_fr if lang == 'fr' else wiki_api_en

    # 나아가는 탐색 함수 (링크 필터링 적용)
    def explore_forwards(self, start_title, start_lang, max_depth=2):
        print(f"\n--- Starting Forward Exploration from '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)]
        visited = {(start_title, start_lang)}

        with self.driver.session(database="neo4j") as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)
                # 현재 노드 처리 (depth 0, 1, 2 모두 처리)
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)

                if depth >= max_depth: continue # 최대 깊이 도달 시 링크 탐색 안 함

                print(f"\nExploring [Depth {depth+1}] links from '{current_title}' ({current_lang})")
                wiki_api = self._get_wiki_api_instance(current_lang)
                page = wiki_api.page(current_title)

                if not page.exists(): continue

                # 링크 가져오기 (필터링 위해 더 많이 가져옴)
                all_links = list(page.links.keys())[:MAX_LINKS_TO_FETCH]
                # --- 링크 필터링 ---
                meaningful_links = [link for link in all_links if is_meaningful_link(link)]
                links_to_process = meaningful_links[:MAX_LINKS_PER_NODE]
                print(f"  -> Found {len(links_to_process)} meaningful links (filtered from {len(all_links)})...")
                # --- 필터링 끝 ---

                for link_title in links_to_process:
                    link_lang = current_lang
                    if (link_title, link_lang) not in visited:
                        # 다음 노드 생성/업데이트
                        session.execute_write(self._get_or_create_node_with_stats, link_title, link_lang)
                        # LLM으로 관계 생성
                        session.execute_write(self._create_relationship_with_llm, current_title, current_lang, link_title, link_lang)
                        # 큐에 추가 및 방문 기록
                        queue.append((link_title, link_lang, depth + 1))
                        visited.add((link_title, link_lang))

    # 들어오는 탐색 함수 (백링크 필터링 적용)
    def explore_backwards(self, start_title, start_lang, max_depth=2):
        print(f"\n--- Starting Backward Exploration to '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)]
        visited = {(start_title, start_lang)}
        with self.driver.session(database="neo4j") as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)
                if depth >= max_depth: continue

                print(f"\nExploring backlinks [Depth {-depth-1}] to '{current_title}' ({current_lang})")
                api_url = f"https://{current_lang}.wikipedia.org/w/api.php"
                try:
                    params = { "action": "query", "format": "json", "list": "backlinks", "bltitle": current_title, "bllimit": MAX_LINKS_TO_FETCH } # 더 많이 요청
                    headers = {'User-Agent': USER_AGENT}
                    response = requests.get(api_url, params=params, headers=headers, timeout=15) # 타임아웃 증가
                    response.raise_for_status()
                    data = response.json()
                    all_backlinks = [item['title'] for item in data.get('query', {}).get('backlinks', [])]
                    # --- 백링크 필터링 ---
                    meaningful_backlinks = [link for link in all_backlinks if is_meaningful_link(link)]
                    backlinks_to_process = meaningful_backlinks[:MAX_LINKS_PER_NODE]
                    print(f"  -> Found {len(backlinks_to_process)} meaningful backlinks (filtered from {len(all_backlinks)})...")
                    # --- 필터링 끝 ---

                    for backlink_title in backlinks_to_process:
                        backlink_lang = current_lang
                        if (backlink_title, backlink_lang) not in visited:
                            session.execute_write(self._get_or_create_node_with_stats, backlink_title, backlink_lang)
                            # LLM으로 관계 생성 (방향 주의!)
                            session.execute_write(self._create_relationship_with_llm, backlink_title, backlink_lang, current_title, current_lang)
                            queue.append((backlink_title, backlink_lang, depth + 1))
                            visited.add((backlink_title, backlink_lang))
                except requests.Timeout: print(f"  !! Timeout fetching backlinks for '{current_title}' ({current_lang}).")
                except requests.RequestException as e: print(f"  !! Error fetching backlinks: {e}")

    # 상위 경로 찾는 함수 (이전과 동일)
    def find_top_paths(self, start_title, start_lang, max_depth=2, top_k=10):
        print(f"\n--- Finding Top {top_k} paths (up to depth {max_depth}) from '{start_title}' ({start_lang}) based on summed pageviews ---")
        # f-string으로 max_depth 삽입
        cypher_query = f"""
        MATCH path = (start_node:Article {{title: $start_title, lang: $start_lang}})-[*0..{max_depth}]-(:Article)
        WITH nodes(path) AS path_nodes
        WHERE path_nodes[0].title = $start_title AND path_nodes[0].lang = $start_lang
        UNWIND range(0, size(path_nodes)-1) AS idx
        WITH path_nodes, idx, path_nodes[idx] AS node_in_path
        OPTIONAL MATCH (node_in_path)-[:HAS_STATS]->(stats)
        WITH path_nodes, collect({{title: node_in_path.title, lang: node_in_path.lang, depth: idx, views: coalesce(stats.wiki_pageviews_30day, 0)}}) AS details_list
        // ORDER BY details_list[0].depth 는 COLLECT 전에 해야 의미가 있음. idx 기준으로 정렬됨.
        WITH details_list,
             reduce(totalViews = 0, nv IN details_list | totalViews + nv.views) AS total_path_views
        WHERE size(details_list) > 1
        RETURN details_list AS path_details, total_path_views
        ORDER BY total_path_views DESC
        LIMIT $top_k
        """
        results = []
        try:
            with self.driver.session(database="neo4j") as session:
                # 파라미터에서 max_depth 제거됨
                result = session.run(cypher_query, start_title=start_title, start_lang=start_lang, top_k=top_k)
                results = result.data()

            if not results:
                print("  -> No paths found matching the criteria.")
                return

            print(f"\n--- Top {len(results)} Paths Found ---")
            for i, record in enumerate(results):
                path_details = record['path_details']
                total_views = record['total_path_views']
                path_str_list = [f"{n['title']} ({n['depth']}d, v:{n.get('views', 0)})" for n in path_details]
                path_str = " - ".join(path_str_list)
                print(f"{i+1}. Score: {total_views}\n   Path: {path_str}\n")
        except exceptions.CypherSyntaxError as e:
            print(f"  !! Cypher query error in find_top_paths: {e}")
        except Exception as e:
            print(f"  !! An error occurred during path finding: {e}")


# --- 4. 메인 실행 블록 ---
if __name__ == "__main__":
    URI = os.getenv("NEO4J_URI")
    AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    driver = None
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        driver.verify_connectivity()
        print("Successfully connected to Neo4j AuraDB.")
        builder = WikipediaGraphBuilder(driver)
        start_node_title = "Parc des Bastions"
        start_node_lang = "fr"
        exploration_depth = 2

        # 1. 그래프 데이터 구축 (LLM 사용, 링크 필터링 적용)
        print("Building graph data (filtered links, LLM relationships)...")
        # 기존 데이터 삭제 (선택 사항 - 개발 시 유용)
        # print("Clearing existing data...")
        # with driver.session(database="neo4j") as session:
        #     session.run("MATCH (n) DETACH DELETE n")
        # print("Existing data cleared.")

        builder.explore_forwards(start_node_title, start_node_lang, exploration_depth)
        builder.explore_backwards(start_node_title, start_node_lang, exploration_depth)
        print("\nGraph construction attempt complete!")

        # 2. 구축된 그래프에서 상위 경로 찾기
        builder.find_top_paths(start_node_title, start_node_lang, max_depth=exploration_depth, top_k=10)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if driver:
            driver.close()
            print("\nNeo4j connection closed.")