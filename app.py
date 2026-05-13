import streamlit as st
from streamlit_javascript import st_javascript 
import json
import os
import re
import tempfile
import exam
import os as os_lib # 用於產生隨機數

# --- 1. 頁面設定必須放在第一行 ---
st.set_page_config(
    page_title="國考字卡練習", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# --- 2. 唯一 ID 初始化 (確保瀏覽器獨立且持久) ---
# 取得瀏覽器存儲的 ID
stored_id = st_javascript("localStorage.getItem('flashcard_user_id');")

if 'user_id' not in st.session_state:
    if stored_id is not None and stored_id != "":
        # A. 成功從瀏覽器讀回舊 ID
        st.session_state.user_id = stored_id
    elif stored_id is None:
        # B. 等待 JavaScript 回傳，先停止執行後續代碼避免產生錯誤 ID
        st.stop() 
    else:
        # C. 確定是新使用者，產生唯一 ID 並存入瀏覽器
        # 使用 os.urandom 確保隨機性，防止與他人連通
        new_id = re.sub(r'\W+', '', str(os_lib.urandom(4).hex()))
        st.session_state.user_id = new_id
        st_javascript(f"localStorage.setItem('flashcard_user_id', '{new_id}');")

# 鎖定該使用者的專屬檔案路徑
USER_JSON = f"questions_{st.session_state.user_id}.json"
USER_IMG_DIR = f"images_{st.session_state.user_id}"

# 先設定頁面，再進行邏輯運算
st.set_page_config(
    page_title="國考字卡練習", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)


# --- app.py 中的 CSS 修正 ---
st.markdown("""
    <style>
    /* 1. 全域禁止選取與長按選單 (排除輸入框) */
    * {
        -webkit-user-select: none;
        user-select: none;
        -webkit-touch-callout: none; /* 禁用 iOS 放大鏡與選單 */
    }
    input, textarea {
        -webkit-user-select: text !important;
        user-select: text !important;
    }

    /* 2. 強制鎖定視窗寬度，移除所有左右邊距 */
    .main .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }

    /* 3. 強制所有欄位橫向併排，絕對不換行也不產生捲軸 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 4px !important; /* 極窄間距 */
        align-items: center !important;
    }
    
    /* 確保 Column 不會因為內容太寬而撐開 */
    [data-testid="stColumn"] {
        min-width: 0px !important;
        flex: 1 1 auto !important;
    }

    /* 4. 按鈕樣式：確保文字不換行且填滿格子 */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        padding: 0px 2px !important;
        white-space: nowrap !important;
        height: 2.6rem !important;
    }
    /* 縮小卡片內部的間距 */
        .stContainer {
            padding: 0.8rem !important;
        }
        /* 縮小水平分割線的間距 */
        hr {
            margin: 0.5rem 0 !important;
        }
        /* 讓背面標紅的文字更顯眼 */
        span[style*="color: #ff4b4b"] {
            background-color: rgba(255, 75, 75, 0.1);
            padding: 2px 4px;
            border-radius: 4px;
        }
    .top-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
    }

/* 針對手機版縮小標題字體，並讓問號按鈕圓形置中且與標題等高 */
    @media (max-width: 600px) {
        .mobile-title {
            font-size: 1.8rem !important; /* 調整標題大小 */
            margin: 0 !important;
            line-height: 2.5rem !important; /* 鎖定行高，用於對齊按鈕 */
            white-space: nowrap;
        }
        /* 🎯 問號按鈕：正圓形、垂直水平置中 🎯 */
        div.stButton > button:has(div:contains("❓")) {
            width: 2.5rem !important; /* 寬度與標題行高一致 */
            height: 2.5rem !important; /* 高度與標題行高一致 */
            border-radius: 50% !important; /* 強制圓形 */
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 !important;
            min-width: 2.5rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)            

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'flipped' not in st.session_state: st.session_state.flipped = False

# 新增控制狀態
if 'show_help_dialog' not in st.session_state:
    st.session_state.show_help_dialog = False
if 'tutorial_auto_triggered' not in st.session_state:
    st.session_state.tutorial_auto_triggered = False

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
                
    **目前沒錢買伺服器，試題可能過一段時間後會自己消失，重傳就好ㄌ!(也歡迎贊助我喔)**           
    
    **祝 金榜題名！**
    """)
    
    if st.button("開始練習！", width='stretch', type="primary"):
        # 修正這裡的變數名稱，確保與外部一致
        st.session_state.show_help_dialog = False 
        st.session_state.tutorial_auto_triggered = True
        st.rerun()

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

# --- 3. 載入資料並決定當前題目 ---
if 'data' not in st.session_state:
    st.session_state.data = load_data()

# 抓取目前的題庫清單
# --- app.py 載入資料後的邏輯區塊 ---

# 取得目前是否有題庫
series_names = list(st.session_state.data.get("decks", {}).keys())


# 使用 [7.5, 2.5] 比例，讓加大的標題有足夠空間，同時按鈕不跑位
col_head_title, col_help_btn = st.columns([8.5, 1.5])

with col_head_title:
    # 使用 h2 配合自定義 CSS 類別
    st.markdown('<h2 class="mobile-title">🗂️ 國考字卡練習</h2>', unsafe_allow_html=True)

with col_help_btn:
    if st.button("❓", help="點擊查看教學"):
        st.session_state.show_help_dialog = True

# --- 2. 自動教學觸發判斷 (針對新使用者/空題庫) ---
series_names = list(st.session_state.data.get("decks", {}).keys())

# 如果沒題庫，且這一次開啟網頁還沒自動跳過教學，就設為 True
if not series_names and not st.session_state.tutorial_auto_triggered:
    st.session_state.show_help_dialog = True
    st.session_state.tutorial_auto_triggered = True 

# --- 3. 【核心修正】全程式唯一一個呼叫對話框的地方 ---
if st.session_state.show_help_dialog:
    show_tutorial()
    
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

# --- 修正後 ---
if not questions:
    st.warning("⚠️ 目前題庫是空的！請點擊下方的「題庫管理與檔案匯入」展開並匯入 PDF 檔案。")
else:
# 🎯 標題
    st.subheader(metadata.get("deck_name", "字卡練習"))
    
    # 📱 調整比例：進度佔 2.2，輸入框佔 1，按鈕佔 0.8
    # 這樣的「不等寬」設計最符合手機窄螢幕
    col_info, col_jump_input, col_jump_btn = st.columns([2.2, 1, 0.8])
    
    with col_info:
        st.write(f"進度: **{st.session_state.current_idx + 1}/{len(questions)}**")
        
    with col_jump_input:
        q_target = st.text_input("跳轉", placeholder="題號", label_visibility="collapsed", key="jump_input")
        
    with col_jump_btn:
        if st.button("跳轉", width='stretch'):
            # 1. 只有在框框「真的有輸入內容」時才執行判斷
            if q_target.strip(): 
                try:
                    # 提取輸入字串中的純數字部分 (例如輸入 "05" 會變 "5")
                    input_num = re.sub(r'\D', '', q_target) 
                    
                    if input_num:
                        target_id = str(int(input_num))
                        target_idx = next((i for i, q in enumerate(questions) if str(q["id"]) == target_id), None)
                        
                        if target_idx is not None:
                            st.session_state.current_idx = target_idx
                            st.session_state.flipped = False
                            st.rerun()
                        else:
                            # 只有在「找不到該題號」時才提示
                            st.toast(f"❌ 找不到題號：{target_id}", icon="⚠️")
                    else:
                        # 如果輸入了一堆字但裡面沒數字，才提示
                        st.toast("⚠️ 請輸入有效數字", icon="ℹ️")
                except:
                    # 發生非預期錯誤時靜默處理，不干擾使用者
                    pass
            
            # 2. 如果框框是空的 (if q_target.strip() 為 False)
            # 點按鈕會直接不執行任何動作，也不會跳出「請輸入數字」的警告

# --- 【快速刷題】控制按鈕 ---
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

# --- 字卡內容區域 ---
    with st.container(border=True):
        q = questions[st.session_state.current_idx]
        if not st.session_state.flipped:
            # 📄 正面：題目
            st.markdown(f"**Q{q['id']}**")
            st.write(q['text'])
            if "image" in q and os.path.exists(q['image']):
                st.image(q['image'], width='stretch')
            for key, val in q['options'].items():
                if val: st.write(f"({key}) {val}")
        else:
            # 💡 背面：答案與選項對照
            st.markdown("✅ **正確答案**")
            
            # --- 核心修正：動態字體大小 ---
            ans_val = q['answer']
            if len(ans_val) <= 5: # 如果是單一字母 (如 A, B, C, D)
                st.markdown(f"<h2 style='text-align: center; color: #ff4b4b; margin: 10px 0;'>{ans_val}</h2>", unsafe_allow_html=True)
            else: # 如果是長篇備註 (如：答A、C給分)
                st.markdown(f"<div style='color: #ff4b4b; font-size: 16px; font-weight: bold; border-left: 4px solid #ff4b4b; padding-left: 10px; margin: 10px 0;'>{ans_val}</div>", unsafe_allow_html=True)
            
            # --- 核心修正：背面也顯示選項內容 ---
            st.markdown("---")
            for key, val in q['options'].items():
                # 如果該選項是正確答案，將文字標紅加粗方便一眼辨識
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
                    # 核心修正：路徑改為 USER_IMG_DIR
                    img_map = exam.get_pdf_images(question_pdf, output_dir=USER_IMG_DIR)
                    raw_qs, m_data = exam.extract_exam_data(question_pdf)
                    ans_list, remarks_map = exam.parse_answer_pdf(answer_pdf) if answer_pdf else ([], {})

                    img_pointers = {p: 0 for p in img_map.keys()}

                    for q in raw_qs:
                        idx = int(q["id"]) - 1
                        raw_ans = ans_list[idx] if idx < len(ans_list) else "N/A"
                        if raw_ans == "#" and q["id"] in remarks_map:
                            q["answer"] = f"更正：{remarks_map[q['id']]}"
                        else:
                            q["answer"] = raw_ans

                        needs_image = False
                        if any(k in q["text"] for k in ["圖", "下圖", "附圖"]):
                            needs_image = True
                        if not q["options"] or all(val == "" for val in q["options"].values()):
                            needs_image = True
                        
                        if needs_image:
                            for p in [q["page"], q["page"] + 1]:
                                if p in img_map and img_pointers.get(p, 0) < len(img_map[p]):
                                    q["image"] = img_map[p][img_pointers[p]]
                                    img_pointers[p] += 1
                                    break

                    s_name = find_existing_series(m_data, question_pdf, st.session_state.data["decks"].keys())
                    if not s_name:
                        s_name = build_series_name(m_data, question_pdf, st.session_state.data["decks"].keys())
                    
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