import cv2
import pandas as pd

IMG = "map.png"
NODES = "nodes.csv"
EDGES = "edges.csv"

# Load base map
base = cv2.imread(IMG)
if base is None:
    raise SystemExit("map.png not found!")

nodes = pd.read_csv(NODES)
edges = pd.read_csv(EDGES)

# --- Nodes only ---
nodes_img = base.copy()
for _, node in nodes.iterrows():
    x, y = int(node["x"]), int(node["y"])
    cv2.circle(nodes_img, (x, y), 5, (0, 0, 255), -1)
    cv2.putText(nodes_img, node["id"], (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
cv2.imwrite("map_with_nodes.png", nodes_img)

# --- Edges only ---
edges_img = base.copy()
for _, edge in edges.iterrows():
    n1 = nodes[nodes["id"] == edge["n1"]]
    n2 = nodes[nodes["id"] == edge["n2"]]
    if n1.empty or n2.empty:
        print(f"⚠️ Skipping invalid edge: {edge['n1']} ↔ {edge['n2']}")
        continue
    n1, n2 = n1.iloc[0], n2.iloc[0]
    cv2.line(edges_img, (int(n1["x"]), int(n1["y"])),
             (int(n2["x"]), int(n2["y"])), (255, 0, 0), 2)
cv2.imwrite("map_with_edges.png", edges_img)

# --- Combined ---
combined_img = base.copy()
for _, edge in edges.iterrows():
    n1 = nodes[nodes["id"] == edge["n1"]]
    n2 = nodes[nodes["id"] == edge["n2"]]
    if n1.empty or n2.empty:
        continue
    n1, n2 = n1.iloc[0], n2.iloc[0]
    cv2.line(combined_img, (int(n1["x"]), int(n1["y"])),
             (int(n2["x"]), int(n2["y"])), (255, 0, 0), 2)
for _, node in nodes.iterrows():
    x, y = int(node["x"]), int(node["y"])
    cv2.circle(combined_img, (x, y), 5, (0, 0, 255), -1)
    cv2.putText(combined_img, node["id"], (x + 5, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
cv2.imwrite("map_with_nodes_edges.png", combined_img)

print("✅ Saved images:")
print("- map_with_nodes.png")
print("- map_with_edges.png")
print("- map_with_nodes_edges.png")
