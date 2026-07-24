import cv2, pandas as pd, os, math, shutil, datetime, argparse

NODES = "nodes.csv"
OUT = "edges_by_name.csv"
BACKUP = "backups_edges"

def backup_edges():
    if os.path.exists(OUT):
        os.makedirs(BACKUP, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(BACKUP, f"edges_backup_{ts}.csv")
        shutil.copy2(OUT, dst)
        print(f"[Backup] edges -> {dst}")

def load_nodes():
    df = pd.read_csv(NODES)
    df["name"] = df["name"].astype(str)
    df["floor"] = df["floor"].astype(int)
    return df

def load_edges():
    if not os.path.exists(OUT):
        return pd.DataFrame(columns=["name1","name2","weight"])
    return pd.read_csv(OUT)

def nearest(nodes_df, x, y, floor):
    f_nodes = nodes_df[nodes_df["floor"] == floor]
    if f_nodes.empty: return None, None
    d = ((f_nodes["x"] - x)**2 + (f_nodes["y"] - y)**2).pow(0.5)
    idx = d.idxmin()
    return f_nodes.loc[idx].to_dict(), float(d.loc[idx])

def draw_all_nodes(img, nodes_df, floor):
    for _, r in nodes_df[nodes_df["floor"]==floor].iterrows():
        cx, cy = int(r["x"]), int(r["y"])
        cv2.circle(img, (cx,cy), 5, (0,0,255), -1)
        cv2.putText(img, r["name"], (cx+6,cy-6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (255,255,255), 1, cv2.LINE_AA)

def get_map(floor):
    for ext in ["png","jpg","jpeg"]:
        f = f"map_floor{floor}.{ext}"
        if os.path.exists(f): return f
    if floor==0 and os.path.exists("map.png"): return "map.png"
    return None

def pick_node(nodes_df, floor):
    """One-off click picker for inter-floor mode."""
    mapfile = get_map(floor)
    if not mapfile:
        print(f"[Error] Missing map for floor {floor}."); return None

    img = cv2.imread(mapfile)
    disp = img.copy()
    draw_all_nodes(disp, nodes_df, floor)

    sel = {"node":None}

    def click(ev,x,y,_,__):
        if ev == cv2.EVENT_LBUTTONDOWN:
            nd, dist = nearest(nodes_df, x, y, floor)
            if nd:
                print("[Selected]", nd["name"])
                sel["node"] = nd
                tmp = disp.copy()
                cv2.circle(tmp, (nd["x"],nd["y"]), 8, (0,255,0), 2)
                cv2.imshow("map", tmp)

    cv2.namedWindow("map", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("map", click)
    cv2.imshow("map", disp)
    print("Click a node → press q to confirm.")

    while True:
        k = cv2.waitKey(1)&0xFF
        if k==ord('q') and sel["node"] is not None:
            break
        if k==27:  # ESC abort
            sel["node"] = None
            break

    cv2.destroyAllWindows()
    return sel["node"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="floor",
                        help="floor (fast same-floor) or inter (cross-floor)")
    parser.add_argument("--floor", type=int, default=None,
                        help="floor number for fast mode")
    args = parser.parse_args()

    nodes_df = load_nodes()
    edges_df = load_edges()

    # ------------------------
    # MODE A: FAST FLOOR MODE
    # ------------------------
    if args.mode == "floor":
        if args.floor is None:
            print("Usage: python edge_picker_fast.py --mode floor --floor 0")
            return

        floor = args.floor
        mapfile = get_map(floor)
        if not mapfile:
            print(f"[Error] Map for floor {floor} missing.")
            return

        print(f"[FAST MODE] Floor {floor} — Click pairs of nodes to create edges. Press q to stop.")

        img = cv2.imread(mapfile)
        disp = img.copy()
        draw_all_nodes(disp, nodes_df, floor)
        cv2.namedWindow("map", cv2.WINDOW_NORMAL)
        cv2.imshow("map", disp)

        clicks = []

        def click(ev,x,y,_,__):
            nonlocal clicks, disp, edges_df
            if ev == cv2.EVENT_LBUTTONDOWN:
                nd, dist = nearest(nodes_df, x, y, floor)
                if not nd: return
                print("[Selected]", nd["name"])
                clicks.append(nd)

                # highlight click
                temp = disp.copy()
                cv2.circle(temp, (nd["x"],nd["y"]), 8, (0,255,0), 2)
                cv2.imshow("map", temp)

                # Every 2 clicks = create edge
                if len(clicks) == 2:
                    n1, n2 = clicks
                    if n1["name"] != n2["name"]:
                        dx = n1["x"] - n2["x"]
                        dy = n1["y"] - n2["y"]
                        wt = round(math.hypot(dx,dy),2)

                        # check duplicate
                        exists = False
                        for _, r in edges_df.iterrows():
                            a,b = r["name1"], r["name2"]
                            if (a==n1["name"] and b==n2["name"]) or (a==n2["name"] and b==n1["name"]):
                                exists=True; break

                        if not exists:
                            backup_edges()
                            new_row = pd.DataFrame([{
                                "name1":n1["name"],
                                "name2":n2["name"],
                                "weight":wt
                            }])
                            edges_df = pd.concat([edges_df,new_row],ignore_index=True)
                            edges_df.to_csv(OUT,index=False)
                            print(f"[Saved Edge] {n1['name']} ↔ {n2['name']} ({wt}px)")
                        else:
                            print("[Skip] Duplicate edge.")

                    clicks = []  # reset pair

        cv2.setMouseCallback("map", click)

        while True:
            k = cv2.waitKey(1)&0xFF
            if k==ord('q'):
                break

        cv2.destroyAllWindows()
        print("[Done] Floor mode complete.")
        return

    # --------------------------------
    # MODE B: SIMPLE INTER-FLOOR MODE
    # --------------------------------
    elif args.mode == "inter":
        print("[INTER-FLOOR MODE] Connect staircase/lift nodes between floors.")
        while True:
            f1 = input("Floor of first node (or q to quit): ").strip()
            if f1.lower()=='q': break
            f2 = input("Floor of second node: ").strip()
            if not (f1.isdigit() and f2.isdigit()): 
                print("Invalid.") 
                continue
            f1, f2 = int(f1), int(f2)

            print("Pick first node:")
            n1 = pick_node(nodes_df, f1)
            if not n1: continue

            print("Pick second node:")
            n2 = pick_node(nodes_df, f2)
            if not n2: continue

            dx = n1["x"] - n2["x"]
            dy = n1["y"] - n2["y"]
            wt = round(math.hypot(dx,dy),2)

            edges_df = pd.concat([edges_df,
                pd.DataFrame([{
                    "name1":n1["name"],
                    "name2":n2["name"],
                    "weight":wt
                }])
            ], ignore_index=True)

            backup_edges()
            edges_df.to_csv(OUT,index=False)
            print(f"[Saved Inter-Floor Edge] {n1['name']} ↔ {n2['name']} ({wt}px)")

        print("[Done] Inter-floor mode complete.")
        return

    else:
        print("Invalid mode. Use --mode floor or --mode inter.")
if __name__ == "__main__":
    main()
