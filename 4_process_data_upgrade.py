
import json
from typing import List
from utils import  GraphResponse, combine_chunk_graphs, llm_call_structured, UPDATED_TEMPLATE


# 노드 이름 한글 매핑
KOREAN_NODE_MAP = {
    "Eren Jaeger": "에렌 예거",
    "Mikasa Ackerman": "미카사 아커만",
    "Armin Arlert": "아르민 알레르트", 
    "Levi Ackerman": "리바이 아커만",
    "Erwin Smith": "에르빈 스미스",
    "Hange Zoë": "한지 조에",
    "Jean Kirstein": "장 키르슈타인",
    "Reiner Braun": "라이너 브라운",
    "Bertholdt Hoover": "베르톨트 후버",
    "Annie Leonhart": "애니 레온하트",
    "Grisha Jaeger": "그리샤 예거",
    "Female Titan": "여성형 거인",
    "Eren's Titan": "진격의 거인",
    "Colossal Titan": "초대형 거인",
    "Armored Titan": "갑옷 거인"
}

if __name__ == "__main__":
    

    with open("output/1_원본데이터.json", encoding="utf-8") as f:
        episodes = json.load(f)

    chunk_graphs: List[GraphResponse] = []
    
    for episode in episodes:
        print(f"에피소드 처리 중: 시즌 {episode["season"]}, 에피소드 {episode["episode_in_season"]}")
        
        try:
            # (1) 업데이트된 프롬프트를 반영해서 노드 표준화
            prompt = UPDATED_TEMPLATE + f"\n 입력값\n {episode.synopsis}"
            graph_response = llm_call_structured(prompt)

            # (2) 에피소드 번호를 관계에 추가 (ex. S1E01)
            episode_number = f"S{episode['season']}E{episode['episode_in_season']:02d}"

            for relationship in graph_response.relationships:
                if relationship.properties is None:
                    relationship.properties = {}
                relationship.properties["episode_number"] = episode_number
                
            # (3) 노드 이름 한국어로 변환
            for node in graph_response.nodes:
                english_name = node.properties["name"]
                if english_name in KOREAN_NODE_MAP:
                    node.properties["name"] = KOREAN_NODE_MAP[english_name]
            
            chunk_graphs.append(graph_response)
            
        except Exception as e:
            print(f"  - 에피소드 처리 중 오류 발생: {e}")
            continue
    
    if chunk_graphs:
        combined_graph = combine_chunk_graphs(chunk_graphs)
        
        with open("output/지식그래프_최종.json", "w", encoding="utf-8") as f:
            json.dump(combined_graph.model_dump(), f, ensure_ascii=False, indent=2)
    else:
        print("그래프를 성공적으로 추출하지 못했습니다.")