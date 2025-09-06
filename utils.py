import openai
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from typing import List, Optional, Union
import os
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


PropertyValue = Union[str, int, float, bool, None]

class Node(BaseModel):
    id: str
    label: str
    properties: Optional[Dict[str, PropertyValue]] = None

class Relationship(BaseModel):
    type: str
    start_node_id: str
    end_node_id: str
    properties: Optional[Dict[str, PropertyValue]] = None

class GraphResponse(BaseModel):
    nodes: List[Node]
    relationships: List[Relationship]



DEFAULT_TEMPLATE = """
You are a top-tier algorithm designed for extracting
information in structured formats to build a knowledge graph.

Extract the entities (nodes) and specify their type from the following text.
Also extract the relationships between these nodes.

Return result as JSON using the following format:
{{"nodes": [ {{"id": "0", "label": "Person", "properties": {{"name": "John"}} }}],
"relationships": [{{"type": "KNOWS", "start_node_id": "0", "end_node_id": "1", "properties": {{"since": "2024-08-01"}} }}] }}

Assign a unique ID (string) to each node, and reuse it to define relationships.
Do respect the source and target node types for relationship and
the relationship direction.

Make sure you adhere to the following rules to produce valid JSON objects:
- Do not return any additional information other than the JSON in it.
- Omit any backticks around the JSON - simply output the JSON on its own.
- The JSON object must not wrapped into a list - it is its own JSON object.
- Property names must be enclosed in double quotes
"""


UPDATED_TEMPLATE="""
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph. Extract the entities (nodes) and specify their type from the following text, but **you MUST select nodes ONLY from the following predefined set** (see the provided NODES list below). Do not create any new nodes or use names that do not exactly match one in the NODES list.

Also extract the relationships between these nodes. Return the result as JSON using the following format:

{
  "nodes": [
    {"id": "N0", "label": "사람", "properties": {"name": "Eren Jaeger"}}
  ],
  "relationships": [
    {"type": "KNOWS", "start_node_id": "N0", "end_node_id": "N1", "properties": {"since": "2024-08-01"}}
  ]
}

Additional rules:
- **Select nodes strictly from the NODES list below**. Do not invent new nodes or use any name not in the list.
- Assign a unique ID (string) from the NODES list to each node, and reuse it to define relationships.
- Do respect the source and target node types for relationship and the relationship direction.
- Return only the JSON object, without any extra text or backticks.
- The JSON object must not be wrapped in a list.
- Property names must be enclosed in double quotes.

NODES =
[
  {"id":"N0",  "label":"사람", "properties":{"name":"Eren Jaeger"}},
  {"id":"N1",  "label":"사람", "properties":{"name":"Mikasa Ackerman"}},
  {"id":"N2",  "label":"사람", "properties":{"name":"Armin Arlert"}},
  {"id":"N3",  "label":"사람", "properties":{"name":"Levi Ackerman"}},
  {"id":"N4",  "label":"사람", "properties":{"name":"Erwin Smith"}},
  {"id":"N5",  "label":"사람", "properties":{"name":"Hange Zoë"}},
  {"id":"N6",  "label":"사람", "properties":{"name":"Jean Kirstein"}},
  {"id":"N7",  "label":"사람", "properties":{"name":"Reiner Braun"}},
  {"id":"N8",  "label":"사람", "properties":{"name":"Bertholdt Hoover"}},
  {"id":"N9",  "label":"사람", "properties":{"name":"Annie Leonhart"}},
  {"id":"N10", "label":"사람", "properties":{"name":"Grisha Jaeger"}},
  {"id":"N11", "label":"거인", "properties":{"name":"Female Titan"}},
  {"id":"N12", "label":"거인", "properties":{"name":"Eren's Titan"}},
  {"id":"N13", "label":"거인", "properties":{"name":"Colossal Titan"}},
  {"id":"N14", "label":"거인", "properties":{"name":"Armored Titan"}}
]


"""



def llm_call_structured(prompt: str, model: str = "gpt-4.1") -> GraphResponse:
    resp = client.responses.parse(
        model=model,
        input=[
            {"role": "user", "content": prompt},
        ],
        text_format=GraphResponse,  # <- Pydantic 스키마 그대로 입력
    )
    return resp.output_parsed  





# 예시:
# 그래프1: nodes: [N1(에렌), N2(미카사)], relationships: [에렌->미카사: 친구]
# 그래프2: nodes: [N1(에렌), N3(리바이)], relationships: [리바이->에르빈: 부하]  # N1 중복
# 결합된 그래프: nodes: [N1(에렌), N2(미카사), N3(리바이)], relationships: [친구, 부하]  # 중복 제거

def combine_chunk_graphs(chunk_graphs: list) -> 'GraphResponse':
    """
    여러 개의 GraphResponse 객체를 하나로 합칩니다.
    - 모든 노드와 관계(relationship)를 모읍니다.
    - 중복된 노드는 제거하고, 처음 등장한 노드만 남깁니다.
    """
    # 1. 모든 chunk_graph에서 노드를 모읍니다
    all_nodes = []
    for chunk_graph in chunk_graphs:
        for node in chunk_graph.nodes:
            all_nodes.append(node)
    
    # 2. 모든 chunk_graph에서 관계(relationship)를 모읍니다
    all_relationships = []
    for chunk_graph in chunk_graphs:
        for relationship in chunk_graph.relationships:
            all_relationships.append(relationship)
    
    # 3. 중복된 노드를 제거합니다
    unique_nodes = []
    seen = set()  # 이미 추가된 노드를 기억해둘 집합

    for node in all_nodes:
        # 노드의 id, label, properties를 묶어서 하나의 키로 만듭니다
        node_key = (node.id, node.label, str(node.properties))
        # 이미 추가된 노드가 아니라면 unique_nodes에 추가합니다
        if node_key not in seen:
            unique_nodes.append(node)
            seen.add(node_key)

    # 4. 중복이 제거된 노드들과 모든 관계를 합쳐 새로운 GraphResponse를 만듭니다
    return GraphResponse(nodes=unique_nodes, relationships=all_relationships)


if __name__ == "__main__":
    
    # 1기 1화 테스트
    sample_episode = """
    For over a century, humans have been living in settlements surrounded by three 50-meter gigantic walls, Wall Maria, Wall Rose and Wall Sina, which prevent the Titans, giant humanoid creatures who eat humans, from entering. Eren Jaeger , of the town called the Shiganshina District, wishes to see the outside world by joining the Scout Regiment , as he likens living in the cities to being like livestock. His resolve impresses his father Grisha Jaeger , who promises to show him what lies in their basement once he returns. Things change when the Colossal Titan, a giant 60-meter Titan taller than regular ones, appears and destroys the gate, allowing smaller Titans to enter. As the town erupts into mass panic, Eren and his friend Mikasa Ackerman find Eren's mother Carla Jaeger pinned under their collapsed house. A Smiling Titan approaches and Carla begs them to flee. City guard Hannes promises Carla to protect the kids. As he flees carrying them, Eren watches in horror as the Smiling Titan eats his mother.
    """
    prompt = DEFAULT_TEMPLATE.format(text=sample_episode)
    result: GraphResponse = llm_call_structured(prompt)
    print("\nLLM 응답:")
    print(result)

