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



UPDATED_TEMPLATE = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph. Extract the entities (nodes) and specify their type from the following text, but **you MUST select nodes ONLY from the following predefined set** (see the provided NODES list below). Do not create any new nodes or use names that do not exactly match one in the NODES list.

Also extract the relationships between these nodes. Return the result as JSON using the following format:

{
  "nodes": [
    {"id": "N0", "label": "인간", "properties": {"name": "Tanjiro Kamado"}}
  ],
  "relationships": [
    {"type": "FIGHTS", "start_node_id": "N0", "end_node_id": "N13", "properties": {"outcome": "victory"}}
  ]
}

Additional rules:
- Use only nodes from the NODES list. Do not invent or substitute nodes.
- Skip any relationship if one of its entities is not in NODES.
- Only output valid relationships where both endpoints exist in NODES and the direction matches their types.

NODES =
[
  {"id":"N0",  "label":"인간", "properties":{"name":"Tanjiro Kamado"}},
  {"id":"N1",  "label":"인간", "properties":{"name":"Nezuko Kamado"}},
  {"id":"N2",  "label":"인간", "properties":{"name":"Giyu Tomioka"}},
  {"id":"N3",  "label":"인간", "properties":{"name":"Sakonji Urokodaki"}},
  {"id":"N4",  "label":"인간", "properties":{"name":"Sabito"}},
  {"id":"N5",  "label":"인간", "properties":{"name":"Makomo"}},
  {"id":"N6",  "label":"인간", "properties":{"name":"Zenitsu Agatsuma"}},
  {"id":"N7",  "label":"인간", "properties":{"name":"Inosuke Hashibira"}},
  {"id":"N8",  "label":"인간", "properties":{"name":"Kanao Tsuyuri"}},
  {"id":"N9",  "label":"인간", "properties":{"name":"Kyojuro Rengoku"}},
  {"id":"N10", "label":"인간", "properties":{"name":"Kagaya Ubuyashiki"}},
  {"id":"N11", "label":"인간", "properties":{"name":"Shinobu Kocho"}},
  {"id":"N12", "label":"인간", "properties":{"name":"Sanemi Shinazugawa"}},
  {"id":"N13", "label":"도깨비", "properties":{"name":"Muzan Kibutsuji"}},
  {"id":"N14", "label":"도깨비", "properties":{"name":"Susamaru"}},
  {"id":"N15", "label":"도깨비", "properties":{"name":"Yahaba"}},
  {"id":"N16", "label":"도깨비", "properties":{"name":"Kyogai"}},
  {"id":"N17", "label":"도깨비", "properties":{"name":"Rui"}},
  {"id":"N18", "label":"도깨비", "properties":{"name":"Enmu"}}
]
"""



###### 진격의 거인 예시 #########

# UPDATED_TEMPLATE="""
# You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph. Extract the entities (nodes) and specify their type from the following text, but **you MUST select nodes ONLY from the following predefined set** (see the provided NODES list below). Do not create any new nodes or use names that do not exactly match one in the NODES list.

# Also extract the relationships between these nodes. Return the result as JSON using the following format:

# {
#   "nodes": [
#     {"id": "N0", "label": "사람", "properties": {"name": "Eren Jaeger"}}
#   ],
#   "relationships": [
#     {"type": "KNOWS", "start_node_id": "N0", "end_node_id": "N1", "properties": {"since": "2024-08-01"}}
#   ]
# }

# Additional rules:
# - Use only nodes from the NODES list. Do not invent or substitute nodes.
# - Skip any relationship if one of its entities is not in NODES.
# - Only output valid relationships where both endpoints exist in NODES and the direction matches their types.

# NODES =
# [
#   {"id":"N0",  "label":"사람", "properties":{"name":"Eren Jaeger"}},
#   {"id":"N1",  "label":"사람", "properties":{"name":"Mikasa Ackerman"}},
#   {"id":"N2",  "label":"사람", "properties":{"name":"Armin Arlert"}},
#   {"id":"N3",  "label":"사람", "properties":{"name":"Levi Ackerman"}},
#   {"id":"N4",  "label":"사람", "properties":{"name":"Erwin Smith"}},
#   {"id":"N5",  "label":"사람", "properties":{"name":"Hange Zoë"}},
#   {"id":"N6",  "label":"사람", "properties":{"name":"Jean Kirstein"}},
#   {"id":"N7",  "label":"사람", "properties":{"name":"Reiner Braun"}},
#   {"id":"N8",  "label":"사람", "properties":{"name":"Bertholdt Hoover"}},
#   {"id":"N9",  "label":"사람", "properties":{"name":"Annie Leonhart"}},
#   {"id":"N10", "label":"사람", "properties":{"name":"Grisha Jaeger"}},
#   {"id":"N11", "label":"거인", "properties":{"name":"Female Titan"}},
#   {"id":"N12", "label":"거인", "properties":{"name":"Eren's Titan"}},
#   {"id":"N13", "label":"거인", "properties":{"name":"Colossal Titan"}},
#   {"id":"N14", "label":"거인", "properties":{"name":"Armored Titan"}}
# ]


# """



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
# 그래프1: nodes: [N1(탄지로), N2(네즈코)], relationships: [탄지로->네즈코: 형제]
# 그래프2: nodes: [N1(탄지로), N3(기유)], relationships: [기유->탄지로: 지도]  # N1 중복
# 결합된 그래프: nodes: [N1(탄지로), N2(네즈코), N3(기유)], relationships: [형제, 지도]  # 중복 제거

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
    Tanjiro Kamado lives a quiet, peaceful life with his family in the snowy mountains of Japan, providing for them by selling charcoal at the nearby town. One day, he returns home and finds his entire family slaughtered in a demon attack, with the exception of his younger sister, Nezuko, who has been transformed into a demon herself. A Demon Slayer, Giyu Tomioka, appears to kill Nezuko, but Tanjiro attempts to defend her. Surprised to see Nezuko resist her demonic urges and impressed by Tanjiro's potential, he decides to spare her life, telling him to go find a man named Sakonji Urokodaki on Mt. Sagiri. Tanjiro and Nezuko bury their family before departing.
    """
    prompt = DEFAULT_TEMPLATE.format(text=sample_episode)
    result: GraphResponse = llm_call_structured(prompt)
    print("\nLLM 응답:")
    print(result)

