# build_graph_v2.py

# --- 0. 필요한 라이브러리 가져오기 ---
import os
import requests
import wikipediaapi
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import math
import json
from typing import List, Dict, Optional # 타입 힌트를 위해 추가
# Pydantic 모델 정의를 위해 추가
from pydantic import BaseModel, Field
# LLM API 라이브러리 (예: Google Gemini)
import google.generativeai as genai

# --- 1. 설정 및 초기화 ---
load_dotenv()
USER_AGENT = "HereStoryGo/1.0 (PythonApp; https://herestorygo.com)"

# --- LLM 및 API 설정 ---
# ❗❗ 사용자의 API 키로 변경하세요. (Gemini 예시)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found in .env file. LLM relationship extraction will be disabled.")
    # 실제 서비스에서는 키가 없으면 에러 처리 필요

# 사용할 LLM 모델 설정 (Gemini 예시)
# check_google_api.py에서 확인된 유효한 모델 이름으로 변경
LLM_MODEL_NAME = "models/gemini-pro-latest"

# LLM 호출 함수 (Google Gemini 예시)
def llm_call_json(prompt: str) -> Optional[Dict]:
    """주어진 프롬프트로 LLM을 호출하고 JSON 응답을 파싱합니다."""
    if not GOOGLE_API_KEY: return None # API 키 없으면 실행 안 함
    try:
        model = genai.GenerativeModel(LLM_MODEL_NAME)
        # JSON 모드 활성화 또는 후처리 필요 (Gemini API 따라 다름)
        # 참고: Gemini API는 직접적인 JSON 모드 지원이 제한적일 수 있음.
        # 출력에서 JSON 부분을 파싱하는 로직이 필요할 수 있음.
        response = model.generate_content(prompt)
        # --- 응답에서 JSON 파싱 ---
        # response.text에서 ```json ... ``` 부분을 찾아서 파싱
        json_part = response.text.strip()
        if json_part.startswith("```json"):
            json_part = json_part[7:]
        if json_part.endswith("```"):
            json_part = json_part[:-3]
        
        # 가끔 LLM이 잘못된 JSON을 반환할 수 있으므로 예외 처리
        try:
            return json.loads(json_part)
        except json.JSONDecodeError:
             print(f"  !! LLM response is not valid JSON:\n{response.text}")
             return None

    except Exception as e:
        print(f"  !! Error calling LLM API: {e}")
        return None

# --- 위키피디아 API 설정 ---
# 주 언어(프랑스어)와 보조 언어(영어) API 인스턴스를 각각 생성합니다.
# 모든 인자를 키워드 인자로 명시적으로 전달합니다.
wiki_api_fr = wikipediaapi.Wikipedia(
    language='fr',  # <-- 'language=' 추가
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT
)
wiki_api_en = wikipediaapi.Wikipedia(
    language='en',  # <-- 'language=' 추가
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT
)
PAGEVIEWS_ENDPOINT = "..." # 이전과 동일
MAX_LINKS_PER_NODE = 5

# --- 2. 헬퍼 함수 ---
def get_monthly_pageviews(page_title: str, lang: str) -> int:
    # ...(이전 코드와 동일)...
    today = datetime.now(timezone.utc)
    last_month = today - timedelta(days=30)
    start_date = last_month.strftime('%Y%m%d00')
    end_date = today.strftime('%Y%m%d00')
    try:
        title_formatted = page_title.replace(" ", "_")
        project_url = f"{lang}.wikipedia.org"
        url = PAGEVIEWS_ENDPOINT.format(
            project=project_url, access="all-access", agent="user",
            article=title_formatted, granularity="daily", start=start_date, end=end_date
        )
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        total_views = sum(item['views'] for item in data.get('items', []))
        return total_views
    except requests.RequestException:
        return 0

# --- Pydantic 모델 (LLM 출력 검증용 - 선택 사항이지만 권장) ---
# Pydantic을 사용하지 않으려면 이 부분과 llm_call_structured 함수 대신
# llm_call_json 함수와 간단한 딕셔너리 검증 로직을 사용해도 됩니다.
class Node(BaseModel):
    id: str
    label: str
    properties: Dict[str, str]

class Relationship(BaseModel):
    type: str
    start_node_id: str
    end_node_id: str
    properties: Optional[Dict] = Field(default_factory=dict)

