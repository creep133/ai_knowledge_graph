
import json
from typing import List
from utils import  GraphResponse, combine_chunk_graphs, llm_call_structured, UPDATED_TEMPLATE





# 노드 이름 한글 매핑 (귀살대 · 도깨비)
KOREAN_NODE_MAP = {
    # 귀살대 (Demon Slayer Corps)
    "Tanjiro Kamado": "카마도 탄지로",
    "Nezuko Kamado": "카마도 네즈코",
    "Giyu Tomioka": "토미오카 기유",
    "Sakonji Urokodaki": "우로코다키 사콘지",
    "Sabito": "사비토",
    "Makomo": "마코모",
    "Zenitsu Agatsuma": "아가츠마 젠이츠",
    "Inosuke Hashibira": "하시비라 이노스케",
    "Kanao Tsuyuri": "츠유리 카나오",
    "Kyojuro Rengoku": "렌고쿠 쿄쥬로",
    "Kagaya Ubuyashiki": "우부야시키 카가야",
    "Shinobu Kocho": "코쵸우 시노부",
    "Sanemi Shinazugawa": "시나즈가와 사네미",

    # 도깨비 (Demons)
    "Muzan Kibutsuji": "키부츠지 무잔",
    "Susamaru": "스사마루",
    "Yahaba": "야하바",
    "Kyogai": "쿄우가이",
    "Rui": "루이",
    "Enmu": "엔무",
}



if __name__ == "__main__":
    

    with open("output/1_원본데이터.json", encoding="utf-8") as f:
        episodes = json.load(f)

   # 첫 1개 에피소드만 테스트    
    sample_episodes = episodes 
    
    chunk_graphs: List[GraphResponse] = []
    
    for episode in sample_episodes:
        print(f"에피소드 처리 중: 시즌 {episode["season"]}, 에피소드 {episode["episode_in_season"]}")
        
        try:
            # (1) 업데이트된 프롬프트를 반영해서 노드 표준화
            prompt = UPDATED_TEMPLATE + f"\n 입력값\n {episode["synopsis"]}"
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