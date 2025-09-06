import json
from typing import List
from utils import DEFAULT_TEMPLATE, GraphResponse, llm_call_structured, combine_chunk_graphs

if __name__ == "__main__":
    
    # 데이터 불러오기
    with open("output/1_원본데이터.json", encoding="utf-8") as f:
        episodes = json.load(f)

    # 첫 1개 에피소드만 테스트    
    sample_episodes = episodes[:1] 
    
    chunk_graphs: List[GraphResponse] = []
    
    for episode in sample_episodes:

        print(f"에피소드 처리 중: 시즌 {episode["season"]}, 에피소드 {episode["episode_in_season"]}")
        
        try:
            # 프롬프트 생성 및 LLM 호출
            prompt = DEFAULT_TEMPLATE + f"\n 입력값\n {episode["synopsis"]}"
            graph_response = llm_call_structured(prompt)
            chunk_graphs.append(graph_response)
            
        except Exception as e:
            print(f"  - 에피소드 처리 중 오류 발생: {e}")
            continue
    
    # 모든 청크 그래프를 하나로 결합
    if chunk_graphs:
        combined_graph = combine_chunk_graphs(chunk_graphs)
        
        # 지식그래프 저장
        with open("output/지식그래프.json", "w", encoding="utf-8") as f:
            json.dump(combined_graph.model_dump(), f, ensure_ascii=False, indent=2)
        
    else:
        print("그래프를 성공적으로 추출하지 못했습니다.")