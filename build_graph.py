# build_graph.py
import pandas as pd
import networkx as nx
import pickle

nodes = pd.read_csv("nodes.csv")
edges = pd.read_csv("edges_by_name.csv")

G = nx.Graph()

for _, r in nodes.iterrows():
    G.add_node(
        r["name"],
        floor=int(r["floor"]),
        x=int(r["x"]),
        y=int(r["y"])
    )

for _, e in edges.iterrows():
    G.add_edge(
        e["name1"],
        e["name2"],
        weight=float(e["weight"])
    )

with open("graph_by_name.gpickle", "wb") as f:
    pickle.dump(G, f)

print("Graph saved. Nodes:", G.number_of_nodes(), "Edges:", G.number_of_edges())
