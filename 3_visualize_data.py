from pyvis.network import Network
import json

def visualize_graph(json_file, output_file):
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    net = Network(height="600px", width="100%", directed=True)

    # 물리 옵션만 추가!
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.005,
          "springLength": 150,
          "springConstant": 0.05,
          "damping": 0.4,
          "avoidOverlap": 0.1
        },
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based",
        "stabilization": {"iterations": 100}
      }
    }
    """)

    for node in data["nodes"]:
        net.add_node(
            node["id"], 
            label=node["properties"].get("name", str(node["id"])),
        )
    for rel in data["relationships"]:
        net.add_edge(
            rel["start_node_id"], 
            rel["end_node_id"], 
            label=rel.get("type", "")
        )

    net.save_graph(output_file)
    print(f"그래프가 '{output_file}'에 저장되었습니다.")

if __name__ == "__main__":
    visualize_graph("output/지식그래프.json", "output/시각화.html")