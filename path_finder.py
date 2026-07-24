# path_finder.py
# Name-based pathfinder with case-insensitive entry
import pickle, os, cv2, math, pandas as pd, networkx as nx, numpy as np

GPICKLE = "graph_by_name.gpickle"
NODES_CSV = "nodes.csv"
OUT_PREFIX = "path_floor"

# --- load graph ---
with open(GPICKLE, "rb") as f:
    G = pickle.load(f)

nodes = pd.read_csv(NODES_CSV).set_index("name")

# --- helper: case-insensitive name -> canonical name ---
lower_map = {name.lower(): name for name in G.nodes()}

def canonical(name):
    if name in G: 
        return name
    n = name.strip().lower()
    return lower_map.get(n, None)

# --- ask user ---
src_in = input("Source node name: ").strip()
dst_in = input("Destination node name: ").strip()

src = canonical(src_in)
dst = canonical(dst_in)
if src is None or dst is None:
    print("Source or destination not found (case-insensitive).")
    print("Try one of (examples):", list(G.nodes())[:8])
    raise SystemExit

try:
    path = nx.shortest_path(G, source=src, target=dst, weight="weight")
except Exception as e:
    print("Path error:", e)
    raise SystemExit

print("Shortest path:", " -> ".join(path))

# --- prepare per-floor images ---
floors_needed = sorted({int(nodes.loc[name]["floor"]) for name in path})
floor_images = {}
for f in floors_needed:
    found = None
    for ext in ("png","jpg","jpeg"):
        p = f"map_floor{f}.{ext}"
        if os.path.exists(p):
            found = p; break
    if not found and f == 0 and os.path.exists("map.png"):
        found = "map.png"
    if found:
        floor_images[f] = cv2.imread(found)
    else:
        # blank canvas fallback
        floor_images[f] = 255 * np.ones((800,1200,3), dtype=np.uint8)

# make draw copies
drawn = {f: floor_images[f].copy() for f in floor_images}

# draw helper
def draw_node(img, x, y, label, color, radius=6):
    cv2.circle(img, (int(x),int(y)), radius, color, -1)
    cv2.putText(img, label, (int(x)+8,int(y)-8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1, cv2.LINE_AA)

# draw path segments
for i in range(len(path)-1):
    a, b = path[i], path[i+1]
    ra = nodes.loc[a]; rb = nodes.loc[b]
    fa, fb = int(ra["floor"]), int(rb["floor"])
    xa, ya = int(ra["x"]), int(ra["y"])
    xb, yb = int(rb["x"]), int(rb["y"])

    # mark points (intermediates green by default)
    draw_node(drawn[fa], xa, ya, a, (0,200,0), radius=6)
    draw_node(drawn[fb], xb, yb, b, (0,200,0), radius=6)

    if fa == fb:
        cv2.line(drawn[fa], (xa,ya), (xb,yb), (0,180,255), 3, cv2.LINE_AA)
    else:
        # mark inter-floor nodes clearly (circle + label)
        draw_node(drawn[fa], xa, ya, a, (200,0,200), radius=8)
        draw_node(drawn[fb], xb, yb, b, (200,0,200), radius=8)

# recolor start/end
s = nodes.loc[path[0]]; t = nodes.loc[path[-1]]
draw_node(drawn[int(s["floor"])], int(s["x"]), int(s["y"]), path[0], (255,0,0), radius=9)  # blue
draw_node(drawn[int(t["floor"])], int(t["x"]), int(t["y"]), path[-1], (0,0,255), radius=9)  # red

# save & show
saved = []
for f in sorted(drawn.keys()):
    out = f"{OUT_PREFIX}{f}.png"
    cv2.imwrite(out, drawn[f])
    saved.append(out)
    print("Saved:", out)

# simple viewer: advance with any key, 'q' to quit
for p in saved:
    img = cv2.imread(p)
    cv2.namedWindow(p, cv2.WINDOW_NORMAL)
    cv2.imshow(p, img)
    k = cv2.waitKey(0) & 0xFF
    cv2.destroyWindow(p)
    if k == ord('q'):
        break

print("Done.")
