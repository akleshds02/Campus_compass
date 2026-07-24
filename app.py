# app.py — Campus Compass (Enhanced - Fixed Animation Speed)
import streamlit as st
import pandas as pd
import networkx as nx
import pickle, os, math, time, re
from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO
from functools import partial
from rapidfuzz import process, fuzz
import pyttsx3
from tempfile import NamedTemporaryFile
from collections import defaultdict
import base64  
import time

# Add these 3 lines RIGHT AFTER YOUR IMPORTS (around line 30):

def set_source_callback(node_name):
    """Callback for setting source from floor picker"""
    st.session_state.src_input = node_name

def add_stop_callback(node_name):
    """Callback for adding stop from floor picker"""
    current = st.session_state.get("stops_select", [])
    if node_name not in current:
        st.session_state.stops_select = current + [node_name]

def set_dest_callback(node_name):
    """Callback for setting destination from floor picker"""
    st.session_state.dst_input = node_name
    
# custom CSS for better UI
st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 1rem;
    }
    
    /* Title styling */
    .title-text {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    
    /* Subtitle */
    .subtitle-text {
        color: #666;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Card-like containers */
    .st-emotion-cache-1y4p8pa {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%);
        border-radius: 15px;
        padding: 1.5rem;
        border: 1px solid #e0e6ed;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    
    /* Section headers */
    .section-header {
        color: #4a5568;
        font-size: 1.4rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #667eea;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* Compute route button special */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
        font-size: 1.1rem;
        padding: 0.7rem 1.5rem;
    }
    
    /* Slider styling */
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 10px;
        border: none;
    }
    
    /* Map thumbnails */
    .stImage > img {
        border-radius: 10px;
        border: 2px solid #e0e6ed;
        transition: all 0.3s ease;
    }
    
    .stImage > img:hover {
        border-color: #667eea;
        transform: scale(1.02);
    }
    
    /* Diagnostics panel */
    .streamlit-expanderHeader {
        background: #f8fafc;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    
    /* Voice directions audio */
    audio {
        border-radius: 8px;
        margin: 10px 0;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        color: #718096;
        font-size: 0.9rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

st.set_page_config(layout="wide", page_title="Campus Compass")

# ---- Load data ----
@st.cache_data
def load_graph():
    with open("graph_by_name.gpickle","rb") as f:
        return pickle.load(f)

@st.cache_data
def load_nodes():
    return pd.read_csv("nodes.csv").set_index("name")

G = load_graph()
nodes = load_nodes()
node_list = sorted(list(G.nodes()))
lower_map = {n.lower(): n for n in node_list}

# categories (simple heuristics)
def infer_category(name: str):
    s = name.lower()
    if any(k in s for k in ["class ", "c1", "class"]): return "Class"
    if "lab" in s: return "Lab"
    if "lift" in s: return "Lift"
    if "stair" in s or "stairs" in s: return "Stairs"
    if "restroom" in s or "washroom" in s or "toilet" in s: return "Restroom"
    if "office" in s or "hod" in s or "principal" in s or "staff" in s: return "Office"
    if "hall" in s or "seminar" in s: return "Hall"
    if "reception" in s or "waiting" in s: return "Common"
    if "canteen" in s or "library" in s: return "Facility"
    return "Other"

categories = {n: infer_category(n) for n in node_list}
all_categories = ["All"] + sorted(set(categories.values()))

# small helpers
def canonical_from_text(name):
    if not name: return None
    if name in node_list: return name
    return lower_map.get(name.strip().lower())

# typeahead (server-side, fuzzy) — excludes corridor nodes (cNN)
def _set_session_value(key, val):
    st.session_state[key] = val

def typeahead_input(label, names, input_key, category_key=None, max_suggestions=12):
    if input_key not in st.session_state:
        st.session_state[input_key] = ""
    query = st.text_input(label, value=st.session_state.get(input_key,""), key=input_key, placeholder="Start typing...")
    q = query.strip()
    candidates = [n for n in names if not re.match(r'^c\d+$', n.strip().lower())]
    if category_key and st.session_state.get(category_key) and st.session_state.get(category_key) != "All":
        cat = st.session_state.get(category_key)
        candidates = [n for n in candidates if categories.get(n)==cat]
    suggestions = []
    if q:
        results = process.extract(q, candidates, scorer=fuzz.WRatio, limit=max_suggestions)
        suggestions = [r[0] for r in results if r[1] >= 25]
    if suggestions:
        cols = st.columns(3)
        for idx, s in enumerate(suggestions):
            col = cols[idx % 3]
            lab = f"{s} ({categories.get(s)})"
            cb = partial(_set_session_value, input_key, s)
            col.button(lab, key=f"{input_key}_sugg_{idx}", on_click=cb)
    return st.session_state.get(input_key, "")

# drawing helpers
def _draw_dashed_line(draw, p1, p2, dash_len=18, gap_len=12, fill=(200,200,200,180), width=8):
    x1,y1 = p1; x2,y2 = p2
    dist = math.hypot(x2-x1, y2-y1)
    if dist == 0:
        draw.line((p1,p2), fill=fill, width=width)
        return
    steps = int(dist / (dash_len+gap_len)) + 1
    for i in range(steps+1):
        t0 = (i*(dash_len+gap_len))/dist
        t1 = min((i*(dash_len+gap_len)+dash_len)/dist, 1.0)
        if t0>=1: break
        sx = int(x1 + (x2-x1)*t0); sy = int(y1 + (y2-y1)*t0)
        ex = int(x1 + (x2-x1)*t1); ey = int(y1 + (y2-y1)*t1)
        draw.line((sx,sy,ex,ey), fill=fill, width=width)

def draw_smooth_path_on_img(img, path_nodes, floor, path_color=(0,160,255,220), width=12, progress_idx=None):
    draw = ImageDraw.Draw(img, "RGBA")
    seg_points = []
    
    # Collect all points on this floor
    for i in range(len(path_nodes)-1):
        a = path_nodes[i]; b = path_nodes[i+1]
        ra = nodes.loc[a]; rb = nodes.loc[b]
        if int(ra["floor"]) != floor or int(rb["floor"]) != floor: 
            continue
        seg_points.append(((int(ra["x"]), int(ra["y"])), (int(rb["x"]), int(rb["y"])), i))

    # Shadow for entire path
    shadow = Image.new("RGBA", img.size, (0,0,0,0))
    sdraw = ImageDraw.Draw(shadow, "RGBA")
    for (p1,p2,_i) in seg_points:
        sdraw.line((p1,p2), fill=(0,0,0,110), width=width+8)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))
    img.alpha_composite(shadow)

    if progress_idx is not None:
        # progress_idx is now fractional like 0.5, 1.25, etc.
        completed_segments = int(math.floor(progress_idx))  # Whole segments done
        current_seg_progress = progress_idx - completed_segments  # 0.0 to 1.0
        
        # Draw COMPLETED segments (full blue)
        for (p1,p2,i) in seg_points:
            if i < completed_segments:
                draw.line((p1,p2), fill=path_color, width=width, joint="curve")
        
        # Draw CURRENT segment PARTIALLY (part blue, part dashed)
        for (p1,p2,i) in seg_points:
            if i == completed_segments:
                x1, y1 = p1
                x2, y2 = p2
                
                # Calculate point where we currently are
                current_x = x1 + (x2 - x1) * current_seg_progress
                current_y = y1 + (y2 - y1) * current_seg_progress
                
                # Draw covered part as SOLID BLUE
                draw.line((x1, y1, current_x, current_y), fill=path_color, width=width, joint="curve")
                
                # Draw remaining part as DASHED WHITE
                _draw_dashed_line(draw, (current_x, current_y), p2, dash_len=18, gap_len=12, fill=(200,200,200,180), width=width)
                break
        
        # Draw FUTURE segments as DASHED WHITE
        for (p1,p2,i) in seg_points:
            if i > completed_segments:
                _draw_dashed_line(draw, p1, p2, dash_len=18, gap_len=12, fill=(200,200,200,180), width=width)
    else:
        # Draw all as solid (no progress tracking)
        for (p1,p2,i) in seg_points:
            draw.line((p1,p2), fill=path_color, width=width, joint="curve")
    
    return img

def draw_human_marker(img, x, y, scale=1.0, color=(255,60,60,255)):
    draw = ImageDraw.Draw(img, "RGBA")
    r = int(6 * scale)
    # head
    draw.ellipse((x-r, y-3*r, x+r, y-r), fill=color)
    # body
    bw = int(5 * scale); bh = int(10 * scale)
    draw.rectangle((x-bw, y-r, x+bw, y-r+bh), fill=color)
    return img

def interpolate_points(x1,y1,x2,y2,step_px=8):
    dist = math.hypot(x2-x1, y2-y1)
    if dist==0: return [(x1,y1)]
    steps = max(1,int(dist/step_px))
    pts=[]
    for i in range(steps+1):
        t=i/steps
        pts.append((round(x1+(x2-x1)*t), round(y1+(y2-y1)*t)))
    return pts

# pins & animation build
def draw_pin(img, x, y, color=(255,0,0,255), size=14):
    draw = ImageDraw.Draw(img, "RGBA")
    r = int(size/2)
    draw.ellipse((x-r, y-3*r, x+r, y-r), fill=color)
    tri = [(x, y-r//2), (x-r, y+r), (x+r, y+r)]
    draw.polygon(tri, fill=color)
    return img

def build_animation_sequence(path_nodes, step_px=8):
    seq = []
    base_imgs = {}
    floors_used = sorted({int(nodes.loc[n]["floor"]) for n in path_nodes})
    for f in floors_used:
        im = None
        for ext in ("png","jpg","jpeg"):
            p = f"map_floor{f}.{ext}"
            if os.path.exists(p):
                im = Image.open(p).convert("RGBA"); break
        if im is None:
            if f==0 and os.path.exists("map.png"):
                im = Image.open("map.png").convert("RGBA")
            else:
                im = Image.new("RGBA",(1157,1600),(255,255,255,255))
        base_imgs[f] = im

    # pins
    if len(path_nodes) >= 1:
        src = path_nodes[0]; dst = path_nodes[-1]
        sx, sy = int(nodes.loc[src]["x"]), int(nodes.loc[src]["y"])
        dx, dy = int(nodes.loc[dst]["x"]), int(nodes.loc[dst]["y"])
        sf = int(nodes.loc[src]["floor"]); df = int(nodes.loc[dst]["floor"])
        draw_pin(base_imgs[sf], sx, sy, color=(220,20,60,255), size=18)
        draw_pin(base_imgs[df], dx, dy, color=(40,180,40,255), size=18)

    for i in range(len(path_nodes)-1):
        a = path_nodes[i]; b = path_nodes[i+1]
        ra = nodes.loc[a]; rb = nodes.loc[b]
        fa, fb = int(ra["floor"]), int(rb["floor"])
        xa, ya = int(ra["x"]), int(ra["y"])
        xb, yb = int(rb["x"]), int(rb["y"])
        if fa == fb:
            pts = interpolate_points(xa,ya,xb,yb,step_px=step_px)
            for (px,py) in pts:
                seq.append((fa, px, py, i))
        else:
            for _ in range(6):
                seq.append((fa, xa, ya, i))
            for _ in range(6):
                seq.append((fb, xb, yb, i))
    if not seq:
        dst = path_nodes[-1]
        df = int(nodes.loc[dst]["floor"])
        dx,dy = int(nodes.loc[dst]["x"]), int(nodes.loc[dst]["y"])
        seq.append((df, dx, dy, 0))
    return base_imgs, seq

# image resize for display
def pil_to_bytes_resized(img, max_height=500):
    w,h = img.size
    if h>max_height:
        scale = max_height/float(h)
        img = img.resize((int(w*scale), int(h*scale)), Image.Resampling.LANCZOS)
    b = BytesIO(); img.convert("RGB").save(b, format="PNG")
    return b.getvalue()

# TTS helpers (FIXED: Background speech)
def speak_text_async(text):
    """Generate speech with debugging"""
    print(f"\n=== DEBUG TTS START ===")
    print(f"Text to speak: '{text}'")
    
    try:
        # Initialize engine
        engine = pyttsx3.init()
        print("✓ Engine initialized")
        
        # Set properties
        engine.setProperty('rate', 160)
        print(f"✓ Rate set to 160")
        
        # Get available voices
        voices = engine.getProperty('voices')
        print(f"✓ Found {len(voices)} voices")
        
        if len(voices) == 0:
            print("✗ ERROR: No voices found!")
            return None
        
        # Show first voice
        print(f"✓ Using voice: {voices[0].name}")
        
        # Create temp file
        tf = NamedTemporaryFile(delete=False, suffix=".wav")
        filename = tf.name
        tf.close()
        print(f"✓ Temp file: {filename}")
        
        # Save to file
        print("✓ Saving speech to file...")
        engine.save_to_file(text, filename)
        engine.runAndWait()
        print("✓ Speech generated")
        
        # Check file
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"✓ File exists, size: {file_size} bytes")
            
            if file_size < 100:
                print(f"✗ ERROR: File too small ({file_size} bytes)")
                os.unlink(filename)
                return None
            
            # Read file
            with open(filename, 'rb') as f:
                audio_bytes = f.read()
            
            print(f"✓ Read {len(audio_bytes)} bytes")
            os.unlink(filename)
            print("✓ Temp file cleaned up")
            
            return audio_bytes
            
        else:
            print("✗ ERROR: File was not created!")
            return None
            
    except Exception as e:
        print(f"✗ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        print("=== DEBUG TTS END ===\n")

# marker scale (small & professional)
MARKER_SCALE = 2.0

# corridor regex
CORRIDOR_RE = re.compile(r'^c\d+$', re.IGNORECASE)

def build_segmented_directions(path):
    """
    Returns a list of dicts where 'seg' matches the path node index (seg_idx from animation)
    """
    steps = []
    n = len(path)

    def coord(node):
        r = nodes.loc[node]
        return int(r["x"]), int(r["y"]), int(r["floor"])

    # --- START ---
    steps.append({
        "seg": 0,
        "text": f"Starting from {path[0]}",
        "type": "start",
        "frames": 0
    })

    # Get coordinates for all nodes
    coords = []
    for i, node in enumerate(path):
        if not CORRIDOR_RE.match(node):  # Only real nodes for turn detection
            x, y, floor = coord(node)
            coords.append((i, node, x, y, floor))

    # Analyze path for turns and key points
    for idx in range(1, len(coords) - 1):  # Skip first and last
        i, node, x, y, floor = coords[idx]
        prev_i, prev_node, prev_x, prev_y, prev_floor = coords[idx-1]
        next_i, next_node, next_x, next_y, next_floor = coords[idx+1]
        
        # Check for floor changes
        if prev_floor != floor:
            if "stair" in prev_node.lower():
                steps.append({
                    "seg": prev_i,  # At the stairs
                    "text": f"Climb the stairs to floor {floor}",
                    "type": "stairs",
                    "frames": 0
                })
            elif "lift" in prev_node.lower():
                steps.append({
                    "seg": prev_i,
                    "text": f"Take the lift to floor {floor}",
                    "type": "lift",
                    "frames": 0
                })
        
        # Turn detection using vector cross product
        v1x, v1y = x - prev_x, y - prev_y
        v2x, v2y = next_x - x, next_y - y
        
        # Calculate angle between vectors
        dot = v1x * v2x + v1y * v2y
        mag1 = math.sqrt(v1x**2 + v1y**2)
        mag2 = math.sqrt(v2x**2 + v2y**2)
        
        if mag1 > 0 and mag2 > 0:
            cos_angle = dot / (mag1 * mag2)
            cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
            angle = math.degrees(math.acos(cos_angle))
            
            # Determine turn direction using cross product
            cross = v1x * v2y - v1y * v2x
            
            # Only announce significant turns (more than 30 degrees)
            if angle > 30:
                if cross > 0:
                    turn = "Turn left"
                else:
                    turn = "Turn right"
                
                steps.append({
                    "seg": i,
                    "text": f"{turn} towards {next_node}",
                    "type": "turn",
                    "frames": 0
                })
        
        # Mention passing by important locations
        if not CORRIDOR_RE.match(node):
            steps.append({
                "seg": i,
                "text": f"Passing by {node}",
                "type": "passing",
                "frames": 0
            })

    # --- DESTINATION ---
    steps.append({
        "seg": n - 1,
        "text": f"You have reached your destination: {path[-1]}",
        "type": "destination",
        "frames": 0
    })
    
    # Sort by segment number and remove duplicates (keep first)
    steps.sort(key=lambda x: x["seg"])
    seen = set()
    unique_steps = []
    for step in steps:
        if step["seg"] not in seen:
            seen.add(step["seg"])
            unique_steps.append(step)
    
    return unique_steps

# session state defaults - KEEP IT SIMPLE
if "frames_meta" not in st.session_state: st.session_state["frames_meta"]=None
if "base_imgs" not in st.session_state: st.session_state["base_imgs"]={}
if "animation_seq" not in st.session_state: st.session_state["animation_seq"]=[]
if "playing" not in st.session_state: st.session_state["playing"]=False
if "src_input" not in st.session_state: st.session_state.src_input = ""
if "dst_input" not in st.session_state: st.session_state.dst_input = ""
if "stops_select" not in st.session_state: st.session_state.stops_select = []

# UI
st.markdown('<h1 class="title-text">🧭 Campus Compass Navigator</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle-text">Interactive indoor navigation with voice-guided directions</p>', unsafe_allow_html=True)

left_col, right_col = st.columns([1, 2])

with left_col:
    st.markdown('<div class="section-header">🎯 Navigation Controls</div>', unsafe_allow_html=True)
    
    # Category filter with icon
    st.selectbox("📍 **Category Filter**", all_categories, index=0, key="category_filter")
    
    # Source and Destination with better labels
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**From:**")
        src_input = typeahead_input("", node_list, "src_input", category_key="category_filter")
    with col2:
        st.markdown("**To:**")
        dst_input = typeahead_input("", node_list, "dst_input", category_key="category_filter")
    
    # Stops with icon
    extra = st.multiselect("🛑 **Add Stops**", options=node_list, key="stops_select",
                          help="Add intermediate stops in order")
    
    st.markdown("---")
    
    # Animation settings in a neat card
    st.markdown('<div class="section-header">⚙️ Animation Settings</div>', unsafe_allow_html=True)
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        fast_mode = st.checkbox("⚡ Fast Mode", value=False, help="Skip some frames for faster animation")
    with col_s2:
        voice_enabled = st.checkbox("🔊 Voice Guide", value=True, key="voice_enabled")
    
    # Speed slider with better labeling
    st.markdown("**🏃 Animation Speed**")
    speed = st.slider("", 1, 50, 4, 1, 
                     help="1 = Slowest, 50 = Fastest", 
                     label_visibility="collapsed")
    
    # Compute button with more prominence
    st.markdown("<br>", unsafe_allow_html=True)
    compute_btn = st.button("🚀 Compute & Animate Route", type="primary", use_container_width=True)

with right_col:
    st.markdown('<div class="section-header">🗺️ Interactive Map</div>', unsafe_allow_html=True)
    
    # Info box with icon
    with st.container():
        st.info("💡 **Tip:** Select nodes using the search above or pick from floor lists below. Enable voice for guided navigation.")
    
    # Floor maps with better presentation
    st.markdown("### 🏢 Campus Floor Maps")
    
    floors = sorted({int(nodes.loc[n,"floor"]) for n in node_list})
    thumb_cols = st.columns(min(5, len(floors)))
    
    for idx, f in enumerate(floors):
        p = None
        for ext in ("png","jpg","jpeg"):
            fn = f"map_floor{f}.{ext}"
            if os.path.exists(fn):
                p = fn; break
        if not p and f==0 and os.path.exists("map.png"):
            p = "map.png"
        
        with thumb_cols[idx % len(thumb_cols)]:
            if p:
                img = Image.open(p).convert("RGBA")
            else:
                img = Image.new("RGBA",(1157,1600),(245,247,250,255))
                draw = ImageDraw.Draw(img)
                # Add floor number to placeholder
                draw.text((500, 700), f"Floor {f}", fill=(100,100,100), font_size=100)
            
            thumb = img.copy()
            thumb.thumbnail((250, 350))
            st.image(pil_to_bytes_resized(thumb, max_height=350), caption=f"**Floor {f}**")
    
    # Floor node pickers with better organization
    st.markdown("### 📍 Quick Node Selection")
    
    # Create tabs for floors if many floors
    if len(floors) <= 5:
        picker_cols = st.columns(len(floors))
        for i, f in enumerate(floors):
            with picker_cols[i]:
                st.markdown(f"**Floor {f}**")
                floor_nodes = [n for n in node_list if int(nodes.loc[n,"floor"])==f]
                sel = st.selectbox(f"Select node", [""] + floor_nodes, key=f"picker_sel_{f}", label_visibility="collapsed")
                
                if sel and sel != "":
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        # Source button with callback
                        st.button("📍", 
                                key=f"src_{f}_{sel}",
                                help=f"Set {sel} as start",
                                on_click=set_source_callback,
                                args=(sel,))
                    
                    with col_btn2:
                        # Stop button with callback
                        st.button("🛑",
                                key=f"stop_{f}_{sel}",
                                help=f"Add {sel} as stop",
                                on_click=add_stop_callback,
                                args=(sel,))
                    
                    with col_btn3:
                        # Destination button with callback
                        st.button("🎯",
                                key=f"dest_{f}_{sel}",
                                help=f"Set {sel} as destination",
                                on_click=set_dest_callback,
                                args=(sel,))
    else:
        # Use tabs for many floors
        floor_tabs = st.tabs([f"Floor {f}" for f in floors])
        for i, (tab, f) in enumerate(zip(floor_tabs, floors)):
            with tab:
                floor_nodes = [n for n in node_list if int(nodes.loc[n,"floor"])==f]
                sel = st.selectbox(f"Select node on Floor {f}", [""] + floor_nodes, key=f"picker_sel_{f}")
                
                if sel:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Set as Start", key=f"set_src_{f}", use_container_width=True):
                            st.session_state["src_input"] = sel
                    with col2:
                        if st.button("Add as Stop", key=f"add_stop_{f}", use_container_width=True):
                            cur = st.session_state.get("stops_select", [])
                            if sel not in cur:
                                st.session_state["stops_select"] = cur + [sel]
                    with col3:
                        if st.button("Set as Destination", key=f"set_dst_{f}", use_container_width=True):
                            st.session_state["dst_input"] = sel
    
    st.markdown("---")

    # Map viewer with better styling
    viewer = st.empty()
    st.markdown("### 🎬 Animation Controls")

    control_cols = st.columns([1, 1, 2])
    with control_cols[0]:
        if st.button("▶️ Play", key="play_btn_main", type="primary", use_container_width=True, 
                    disabled=not st.session_state.get("frames_meta")):
            st.session_state["playing"] = True
    with control_cols[1]:
        if st.button("⏹️ Stop", key="stop_btn_main", use_container_width=True):
            st.session_state["playing"] = False
    
    # Progress and info areas
    info = st.empty()
    progress_bar = st.empty()
    audio_player = st.empty()
    
    # Diagnostics with better icon
    with st.expander("🔧 **Route Diagnostics & Directions**", expanded=False):
        diag = st.container()
        with diag:
            full_path = st.session_state.get("last_path", None)
            if full_path:
                st.markdown("**📊 Route Details**")
                st.write(f"**Total nodes:** {len(full_path)}")
                st.write(f"**Path:** {' → '.join(full_path[:5])}..." if len(full_path) > 5 else f"**Path:** {' → '.join(full_path)}")
                
                directions = st.session_state.get("segments", [])
                if directions:
                    st.markdown("**🗺️ Step-by-step Directions**")
                    for idx, step in enumerate(directions, 1):
                        st.markdown(f"{idx}. {step['text']}")

# COMPUTE ROUTE (FIXED ANIMATION SPEED)
if compute_btn:
    with st.spinner("🔍 Computing optimal route..."):
        # SIMPLIFIED: Buttons now update the same keys as widgets
        s = canonical_from_text(st.session_state.get("src_input", ""))
        d = canonical_from_text(st.session_state.get("dst_input", ""))
        stops = [canonical_from_text(x) for x in st.session_state.get("stops_select", []) if canonical_from_text(x)]
        
        if not s or not d:
            st.error("❌ Select valid source and destination (type or use floor pickers)."); st.stop()
        
        seq = [s] + [t for t in stops] + [d]

        bad = []
        for i in range(len(seq)-1):
            a,b = seq[i], seq[i+1]
            if a==b: continue
            if not nx.has_path(G, a, b):
                bad.append((a,b))
        if bad:
            msg = "❌ No path exists for pairs:\n" + "\n".join(f"• {a} → {b}" for a,b in bad)
            st.error(msg); st.stop()

        full=[]
        for i in range(len(seq)-1):
            a,b = seq[i], seq[i+1]
            sub = nx.shortest_path(G, a, b, weight="weight")
            if full and sub[0]==full[-1]:
                full.extend(sub[1:])
            else:
                full.extend(sub)

        st.session_state["last_path"] = full
        segments = build_segmented_directions(full)
        
        # FIXED: Base step size controls overall speed more than sleep
        step_px = max(2, 40 - int(speed * 2))  # Much slower movement
        
        base_imgs, animation_seq = build_animation_sequence(full, step_px=step_px)
        
        # Compute frame counts per segment
        segment_frame_count = defaultdict(int)
        for (_, _, _, seg_idx) in animation_seq:
            segment_frame_count[seg_idx] += 1
        
        # Attach frame counts to segments
        for seg in segments:
            seg["frames"] = segment_frame_count.get(seg["seg"], 1)
        
        st.session_state["segments"] = segments
        st.session_state["base_imgs"] = base_imgs
        st.session_state["animation_seq"] = animation_seq

        floors_used = sorted(list(base_imgs.keys()))
        st.session_state["frames_meta"] = {"path": full, "floors": floors_used}
        st.session_state["playing"] = False
        
        info.success(f"✅ Route computed: {len(full)} nodes, {len(animation_seq)} animation frames")

# Add this debugging section right after computing the route (around line 340)
if compute_btn and full:
    # Debug: Show what segments we have
    with diag:
        st.write("**DEBUG: Route Analysis**")
        st.write(f"Full path length: {len(full)} nodes")
        st.write(f"Animation sequence length: {len(animation_seq)} frames")
        
        # Show unique seg_idx values in animation
        unique_seg_idxs = set()
        for _, _, _, seg_idx in animation_seq:
            unique_seg_idxs.add(seg_idx)
        st.write(f"Animation has {len(unique_seg_idxs)} unique seg_idx values: {sorted(list(unique_seg_idxs))}")
        
        # Show directions segments
        st.write(f"Directions has {len(segments)} segments:")
        for i, seg in enumerate(segments):
            st.write(f"  {i}. seg={seg['seg']}, text='{seg['text']}'")
        
        # Try to match them
        st.write("**Matching attempt:**")
        for seg_idx in sorted(list(unique_seg_idxs)):
            matching = [s for s in segments if s["seg"] == seg_idx]
            if matching:
                st.write(f"  seg_idx={seg_idx}: FOUND '{matching[0]['text'][:50]}...'")
            else:
                st.write(f"  seg_idx={seg_idx}: NO MATCH in directions")

# VIEWER CONTROLS & PLAYBACK (FIXED FRAME_DELAY DEFINITION)
frames = st.session_state.get("frames")
meta = st.session_state.get("frames_meta")

if meta:
    floors_list = meta["floors"]
    sel_floor = st.selectbox("🏢 Floor view", options=floors_list, index=0, key="viewer_floor")

    # Show base image with full path
    base_imgs = st.session_state.get("base_imgs", {})
    if sel_floor in base_imgs and st.session_state.get("frames_meta", {}).get("path"):
        img_preview = base_imgs[sel_floor].copy()
        img_preview = draw_smooth_path_on_img(img_preview, st.session_state["frames_meta"]["path"], int(sel_floor), width=12, progress_idx=None)
        buf = pil_to_bytes_resized(img_preview, max_height=500)
        viewer.image(buf, use_container_width=True)
    else:
        viewer.info("ℹ️ Compute a route to preview maps & animation.")


# ANIMATION WITH ALL AUDIO PLAYING
if st.session_state.get("playing", False):
    base_imgs = st.session_state.get("base_imgs", {})
    seq = st.session_state.get("animation_seq", [])
    if not seq:
        st.session_state["playing"] = False
    else:
        segments = st.session_state.get("segments", [])
        voice_on = st.session_state.get("voice_enabled", False)
        
        # Define FRAME_DELAY - make it slower
        FRAME_DELAY = max(0.03, 0.5 / speed)  # Much slower base speed
        
        # Pre-generate ALL audio
        audio_segments = []
        if voice_on and segments:
            with audio_player.container():
                st.write("### 🔊 Preparing voice directions...")
                progress_bar_audio = st.progress(0)
                
                for idx, seg in enumerate(segments):
                    progress_bar_audio.progress((idx + 1) / len(segments))
                    audio_bytes = speak_text_async(seg["text"])
                    if audio_bytes and len(audio_bytes) > 1000:
                        import base64
                        audio_segments.append({
                            "seg": seg["seg"],
                            "text": seg["text"],
                            "type": seg.get("type", "direction"),
                            "audio_b64": base64.b64encode(audio_bytes).decode()
                        })
                    
                    with diag:
                        st.write(f"✓ {seg['text']}")
        
        # Clear preparation message
        audio_player.empty()
        
        # Create a container for audio playback
        audio_container = audio_player.container()
        
        # Track which audio we've played
        played_audio_indices = set()
        
        # Group frames by seg_idx for timing
        seg_idx_to_frames = defaultdict(list)
        for frame_idx, (floor, px, py, seg_idx) in enumerate(seq):
            seg_idx_to_frames[seg_idx].append(frame_idx)
        
        # Animation loop with FRACTIONAL PROGRESS TRACKING
        for frame_idx, (floor, px, py, seg_idx) in enumerate(seq):
            if not st.session_state.get("playing", False):
                break
            
            # ===== ADD THIS: Calculate EXACT fractional progress =====
            # Get all frames for current seg_idx
            frames_in_current_seg = seg_idx_to_frames.get(seg_idx, [])
            
            if frames_in_current_seg and len(frames_in_current_seg) > 0:
                # Find position within current segment (0.0 to 1.0)
                current_frame_in_seg = frame_idx - frames_in_current_seg[0]
                total_frames_in_seg = len(frames_in_current_seg)
                segment_progress = current_frame_in_seg / max(1, total_frames_in_seg)
                
                # Create fractional progress: seg_idx + progress through segment
                # Example: seg_idx=0 with 50% progress = 0.5
                fractional_progress = seg_idx + segment_progress
            else:
                fractional_progress = seg_idx
            # ===== END OF ADDED CODE =====
            
            # Check for audio to play
            if voice_on and audio_segments:
                # Find audio for current seg_idx
                for idx, audio_data in enumerate(audio_segments):
                    if audio_data["seg"] == seg_idx and idx not in played_audio_indices:
                        # Check if we're at a good point in the segment
                        frames = seg_idx_to_frames.get(seg_idx, [])
                        if frames and len(frames) > 0:
                            # Play at 25% through the segment
                            play_at_frame = frames[0] + int(len(frames) * 0.25)
                            
                            if frame_idx >= play_at_frame:
                                played_audio_indices.add(idx)
                                
                                # Play audio with HTML (autoplay after user interaction)
                                html_audio = f"""
                                <div style="margin: 5px 0;">
                                    <audio autoplay controls style="width: 100%;">
                                        <source src="data:audio/wav;base64,{audio_data['audio_b64']}" type="audio/wav">
                                    </audio>
                                    <p style="font-size: 0.9em; color: #666; margin: 2px 0;">{audio_data['text']}</p>
                                </div>
                                """
                                audio_container.markdown(html_audio, unsafe_allow_html=True)
                                
                                with diag:
                                    st.write(f"🔊 {audio_data['text']}")
                                break
            
            # Render frame with FRACTIONAL PROGRESS
            base = base_imgs[int(floor)].copy()
            base = draw_smooth_path_on_img(
                base,
                st.session_state["frames_meta"]["path"],
                int(floor),
                width=12,
                progress_idx=fractional_progress  # <-- CHANGED: Use fractional_progress instead of seg_idx
            )
            draw_human_marker(base, px, py, scale=MARKER_SCALE)
            viewer.image(pil_to_bytes_resized(base, max_height=500), use_container_width=True)
            
            # Progress bar
            progress = (frame_idx + 1) / len(seq)
            progress_bar.progress(progress, text=f"Progress: {int(progress*100)}%")
            
            time.sleep(FRAME_DELAY)
        
        # Animation complete
        progress_bar.empty()
        st.session_state["playing"] = False
        
        # Play any remaining audio
        if voice_on and audio_segments:
            for idx, audio_data in enumerate(audio_segments):
                if idx not in played_audio_indices:
                    html_audio = f"""
                    <div style="margin: 5px 0;">
                        <audio autoplay controls style="width: 100%;">
                            <source src="data:audio/wav;base64,{audio_data['audio_b64']}" type="audio/wav">
                        </audio>
                        <p style="font-size: 0.9em; color: #666; margin: 2px 0;">{audio_data['text']}</p>
                    </div>
                    """
                    audio_container.markdown(html_audio, unsafe_allow_html=True)
                    
                    with diag:
                        st.write(f"🎵 {audio_data['text']}")

        info.success("✅ Animation complete!")
    
    # Download button
    if sel_floor in base_imgs and st.session_state.get("frames_meta", {}).get("path"):
        img_dl = base_imgs[sel_floor].copy()
        img_dl = draw_smooth_path_on_img(img_dl, st.session_state["frames_meta"]["path"], int(sel_floor), width=12, progress_idx=None)
        last_buf = pil_to_bytes_resized(img_dl, max_height=500)
        st.download_button("💾 Download current floor map", last_buf, file_name=f"path_floor{sel_floor}.png", use_container_width=True)
else:
    viewer.info("ℹ️ Compute a route to preview maps & animation.")

# Footer
st.markdown("---")
st.markdown("""
<div class="footer">
    <p>🧭 <strong>Campus Compass Navigator</strong> | Built with Streamlit & NetworkX</p>
    <p>Navigate your campus with confidence • Real-time voice guidance • Interactive maps</p>
</div>
""", unsafe_allow_html=True)