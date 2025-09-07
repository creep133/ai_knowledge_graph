# AI 로 지식그래프 만들기

진격의 거인 줄거리를 AI로 분석하여 주인공 중심의 지식 그래프로 만들어봅니다!

## 프로젝트 소개

이 프로젝트는 자동으로:
1. **수집** - 위키피디아에서 에피소드 데이터 수집 (진격의 거인 에피소드)
2. **처리** - OpenAI를 사용하여 텍스트에서 개체와 관계 추출
3. **시각화** - 인터랙티브 웹 형태의 지식 그래프 생성

## 사전 요구사항
- 파이썬 설치
- OpenAI API 키 설정

## 초기 셋팅

2. **OpenAI API 키 설정:**
프로젝트 루트에 `.env` 파일 생성:
```
OPENAI_API_KEY=여기에_API_키_입력
```

## 실행 방법

스크립트를 순서대로 실행하세요:

```bash
# 1단계: 위키피디아에서 에피소드 데이터 수집
uv run 1_collect_data.py

# 2단계: AI로 데이터 처리하여 지식 그래프 생성
uv run 2_process_data.py

# 3단계: 시각화 페이지 생성
uv run 3_visualize_data.py

# 4단계 : 데이터 표준화
uv run 4_process_data_upgrade.py

```

## Neo4j 프롬프트 템플릿
<details>
  <summary>아래를 그대로 복사해서 챗GPT에서 활용해도 됩니다</summary>

```text
You are a top-tier algorithm designed for extracting
information in structured formats to build a knowledge graph.

Extract the entities (nodes) and specify their type from the following text.
Also extract the relationships between these nodes.

Return result as JSON using the following format:
{{"nodes": [ {{"id": "0", "label": "Person", "properties": {{"name": "John"}} }}],
"relationships": [{{"type": "KNOWS", "start_node_id": "0", "end_node_id": "1", "properties": {{"since": "2024-08-01"}} }}] }}

Use only the following node and relationship types (if provided):
{schema}

Assign a unique ID (string) to each node, and reuse it to define relationships.
Do respect the source and target node types for relationship and
the relationship direction.

Make sure you adhere to the following rules to produce valid JSON objects:
- Do not return any additional information other than the JSON in it.
- Omit any backticks around the JSON - simply output the JSON on its own.
- The JSON object must not wrapped into a list - it is its own JSON object.
- Property names must be enclosed in double quotes

Examples:
{examples}

Input text:
```
</details>
https://github.com/neo4j/neo4j-graphrag-python/blob/main/src/neo4j_graphrag/generation/prompts.py

## 지식그래프 시각화 3가지 방법
1. 3_visualize_data.py 을 이용해서 html 실행
2. 시각화도구/index.html 활용
3. https://visualize-knowledge-graph.vercel.app 활용
