# node_picker_tk.py
import cv2
import pandas as pd
import os, shutil, datetime
import tkinter as tk
from tkinter import simpledialog

# ------------------------
# CONFIG
# ------------------------
NODES_CSV = "nodes.csv"
BACKUP_DIR = "backups_nodes"
IMG_FOLDER = "."   # project root
# ------------------------

def backup_nodes():
    """Create a timestamped backup of nodes.csv."""
    if not os.path.exists(NODES_CSV):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"nodes_backup_{ts}.csv")
    shutil.copy2(NODES_CSV, dst)
    print(f"[Backup] Saved: {dst}")

def load_nodes():
    """Load existing nodes or create a new dataframe."""
    if os.path.exists(NODES_CSV):
        df = pd.read_csv(NODES_CSV)
        for col in ["id","name","floor","x","y"]:
            if col not in df.columns:
                df[col] = ""
        return df
    else:
        return pd.DataFrame(columns=["id","name","floor","x","y"])

def next_node_index(df):
    """Get next numeric index for node ID nX."""
    if df.empty:
        return 0
    used = []
    for _id in df["id"].astype(str):
        if _id.startswith("n"):
            try:
                used.append(int(_id[1:]))
            except:
                pass
    return max(used) + 1 if used else 0

def find_map_for_floor(floor):
    """Find map_floorX.png automatically."""
    candidates = [
        f"map_floor{floor}.png",
        f"map_floor{floor}.jpg",
        f"map_floor{floor}.jpeg"
    ]
    for c in candidates:
        p = os.path.join(IMG_FOLDER, c)
        if os.path.exists(p):
            return p
    # Fallback for ground floor
    if floor == 0:
        p = os.path.join(IMG_FOLDER, "map.png")
        if os.path.exists(p):
            return p
    return None


def main():
    print("=== Campus Compass — Node Picker (Tkinter safe input) ===")
    
    # LOAD EXISTING NODES
    nodes_df = load_nodes()
    print(f"[Nodes] Loaded {len(nodes_df)} existing nodes.")

    # MODE (append or fresh)
    mode = input("Mode ([add] to append, [fresh] to overwrite): ").strip().lower()
    if mode not in ("add", "fresh"):
        mode = "add"

    if mode == "fresh":
        backup_nodes()
        nodes_df = pd.DataFrame(columns=["id","name","floor","x","y"])
        node_index = 0
        print("[Mode] Starting fresh.")
    else:
        node_index = next_node_index(nodes_df)
        print(f"[Mode] Adding to existing. Next ID index = {node_index}")

    # SELECT FLOOR
    while True:
        f = input("Enter floor number (0,1,2,3...): ").strip()
        if f.isdigit():
            floor = int(f)
            break
        print("Please enter a valid integer.")

    map_path = find_map_for_floor(floor)
    if not map_path:
        print(f"[Error] No map found for floor {floor}. Expected: map_floor{floor}.png")
        return

    print(f"[Map] Loading {map_path}")
    img = cv2.imread(map_path)
    if img is None:
        print("[Error] Failed to load map image.")
        return

    # Tkinter root (hidden) for name input
    root = tk.Tk()
    root.withdraw()

    display = img.copy()
    cv2.namedWindow("map", cv2.WINDOW_NORMAL)
    cv2.imshow("map", display)

    new_nodes = []

    def onclick(event, x, y, flags, param):
        nonlocal display, new_nodes, node_index

        if event == cv2.EVENT_LBUTTONDOWN:
            # Ask for node name via Tkinter pop-up
            name = simpledialog.askstring("Node name", "Enter location name (Room, Corridor, etc.):", parent=root)
            if not name:
                print("[Skip] Empty name.")
                return

            node_id = f"n{node_index}"
            node_index += 1

            new_nodes.append({
                "id": node_id,
                "name": name.strip(),
                "floor": floor,
                "x": int(x),
                "y": int(y)
            })

            cv2.circle(display, (x,y), 6, (0,0,255), -1)
            cv2.putText(display, name, (x+6,y-6), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255,255,255), 1, cv2.LINE_AA)
            cv2.imshow("map", display)
            print(f"[Added] {node_id} | {name} | Floor {floor} | ({x},{y})")

    cv2.setMouseCallback("map", onclick)

    print("\nInstructions:")
    print(" • Click to add nodes")
    print(" • Press 'q' to quit and save")
    print(" • Press 'c' to cancel without saving")

    # Main loop: wait for 'q' or 'c'
    while True:
        k = cv2.waitKey(1) & 0xFF
        if k == ord('q'):
            if new_nodes:
                save = input("Save new nodes? [y/n]: ").strip().lower()
                if save == 'y':
                    backup_nodes()
                    new_df = pd.DataFrame(new_nodes)[["id","name","floor","x","y"]]
                    updated = pd.concat([nodes_df, new_df], ignore_index=True)
                    updated.to_csv(NODES_CSV, index=False)
                    print(f"[Saved] {len(new_nodes)} nodes → {NODES_CSV}")
                else:
                    print("[No Save] Discarded new nodes.")
            else:
                print("[Info] No nodes added.")
            break
        elif k == ord('c'):
            print("[Cancel] Discarding changes.")
            break

    cv2.destroyAllWindows()
    print("[Done] Node Picker closed.")

if __name__ == "__main__":
    main()
