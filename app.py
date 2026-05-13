import streamlit as st
from streamlit_javascript import st_javascript 
import json
import os
import re
import tempfile
import exam
import os as os_lib

# --- 1. 頁面設定 ---
st.set_page_config(
    page_title="國考字卡練習", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# --- 2. 標題與 CSS 預載 (防止白畫面與重複標題) ---
# 先定義好標題列樣式，確保問號按鈕正確顯示
st.markdown("""
    <style>
    .mobile-title {
        font-size: 1.8rem !important;
        margin: 0 !important;
        line-height: 2.5rem !important;
        white-space: nowrap;
    }
    div.stButton > button:has(div:contains("❓")) {
        width: 2.5rem !important;
        height: 2.5rem !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        min-width: 2.5rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# 這裡是全程式「唯一」繪製頂部標題的地方
col_head_title, col_help_btn = st.columns([8.5, 1.5])
with col_head_title:
    st.markdown('<h2 class="mobile-title">🗂️ 國考字卡練習</h2>', unsafe_allow_html=True)
with col_help_btn:
    if st.button("❓", help="點擊查看教學"):
        st.session_state.show_help_dialog = True

@st.dialog("🚀 歡迎使用國考字卡練習")
def show_tutorial():
    st.markdown("""
    這是一個專為國考設計的自動化刷題工具，幫助你快速練習考古題！
    
    ### 📖 快速上手指南
    1. **匯入題庫**：展開最下方的**題庫管理**，同時選取並上傳題目與答案 PDF。
    2. **更正答案**：系統會自動抓取答案，若有 同時有**答案**及**更正答案** ，會優先採用**更正答案**。
    3. **操作方式**：
        - 點擊 **🔄 解答**：查看正確答案、備註以及選項對照。
        - 點擊 **⬅️/➡️**：切換上下題。
    4. **快速跳轉**：直接輸入題號並點擊 **跳轉**。
    5. **卡片清單**：可以看到目前有的字卡，並切換想刷的題目。
    6. **大量匯入**：同時上傳多組題目與答案 PDF，系統會自動分類並建立不同系列。
                            
                
    **目前沒錢買伺服器，試題在重整後會自己消失，重傳就好ㄌ!(也歡迎贊助我喔)**           
    
    **祝 金榜題名！**
    """)
    
    if st.button("開始練習！", width='stretch', type="primary"):
        # 修正這裡的變數名稱，確保與外部一致
        st.session_state.show_help_dialog = False 
        st.session_state.tutorial_auto_triggered = True
        st.rerun()

# 嘗試從瀏覽器讀取舊 ID
js_id = st_javascript("localStorage.getItem('flashcard_user_id');")

# 第一階段：確保 Session 隨時都有 ID，防止程式卡死 (白畫面)
if 'user_id' not in st.session_state:
    if isinstance(js_id, str) and js_id not in ["null", ""]:
        # A. 如果 JS 跑得快，直接拿回舊 ID
        st.session_state.user_id = js_id
    else:
        # B. JS 還沒好或新使用者，先隨機生一個「暫時標籤」，讓畫面先跑出來
        st.session_state.user_id = "loading_" + re.sub(r'\W+', '', str(os_lib.urandom(6).hex()))

# 第二階段：背景校正 (核心邏輯：在後台偷偷換回正確的 ID)
if isinstance(js_id, str):
    # 如果瀏覽器有舊 ID，且目前用的是暫時標籤，則自動切換並重整
    if js_id not in ["null", ""] and st.session_state.user_id != js_id:
        st.session_state.user_id = js_id
        # 強制清除舊資料快取並重整
        if 'data' in st.session_state: del st.session_state.data
        st.rerun()
    # 如果確定是新使用者 (JS 跑完且沒存過 ID)，將目前的暫時標籤「去標籤化」存入瀏覽器
    elif js_id in ["null", ""] and st.session_state.user_id.startswith("loading_"):
        clean_id = st.session_state.user_id.replace("loading_", "")
        st.session_state.user_id = clean_id
        st_javascript(f"localStorage.setItem('flashcard_user_id', '{clean_id}');")
        if 'data' in st.session_state: del st.session_state.data
        st.rerun()

# 第 79-80 行
_user_dir = os.path.join("users", st.session_state.user_id)
os.makedirs(_user_dir, exist_ok=True)
USER_JSON = os.path.join(_user_dir, "questions.json")
USER_IMG_DIR = os.path.join(_user_dir, "images")

# --- 第三階段：載入資料 (強化防禦與正確呼叫版) ---
if 'data' not in st.session_state or st.session_state.data is None:
    st.session_state.data = {"decks": {}, "active": None}
    
    # 只有當 ID 確定且非初始載入狀態，才讀取檔案
    if not st.session_state.user_id.startswith("loading_"):
        if os.path.exists(USER_JSON):
            try:
                with open(USER_JSON, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, dict) and "decks" in d:
                        st.session_state.data = d
            except Exception:
                pass

# --- 修正版：正確呼叫教學視窗，移除多餘的重複讀取 ---
if st.session_state.show_help_dialog:
    show_tutorial()

# --- 初始化其他狀態 ---
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'flipped' not in st.session_state: st.session_state.flipped = False

# 新增控制狀態
if 'show_help_dialog' not in st.session_state:
    st.session_state.show_help_dialog = False
if 'tutorial_auto_triggered' not in st.session_state:
    st.session_state.tutorial_auto_triggered = False



# --- 2. 修改資料處理函數 ---
def load_data(): 
    # 直接在函式內使用全域的 USER_JSON
    if os.path.exists(USER_JSON):
        with open(USER_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "decks" in data:
            return data
    return {"decks": {}, "active": None}

def save_data(data): 
    with open(USER_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_series_name(metadata, question_path, existing_decks):
    # 直接使用解析出來的簡潔標題作為系列名稱
    deck_name = metadata.get("deck_name", "未知題庫").strip()
    
    # 如果標題已經存在於清單中，才加上編號區分
    if deck_name not in existing_decks:
        return deck_name
    
    suffix = 2
    while True:
        candidate = f"{deck_name} ({suffix})"
        if candidate not in existing_decks:
            return candidate
        suffix += 1

def find_existing_series(metadata, question_path, existing_decks):
    # 改為直接比對標題名稱是否已存在
    deck_name = metadata.get("deck_name", "").strip()
    if deck_name in existing_decks:
        return deck_name
    return None

def normalize_name(name):
    return re.sub(r"[\W_]+", "", name).lower()


def save_uploaded_files(uploaded_files):
    dest_folder = tempfile.mkdtemp(prefix="streamlit_pdf_")
    saved_paths = []
    for uploaded in uploaded_files:
        safe_path = os.path.join(dest_folder, uploaded.name)
        with open(safe_path, "wb") as f:
            f.write(uploaded.getbuffer())
        saved_paths.append(safe_path)
    return saved_paths

# --- 取得題庫清單 (安全讀取) ---
series_names = list(st.session_state.data.get("decks", {}).keys())

# 自動教學觸發判斷 (針對新使用者/空題庫)
if not series_names and not st.session_state.tutorial_auto_triggered:
    # 只有當 ID 已經校正完畢（非 loading）且真的沒題庫時才自動跳教學
    if not st.session_state.user_id.startswith("loading_"):
        st.session_state.show_help_dialog = True
        st.session_state.tutorial_auto_triggered = True
    
active_series = st.session_state.data.get("active")

# 決定目前要顯示的題目與 Metadata
if series_names:
    if active_series not in series_names:
        active_series = series_names[0]
        st.session_state.data["active"] = active_series
    
    deck = st.session_state.data["decks"].get(active_series, {})
    questions = deck.get("questions", [])
    metadata = deck.get("metadata", {})
else:
    questions = []
    metadata = {"deck_name": "🗂️ 尚未載入題庫"}

# --- 修正版：加入空題庫與索引安全保護 ---
if not questions:
    st.warning("⚠️ 目前題庫是空的！請點擊下方的「題庫管理與檔案匯入」展開並匯入 PDF 檔案。")
else:
    # 🎯 標題
    if series_names:
        st.subheader(metadata.get("deck_name", "字卡練習"))
    
    # 安全索引檢查：防止切換題庫時索引溢出
    if st.session_state.current_idx >= len(questions):
        st.session_state.current_idx = 0

    # 📱 控制列：進度、跳轉
    col_info, col_jump_input, col_jump_btn = st.columns([2.2, 1, 0.8])
    with col_info:
        st.write(f"進度: **{st.session_state.current_idx + 1}/{len(questions)}**")
    with col_jump_input:
        q_target = st.text_input("跳轉", placeholder="題號", label_visibility="collapsed", key="jump_input")
    with col_jump_btn:
        if st.button("跳轉", width='stretch') and q_target.strip():
            input_num = re.sub(r'\D', '', q_target) 
            if input_num:
                target_id = str(int(input_num))
                target_idx = next((i for i, q in enumerate(questions) if str(q["id"]) == target_id), None)
                if target_idx is not None:
                    st.session_state.current_idx = target_idx
                    st.session_state.flipped = False
                    st.rerun()

    # 🎮 快速刷題按鈕
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ 上題", width='stretch') and st.session_state.current_idx > 0:
            st.session_state.current_idx -= 1
            st.session_state.flipped = False
            st.rerun()
    with col2:
        if st.button("🔄 解答", type="primary", width='stretch'):
            st.session_state.flipped = not st.session_state.flipped
            st.rerun()
    with col3:
        if st.button("下題 ➡️", width='stretch') and st.session_state.current_idx < len(questions) - 1:
            st.session_state.current_idx += 1
            st.session_state.flipped = False
            st.rerun()

    # 🃏 字卡內容 (放在 if questions 內確保安全)
    with st.container(border=True):
        q = questions[st.session_state.current_idx]
        if not st.session_state.flipped:
            st.markdown(f"**Q{q['id']}**")
            st.write(q['text'])
            if "image" in q and os.path.exists(q['image']):
                st.image(q['image'], use_container_width=True)
            for key, val in q['options'].items():
                if val: st.write(f"({key}) {val}")
        else:
            st.markdown("✅ **正確答案**")
            ans_val = q['answer']
            if len(ans_val) <= 5:
                st.markdown(f"<h2 style='text-align: center; color: #ff4b4b; margin: 10px 0;'>{ans_val}</h2>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='color: #ff4b4b; font-size: 16px; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 10px; margin: 10px 0;'>{ans_val}</div>", unsafe_allow_html=True)
            st.markdown("---")
            for key, val in q['options'].items():
                if key in ans_val and len(ans_val) < 5:
                    st.markdown(f"**<span style='color: #ff4b4b;'>({key}) {val}</span>**", unsafe_allow_html=True)
                else:
                    st.write(f"({key}) {val}")

# --- 5. 管理區域 (移至底部並折疊) ---
with st.expander("🛠️ 題庫管理與檔案匯入"):
    uploaded_files = st.file_uploader(
        "拖曳上傳題目與答案 PDF",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}"
    )

        # --- 3. 修改解析邏輯中的資料夾路徑 ---
    if st.button("🚀 開始分類匯入", type="primary", width='stretch'):
            saved_paths = save_uploaded_files(uploaded_files)
            file_pairs = exam.find_all_pairs(saved_paths)

            for question_pdf, answer_pdf in file_pairs:
                deck_id = os.path.basename(question_pdf)
                with st.spinner(f"正在解析 {deck_id} ..."):
                    # 1. 取得 Metadata 決定系列名稱
                    _, m_data = exam.extract_exam_data(question_pdf)
                    s_name = build_series_name(m_data, question_pdf, st.session_state.data["decks"].keys())
                    
                    # 2. 為該系列建立獨立圖片資料夾，防止圖片覆蓋
                    deck_img_dir = os.path.join(USER_IMG_DIR, re.sub(r'\W+', '', s_name))
                    os.makedirs(deck_img_dir, exist_ok=True)
                    
                    # 3. 執行解析與補圖
                    img_map = exam.get_pdf_images(question_pdf, output_dir=deck_img_dir)
                    raw_qs, _ = exam.extract_exam_data(question_pdf)
                    ans_list, remarks_map = exam.parse_answer_pdf(answer_pdf) if answer_pdf else ([], {})

                    # 4. 配對答案與圖片路徑
                    img_pointers = {p: 0 for p in img_map.keys()}
                    for q in raw_qs:
                        idx = int(q["id"]) - 1
                        q["answer"] = ans_list[idx] if idx < len(ans_list) else "N/A"
                        # (這裡保留你原本的 # 號更正與圖片判定邏輯...)
                        if "image" in q: # 確保路徑指向正確的子資料夾
                             pass 
                    
                    # 儲存到 session_state
                    st.session_state.data["decks"][s_name] = {"metadata": m_data, "questions": raw_qs}
                    st.session_state.data["active"] = s_name

            save_data(st.session_state.data)
            st.session_state.uploader_key += 1 
            st.success("🎉 分類匯入完成！")
            st.rerun()

    if series_names:
        st.markdown("### 目前卡片清單")
        for name in series_names:
            count = len(st.session_state.data["decks"][name]["questions"])
            marker = " ✅" if name == active_series else ""
            st.write(f"- {name} ({count} 題){marker}")

        selected_series = st.selectbox("切換字卡系列", series_names, index=series_names.index(active_series))
        if selected_series != active_series:
            st.session_state.data["active"] = selected_series
            st.session_state.current_idx = 0
            st.session_state.flipped = False
            save_data(st.session_state.data)
            st.rerun()

        if st.button("🗑️ 刪除目前選中系列", type="secondary"):
            st.session_state.data["decks"].pop(active_series, None)
            remaining = list(st.session_state.data["decks"].keys())
            st.session_state.data["active"] = remaining[0] if remaining else None
            save_data(st.session_state.data)
            st.session_state.current_idx = 0
            st.session_state.flipped = False
            st.rerun()

            # --- 新增：清除全部資料 (含圖片) 的兩段式確認邏輯 ---
        st.markdown("---")
        
        # 初始化確認狀態
        if 'confirm_clear_all' not in st.session_state:
            st.session_state.confirm_clear_all = False

        if not st.session_state.confirm_clear_all:
            # 第一階段：顯示初始按鈕
            if st.button("🚨 清除所有題庫與圖片", type="secondary", width='stretch'):
                st.session_state.confirm_clear_all = True
                st.rerun()
        else:
            # 第二階段：顯示確認與取消按鈕
            st.warning("⚠️ **確定要刪除所有資料嗎？** 這將移除所有已匯入的題庫與 images 資料夾內的圖片。")
            col_yes, col_no = st.columns(2)
            
            with col_yes:
                if st.button("🔥 確定，全部刪除", type="primary", width='stretch'):
                    # 1. 刪除伺服器檔案
                    if os.path.exists(USER_JSON):
                        os.remove(USER_JSON)
                    if os.path.exists(USER_IMG_DIR):
                        import shutil
                        shutil.rmtree(USER_IMG_DIR)
                    
# 2. 清除瀏覽器 localStorage 紀錄
                    st_javascript("localStorage.removeItem('flashcard_user_id');")
                    
                    # 3. 清除 Session 狀態，強制下次重新生成 ID
                    del st.session_state.user_id
                    
                    # 3. 重置狀態
                    st.session_state.data = {"decks": {}, "active": None}
                    st.session_state.current_idx = 0
                    st.session_state.flipped = False
                    st.session_state.confirm_clear_all = False
                    
                    st.success("💥 所有資料已清空！")
                    st.rerun()
            
            with col_no:
                if st.button("❌ 取消", width='stretch'):
                    st.session_state.confirm_clear_all = False
                    st.rerun()

st.write("") # 留空行
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; padding-bottom: 20px;'>
        <a href='https://www.tsoutest0123.com/' target='_blank' style='color: #888; text-decoration: none; font-size: 13px; font-weight: 500;'>
             www.tsoutest0123.com
        </a>
    </div>
    """, 
    unsafe_allow_html=True
)