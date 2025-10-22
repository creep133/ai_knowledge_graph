import os
from neo4j import GraphDatabase, exceptions
from dotenv import load_dotenv
import time # 사용자의 실수를 방지하기 위한 짧은 지연 시간

def drop_all_constraints(tx):
    """데이터베이스의 모든 제약 조건을 조회하고 삭제합니다."""
    print("  - Checking for existing constraints...")
    constraints = tx.run("SHOW CONSTRAINTS").data()
    dropped_count = 0
    if not constraints:
        print("  - No constraints found.")
        return dropped_count

    print(f"  - Found {len(constraints)} constraints. Attempting to drop them...")
    # 최신 Neo4j 버전은 SHOW CONSTRAINTS YIELD name 으로 이름을 가져옵니다.
    # 구버전 호환성을 위해 이름이 있는지 확인합니다.
    for constraint in constraints:
        name = constraint.get('name')
        if name:
            try:
                print(f"    - Dropping constraint: {name}")
                tx.run(f"DROP CONSTRAINT {name}")
                dropped_count += 1
            except exceptions.CypherSyntaxError as e:
                # 구문 오류 시 대체 시도 (구버전 또는 다른 제약 조건 유형)
                print(f"    - Standard DROP failed for {name}. Error: {e}")
                # 필요시 여기에 구버전 제약 조건 삭제 구문 추가 (현재는 생략)
            except Exception as e:
                 print(f"    - Failed to drop constraint {name}: {e}")
        else:
            print(f"    - Found constraint without a name, skipping automatic drop: {constraint}")
    print(f"  - Dropped {dropped_count} constraints.")
    return dropped_count

def clear_neo4j_database(driver):
    """연결된 Neo4j 데이터베이스의 모든 노드와 관계를 삭제합니다."""
    print("\n⚠️ 경고: 이 작업은 Neo4j 데이터베이스의 모든 데이터를 영구적으로 삭제합니다!")
    print("⚠️ 반드시 올바른 데이터베이스 인스턴스에 연결되었는지 확인하세요.")

    # 사용자의 실수를 방지하기 위한 명확한 확인 절차
    confirm = input("정말로 모든 데이터를 삭제하려면 'DELETE ALL DATA'를 입력하세요: ")
    if confirm != "DELETE ALL DATA":
        print("확인 문구가 일치하지 않습니다. 데이터베이스 삭제가 취소되었습니다.")
        return False

    print("\n삭제를 진행합니다... (2초 후 시작)")
    time.sleep(2) # 실수로 실행했을 경우 취소할 시간

    try:
        with driver.session() as session:
            # 1단계: 제약 조건 삭제 (제약 조건이 있으면 노드 삭제가 실패할 수 있음)
            session.execute_write(drop_all_constraints)

            # 2단계: 모든 노드와 연결된 관계 삭제
            print("  - Deleting all nodes and relationships...")
            # DETACH DELETE는 노드를 삭제하기 전에 연결된 모든 관계를 먼저 제거합니다.
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume() # 쿼리 실행 결과 요약 정보 가져오기
            print("\n✅ 데이터베이스 초기화 완료!")
            print(f"  - 삭제된 노드 수: {summary.counters.nodes_deleted}")
            print(f"  - 삭제된 관계 수: {summary.counters.relationships_deleted}")
            return True
    except Exception as e:
        print(f"\n❌ 데이터베이스 삭제 중 오류 발생: {e}")
        print("  - 삭제 작업이 불완전할 수 있습니다.")
        print("  - 오류가 계속되면 Neo4j Browser에서 직접 제약 조건을 확인하고 삭제해 보세요.")
        return False

# --- 메인 실행 블록 ---
if __name__ == "__main__":
    # .env 파일 로드
    load_dotenv()
    print("환경 변수를 로드했습니다.")

    # Neo4j 연결 정보 가져오기
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    if not all([NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD]):
        print("❌ 오류: .env 파일에서 Neo4j 연결 정보를 찾을 수 없습니다.")
        exit()

    driver = None
    try:
        # 공식 Neo4j 드라이버를 사용하여 연결
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        driver.verify_connectivity() # 연결 및 인증 테스트
        print(f"성공적으로 Neo4j AuraDB에 연결되었습니다: {NEO4J_URI}")

        # 데이터베이스 삭제 함수 실행
        clear_neo4j_database(driver)

    except Exception as e:
        print(f"\n❌ Neo4j 연결 실패: {e}")
    finally:
        # 스크립트 종료 시 항상 드라이버 연결을 닫습니다.
        if driver:
            driver.close()
            print("\nNeo4j 연결을 닫았습니다.")