class GraphResponse(BaseModel):
    nodes: List[Node]
    relationships: List[Relationship]

# --- 3. 핵심 로직: Wikipedia 그래프 빌더 클래스 ---
class WikipediaGraphBuilder:
    def __init__(self, driver):
        self.driver = driver
        self.processed_nodes = set()
        self.processed_relationships = set() # 관계 중복 생성 방지용

    def _get_or_create_node_with_stats(self, tx, title, lang):
        # ...(이전 코드와 동일)...
        tx.run("""
            MERGE (a:Article {title: $title, lang: $lang})
            ON CREATE SET a.createdAt = timestamp()
        """, title=title, lang=lang)

        node_key = f"{title}_{lang}"
        if node_key in self.processed_nodes:
            return

        print(f"  - Fetching stats for: {title} ({lang})")
        page_views = get_monthly_pageviews(title, lang=lang)

        tx.run("""
            MATCH (a:Article {title: $title, lang: $lang})
            MERGE (a)-[r:HAS_STATS]->(s:Stats)
            SET s.wiki_pageviews_30day = $views,
                s.last_updated = timestamp()
        """, title=title, lang=lang, views=page_views)

        self.processed_nodes.add(node_key)


    def _create_generic_relationship(self, tx, from_title, from_lang, to_title, to_lang, rel_type="LINKS_TO"):
        """두 노드 사이에 지정된 타입의 관계를 생성합니다 (LLM 실패 시 사용)."""
        # 관계 중복 체크
        rel_key_forward = f"{from_title}_{from_lang}-{rel_type}->{to_title}_{to_lang}"
        if rel_key_forward in self.processed_relationships:
            return
            
        print(f"    - Creating generic relationship: '{from_title}' -[:{rel_type}]-> '{to_title}'")
        tx.run(f"""
            MATCH (a:Article {{title: $from_title, lang: $from_lang}})
            MATCH (b:Article {{title: $to_title, lang: $to_lang}})
            MERGE (a)-[:{rel_type}]->(b)
        """, from_title=from_title, from_lang=from_lang, to_title=to_title, to_lang=to_lang)
        self.processed_relationships.add(rel_key_forward)


    def _get_page_summary(self, title, lang):
        """Helper to get page summary, returns None if not found."""
        try:
            wiki_api = self._get_wiki_api_instance(lang)
            page = wiki_api.page(title)
            # 요약이 너무 짧으면 유용하지 않으므로 길이 체크 추가
            return page.summary if page.exists() and len(page.summary) > 50 else None
        except Exception:
            return None


    # ❗❗ LLM 기반 관계 추출 함수 (핵심 수정)
    def _create_relationship_with_llm(self, tx, from_title, from_lang, to_title, to_lang):
        """LLM을 사용하여 두 노드 사이의 의미 관계를 결정하고 생성합니다."""
        # 관계 중복 체크 (어떤 타입이든 이미 관계가 있으면 생성 시도 안 함 - 단순화)
        # 좀 더 정교하게 하려면 특정 타입 관계만 체크
        rel_key_check = f"{from_title}_{from_lang}-->{to_title}_{to_lang}"
        if rel_key_check in self.processed_relationships:
            return

        print(f"    - Analyzing relationship: '{from_title}' ({from_lang}) -> '{to_title}' ({to_lang})")

        # LLM에 전달할 컨텍스트(요약) 가져오기
        from_summary = self._get_page_summary(from_title, from_lang)
        to_summary = self._get_page_summary(to_title, to_lang)

        # 요약 정보가 부족하면 LLM 호출 없이 기본 관계 생성
        if not from_summary or not to_summary:
            print("      -> Summaries insufficient for LLM. Creating generic LINKS_TO.")
            self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, "LINKS_TO")
            self.processed_relationships.add(rel_key_check) # 처리 기록
            return

        # 프롬프트 완성
        # ❗❗ 여기에 이전 채팅에서 정의한 HERE_STORY_GO_RELATIONSHIP_TEMPLATE 문자열이 필요합니다.
        # (길어서 생략. 이전 답변에서 복사하여 여기에 붙여넣으세요.)
        HERE_STORY_GO_RELATIONSHIP_TEMPLATE = """
# ROLE & GOAL
You are a highly intelligent knowledge graph construction algorithm...
... (이전 프롬프트 내용 전체 복사) ...
Now, analyze the following context and provide the JSON output:
Context:
- Entity A Title: {entity_A_title} ({entity_A_lang})
- Entity A Summary: {entity_A_summary}
- Entity B Title: {entity_B_title} ({entity_B_lang})
- Entity B Summary: {entity_B_summary}
"""
        formatted_prompt = HERE_STORY_GO_RELATIONSHIP_TEMPLATE.format(
            entity_A_title=from_title, entity_A_lang=from_lang, entity_A_summary=from_summary,
            entity_B_title=to_title, entity_B_lang=to_lang, entity_B_summary=to_summary
        )

        try:
            # LLM 호출하여 관계 추출 (llm_call_json 함수 사용)
            graph_response_dict = llm_call_json(formatted_prompt)

            # LLM 응답 유효성 검사 및 관계 생성
            if (graph_response_dict
                    and isinstance(graph_response_dict, dict)
                    and "relationships" in graph_response_dict
                    and isinstance(graph_response_dict["relationships"], list)
                    and len(graph_response_dict["relationships"]) > 0):

                rel = graph_response_dict["relationships"][0] # 첫 번째 관계만 사용
                rel_type = rel.get("type")

                # SCHEMA에 정의된 유효한 관계 타입인지 확인 (선택적이지만 권장)
                valid_rel_types = ["BORN_IN", "LIVED_IN", "DIED_IN", "FOUNDED", "DESIGNED",
                                   "PARTICIPATED_IN", "LED", "CREATED", "INFLUENCED_BY",
                                   "FEATURES", "IS_LOCATED_IN", "PART_OF", "LED_TO", "RELATED_TO"]

                if rel_type and rel_type in valid_rel_types:
                    print(f"      -> LLM identified relationship: {rel_type}")
                    # 추출된 의미 관계로 생성
                    self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, rel_type)
                else:
                    print(f"      -> LLM returned invalid or unspecified relationship type: '{rel_type}'. Creating generic LINKS_TO.")
                    self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, "LINKS_TO")
            else:
                 print("      -> LLM did not find a specific relationship structure. Creating generic LINKS_TO.")
                 self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, "LINKS_TO")

        except Exception as e:
            print(f"      -> Error during LLM relationship extraction: {e}. Creating generic LINKS_TO.")
            self._create_generic_relationship(tx, from_title, from_lang, to_title, to_lang, "LINKS_TO")
        
        finally:
             self.processed_relationships.add(rel_key_check) # 성공/실패 여부와 관계없이 처리 기록


    def _get_wiki_api_instance(self, lang):
         return wiki_api_fr if lang == 'fr' else wiki_api_en

    # ❗❗ explore_forwards 와 explore_backwards 함수 수정:
    # _create_relationship 대신 _create_relationship_with_llm 호출
    def explore_forwards(self, start_title, start_lang, max_depth=2):
        print(f"\n--- Starting Forward Exploration (out-going) from '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)]
        visited = {(start_title, start_lang)}

        with self.driver.session(database="neo4j") as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)
                if depth >= max_depth: continue
                print(f"\nExploring [Depth {depth+1}] links from '{current_title}' ({current_lang})")
                # ...(page.exists() 등 생략)...
                page = self._get_wiki_api_instance(current_lang).page(current_title)
                if not page.exists(): continue
                links_to_process = list(page.links.keys())[:MAX_LINKS_PER_NODE]
                print(f"  -> Found {len(links_to_process)} links...")
                for link_title in links_to_process:
                    link_lang = current_lang
                    if (link_title, link_lang) not in visited:
                        session.execute_write(self._get_or_create_node_with_stats, link_title, link_lang)
                        # --- 여기가 변경됨 ---
                        session.execute_write(self._create_relationship_with_llm, current_title, current_lang, link_title, link_lang)
                        # --- 변경 끝 ---
                        queue.append((link_title, link_lang, depth + 1))
                        visited.add((link_title, link_lang))

    def explore_backwards(self, start_title, start_lang, max_depth=2):
        print(f"\n--- Starting Backward Exploration (in-coming) to '{start_title}' ({start_lang}) ---")
        queue = [(start_title, start_lang, 0)]
        visited = {(start_title, start_lang)}
        with self.driver.session(database="neo4j") as session:
            while queue:
                current_title, current_lang, depth = queue.pop(0)
                session.execute_write(self._get_or_create_node_with_stats, current_title, current_lang)
                if depth >= max_depth: continue
                print(f"\nExploring backlinks [Depth {-depth-1}] to '{current_title}' ({current_lang})")
                # ...(백링크 API 호출 부분 생략)...
                api_url = f"https://{current_lang}.wikipedia.org/w/api.php"
                try:
                    params = { "action": "query", "format": "json", "list": "backlinks", "bltitle": current_title, "bllimit": MAX_LINKS_PER_NODE }
                    headers = {'User-Agent': USER_AGENT}
                    response = requests.get(api_url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    backlinks = [item['title'] for item in data.get('query', {}).get('backlinks', [])]
                    print(f"  -> Found {len(backlinks)} backlinks...")
                    for backlink_title in backlinks:
                        backlink_lang = current_lang
                        if (backlink_title, backlink_lang) not in visited:
                            session.execute_write(self._get_or_create_node_with_stats, backlink_title, backlink_lang)
                            # --- 여기가 변경됨 (방향 주의!) ---
                            session.execute_write(self._create_relationship_with_llm, backlink_title, backlink_lang, current_title, current_lang)
                            # --- 변경 끝 ---
                            queue.append((backlink_title, backlink_lang, depth + 1))
                            visited.add((backlink_title, backlink_lang))
                except requests.RequestException as e: print(f"  !! Error fetching backlinks: {e}")


    def find_top_paths(self, start_title, start_lang, max_depth=2, top_k=10):
        """
        시작 노드로부터 최대 깊이까지의 경로 중,
        경로상 노드들의 월간 조회수 합이 높은 상위 K개의 경로를 찾고 출력합니다.
        """
        print(f"\n--- Finding Top {top_k} paths (up to depth {max_depth}) from '{start_title}' ({start_lang}) based on summed pageviews ---")

        # ❗❗ 수정된 부분: f-string을 사용하여 max_depth 값을 쿼리 문자열에 직접 삽입
        cypher_query = f"""
        MATCH path = (start_node:Article {{title: $start_title, lang: $start_lang}})-[*0..{max_depth}]-(:Article)
        WITH nodes(path) AS path_nodes
        WHERE path_nodes[0].title = $start_title AND path_nodes[0].lang = $start_lang
        UNWIND range(0, size(path_nodes)-1) AS idx
        WITH path_nodes, idx, path_nodes[idx] AS node_in_path
        OPTIONAL MATCH (node_in_path)-[:HAS_STATS]->(stats)
        WITH path_nodes, collect({{title: node_in_path.title, lang: node_in_path.lang, depth: idx, views: coalesce(stats.wiki_pageviews_30day, 0)}}) AS details_list
        ORDER BY details_list[0].depth
        WITH details_list,
             reduce(totalViews = 0, nv IN details_list | totalViews + nv.views) AS total_path_views
        WHERE size(details_list) > 1
        RETURN details_list AS path_details, total_path_views
        ORDER BY total_path_views DESC
        LIMIT $top_k
        """
        # ❗❗ 수정 끝

        results = []
        try:
            with self.driver.session(database="neo4j") as session:
                # ❗ 파라미터에서 max_depth 제거 (이미 쿼리 문자열에 포함됨)
                result = session.run(cypher_query, start_title=start_title, start_lang=start_lang, top_k=top_k)
                results = result.data()

            # ...(이하 출력 로직은 동일)...
            if not results:
                print("  -> No paths found matching the criteria.")
                return

            print(f"\n--- Top {len(results)} Paths Found ---")
            for i, record in enumerate(results):
                path_details = record['path_details'] # 경로 노드 정보 리스트
                total_views = record['total_path_views'] # 경로 총 조회수
                path_str_list = []
                for node_info in path_details:
                    path_str_list.append(
                        f"{node_info['title']} ({node_info['depth']} depth, views: {node_info.get('views', 0)})"
                    )
                path_str = " - ".join(path_str_list) # 각 노드 정보를 " - "로 연결
                print(f"{i+1}. Score: {total_views}")
                print(f"   Path: {path_str}\n")

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

        # 1. 그래프 데이터 구축 (LLM 사용)
        print("Building graph data using LLM for relationships...")
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