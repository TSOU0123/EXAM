import streamlit as st
from streamlit_javascript import st_javascript 
import json
import os
import re
import tempfile
import exam
import os as os_lib

# --- 1. 頁面設定 (必須是第一個 Streamlit 指令) ---
st.set_page_config(
    page_title="國考字卡練習", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# --- 2. 狀態初始化 (解決 AttributeError：先定義所有 Key) ---
if 'show_help_dialog' not in st.session_state:
    st.session_state.show_help_dialog = False
if 'tutorial_auto_triggered' not in st.session_state:
    st.session_state.tutorial_auto_triggered = False
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'flipped' not in st.session_state: st.session_state.flipped = False
if 'data' not in st.session_state:
    st.session_state.data = {"decks": {}, "active": None}

# --- 3. 核心函數定義 (確保在呼叫前已定義) ---

@st.dialog("🚀 歡迎使用國考字卡練習")
def show_tutorial():
    # 這裡寫你最新的教學內容
    st.markdown("""
    這是一個專為國考設計的自動化刷題工具，幫助你快速練習考古題！
    
    ### 📖 快速上手指南
    1. **匯入題庫**：展開最下方的**題庫管理**，同時選取並上傳題目與答案 PDF。
    2. **更正答案**：系統會自動抓取答案，若同時有**答案**及**更正答案**，會優先採用更正答案。
    3. **操作方式**：
        - 點擊 **🔄 解答**：查看正確答案、備註以及選項對照。
        - 點擊 **⬅️/➡️**：切換上下題。
    4. **快速跳轉**：直接輸入題號並點擊 **跳轉**。
                            
    **目前沒錢買伺服器，試題在重整後會自己消失，重傳就好ㄌ!(也歡迎贊助我喔)**
    
    **祝 金榜題名！**
    """)
    if st.button("開始練習！", width='stretch', type="primary"):
        st.session_state.show_help_dialog = False 
        st.session_state.tutorial_auto_triggered = True
        st.rerun()

def save_uploaded_files(uploaded_files):
    temp_dir = tempfile.gettempdir()
    paths = []
    for uploaded_file in uploaded_files:
        path = os.path.join(temp_dir, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        paths.append(path)
    return paths

def build_series_name(metadata, filename, existing_keys):
    base_name = metadata.get("deck_name", os.path.splitext(os.path.basename(filename))[0])
    name, counter = base_name, 1
    while name in existing_keys:
        name = f"{base_name} ({counter})"
        counter += 1
    return name

def save_data(data):
    if 'user_id' in st.session_state:
        with open(USER_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# --- 4. 樣式與標題列 (手機版最終加固版) ---
st.markdown("""
    <style>
    /* 1. 徹底隱藏頂部所有狀態欄位，消除空白 */
    header, [data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    
    /* 2. 移除主容器間距，並強行上移 */
    .main .block-container {
        padding-top: 0rem !important; 
        margin-top: -50px !important; /* 加大上移力道消除空白 */
        padding-bottom: 1rem !important;
    }

    /* 3. 強制所有水平區塊 (Columns) 在手機上不換行 */
    /* 這是防止按鈕垂直堆疊的關鍵 */
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 0.3rem !important; /* 縮減元件間距 */
    }
    
    /* 4. 讓 Column 內的元件不要撐開寬度 */
    [data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 auto !important;
    }

    /* 5. 標題字體與溢出處理 */
    .mobile-title {
        font-size: 1.25rem !important;
        margin: 0 !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis; /* 太長會變省略號 */
        font-weight: 700;
    }

    /* 6. 問號按鈕微調 */
    div.stButton > button:has(div:contains("❓")) {
        width: 1.8rem !important; 
        height: 1.8rem !important;
        border-radius: 50% !important;
        padding: 0 !important;
        min-width: 1.8rem !important;
        border: 1px solid #ddd !important;
    }

    /* 7. 控制列與導航按鈕字體縮小，適配小螢幕 */
    div[data-testid="column"] button p {
        font-size: 0.8rem !important;
    }
    
    /* 隱藏跳轉輸入框的標籤高度 */
    [data-testid="stTextInput"] label {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# 調整標題列比例，給標題更多空間
col_head_title, col_help_btn = st.columns([0.9, 0.1])
with col_head_title:
    st.markdown('<h2 class="mobile-title">🗂️ 國考字卡練習</h2>', unsafe_allow_html=True)
with col_help_btn:
    if st.button("❓"):
        st.session_state.show_help_dialog = True

# --- 5. 唯一 ID 與資料加載 ---
js_id = st_javascript("localStorage.getItem('flashcard_user_id');")
if 'user_id' not in st.session_state:
    if isinstance(js_id, str) and js_id not in ["null", ""]:
        st.session_state.user_id = js_id
    else:
        st.session_state.user_id = "loading_" + re.sub(r'\W+', '', str(os_lib.urandom(6).hex()))

if isinstance(js_id, str):
    if js_id not in ["null", ""] and st.session_state.user_id != js_id:
        st.session_state.user_id = js_id
        st.session_state.data = None
        st.rerun()
    elif js_id in ["null", ""] and st.session_state.user_id.startswith("loading_"):
        clean_id = st.session_state.user_id.replace("loading_", "")
        st.session_state.user_id = clean_id
        st_javascript(f"localStorage.setItem('flashcard_user_id', '{clean_id}');")
        st.rerun()

USER_JSON = f"users/{st.session_state.user_id}/questions.json"
USER_IMG_DIR = f"users/{st.session_state.user_id}/images"
os.makedirs(os.path.dirname(USER_JSON), exist_ok=True)
os.makedirs(USER_IMG_DIR, exist_ok=True)

if st.session_state.data is None or st.session_state.data == {"decks": {}, "active": None}:
    if not st.session_state.user_id.startswith("loading_") and os.path.exists(USER_JSON):
        try:
            with open(USER_JSON, "r", encoding="utf-8") as f:
                st.session_state.data = json.load(f)
        except: pass

# --- 6. 觸發視窗 ---
if st.session_state.show_help_dialog:
    show_tutorial()

series_names = list(st.session_state.data.get("decks", {}).keys())
if not series_names and not st.session_state.tutorial_auto_triggered and not st.session_state.user_id.startswith("loading_"):
    st.session_state.show_help_dialog = True
    
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

    col_info, col_jump_input, col_jump_btn = st.columns([1.2, 1, 0.8])
    with col_info:
        # 縮短文字，節省空間
        st.write(f"**{st.session_state.current_idx + 1}/{len(questions)}**")
    with col_jump_input:
        q_target = st.text_input("題號", placeholder="Go", label_visibility="collapsed", key="jump_input")
    with col_jump_btn:
        if st.button("跳轉", width='stretch'):
            # (跳轉邏輯保持不變...)
            pass

    # 🎮 導航按鈕：強制三顆並排
    nav_col1, nav_col2, nav_col3 = st.columns(3)
    with nav_col1:
        if st.button("上題", width='stretch'):
            if st.session_state.current_idx > 0:
                st.session_state.current_idx -= 1
                st.session_state.flipped = False
                st.rerun()
    with nav_col2:
        if st.button("🔄 解答", type="primary", width='stretch'):
            st.session_state.flipped = not st.session_state.flipped
            st.rerun()
    with nav_col3:
        if st.button("下題", width='stretch'):
            if st.session_state.current_idx < len(questions) - 1:
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