import fitz  # PyMuPDF
import re
import json
import os
import argparse

# --- exam.py 修改處：高品質渲染截圖版 ---

def get_pdf_images(pdf_path, output_dir="images"):
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    doc = fitz.open(pdf_path)
    img_map = {} 
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        paths = []
        
        # 1. 取得頁面上所有的文字區塊 (用來定義「題目領土」)
        blocks = page.get_text("blocks")
        # 2. 取得所有的影像
        image_list = page.get_images(full=True)
        # 3. 取得所有的向量線條
        drawings = page.get_drawings()
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            img_rects = page.get_image_rects(xref)
            if not img_rects: continue
            
            img_rect = img_rects[0]
            
            # --- 步驟 A：找尋該圖片所屬的「文字領土」 ---
            # 找出與這張圖最接近或包含這張圖的文字區塊，以此作為截圖的高限與底限
            territory_top = 0
            territory_bottom = page.rect.height
            
            # 簡單邏輯：找出圖片上方最近的文字 block 和下方最近的文字 block
            # 或者更直接：限制截圖的高度不要超過圖片上下各 100 像素，且避開其他 block
            for b in blocks:
                b_rect = fitz.Rect(b[:4])
                # 如果這個文字區塊在圖片上方且離很近，設定為頂部限制
                if b_rect.y1 < img_rect.y0 and (img_rect.y0 - b_rect.y1) < 150:
                    territory_top = max(territory_top, b_rect.y0 - 10)
                # 如果這個文字區塊在圖片下方且離很近，設定為底部限制
                if b_rect.y0 > img_rect.y1 and (b_rect.y0 - img_rect.y1) < 150:
                    territory_bottom = min(territory_bottom, b_rect.y1 + 10)

            # --- 步驟 B：智能合併向量線條，但限制在領土內 ---
            combined_rect = img_rect
            search_buffer = 35 # 縮小搜尋範圍，避免抓到別題
            search_rect = img_rect + (-search_buffer, -search_buffer, search_buffer, search_buffer)
            
            for d in drawings:
                d_rect = d["rect"]
                # 只有當線條很小（避免抓到頁面邊框）且在搜尋範圍內時才合併
                if d_rect.intersects(search_rect) and d_rect.width < 400 and d_rect.height < 400:
                    # 合併後的範圍不能超過領土
                    temp_rect = combined_rect | d_rect
                    if temp_rect.y0 >= territory_top and temp_rect.y1 <= territory_bottom:
                        combined_rect = temp_rect

            # --- 步驟 C：最終裁切範圍修正 ---
            final_rect = fitz.Rect(
                max(0, combined_rect.x0 - 5),
                max(territory_top, combined_rect.y0 - 5),
                min(page.rect.width, combined_rect.x1 + 5),
                min(territory_bottom, combined_rect.y1 + 5)
            )

            # 如果裁切後的寬度或高度太小，則放棄
            if final_rect.width < 5 or final_rect.height < 5:
                continue

            # 渲染截圖
            pix = page.get_pixmap(clip=final_rect, matrix=fitz.Matrix(2, 2), alpha=False)
            
            image_filename = os.path.join(output_dir, f"p{page_num+1}_i{img_index+1}.png")
            pix.save(image_filename)
            paths.append(image_filename)
            
        if paths:
            img_map[page_num + 1] = paths
    return img_map

# --- exam.py ---
# --- exam.py 終極修正版 ---

def extract_exam_data(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    page_offsets = [] 
    for page_num in range(len(doc)):
        page_text = doc[page_num].get_text()
        page_offsets.append((len(full_text), page_num + 1))
        full_text += page_text + "\n"

    # --- 標題抓取邏輯 (跨行並精簡) ---
    header_text = doc[0].get_text()
    title_match = re.search(r'(\d+年(?:第[一二三四五]次)?)', header_text)
    year_prefix = title_match.group(1) if title_match else ""
    subject_match = re.search(r'科目名稱[:：]\s*(.*?)(?=\s*(?:考試時間|題\s*數|$))', header_text, re.DOTALL)
    
    if subject_match:
        raw_subject = subject_match.group(1).replace('\n', '').strip()
        subject_name = re.sub(r'[（\(](?![一二三四五六七八九十][\)）]).*?[）\)]', '', raw_subject).strip()
    else:
        subject_name = os.path.basename(pdf_path)
    
    metadata = {"deck_name": f"{year_prefix} {subject_name}".strip()}

    # --- 題目抓取 (使用 Dictionary 徹底防止重複題號) ---
    questions_dict = {}
    matches = list(re.finditer(r'(?:^|\n)(\d{1,3})\.\s*(.*?)(?=\n\d{1,3}\.|$)', full_text, re.DOTALL))
    
    for m in matches:
        # 強制將題號轉為整數再轉回字串 (例如 "01" 變 "1")，防止重複
        q_id = str(int(m.group(1)))
        if int(q_id) > 125: continue 
        
        block = m.group(2)
        # 檢查是否包含選項 A.，若無則可能是行政代碼，跳過
        if not re.search(r'[A-D]\.', block):
            continue

        start_pos = m.start()
        q_page = 1
        for offset, p_num in page_offsets:
            if start_pos >= offset: q_page = p_num
            else: break
        
        content_parts = re.split(r'\n([A-D])\.', block)
        content = content_parts[0].strip()
        opts_dict = {}
        for i in range(1, len(content_parts), 2):
            label = content_parts[i]
            val = content_parts[i+1].split('\n')[0].strip()
            opts_dict[label] = val
            
        # 相同的 q_id 會直接覆蓋，保證 Q1 只有一個
        questions_dict[q_id] = {
            "id": q_id,
            "text": re.sub(r'\s+', ' ', content).strip(),
            "options": opts_dict,
            "page": q_page
        }
        
    return sorted(questions_dict.values(), key=lambda x: int(x['id'])), metadata

def parse_answer_pdf(ans_pdf_path):
    try:
        doc = fitz.open(ans_pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        
        # 1. 統一轉換全形並排除干擾字串
        full_text = full_text.translate(str.maketrans('ＡＢＣＤ＃', 'ABCD#'))
        
        # 【關鍵修正】：直接將說明文字中可能包含 # 的句子刪除
        # 防止「答案標註#者」這句話裡面的 # 變成第一題的答案
        full_text = full_text.replace("答案標註#者", "REPLACED_TEXT")
        
        # 2. 定位表格起點
        table_start = re.search(r'題\s*[號序]', full_text)
        search_text = full_text[table_start.start():] if table_start else full_text
        
        ans_list = []
        # 3. 抓取答案區塊
        blocks = re.findall(r'答\s*案\s*(.*?)(?=題\s*[號序]|備\s*註|$)', search_text, re.DOTALL)
        for b in blocks:
            # 牙醫解答常見的連續字母 (如 "BA") 也能正確拆解
            found = re.findall(r'[A-D#]', b)
            ans_list.extend(found)
        
        # 4. 抓取備註
        remarks_map = {}
        if "備註" in full_text:
            remarks_text = full_text.split("備註")[-1]
            matches = re.findall(r'第\s*(\d+)\s*題\s*[:：]?(.*?)(?=第\s*\d+\s*題|備\s*註|$)', remarks_text, re.DOTALL)
            for q_num, content in matches:
                remarks_map[str(int(q_num))] = content.strip().strip('，, 。')

        print(f"🎯 成功抓取解答，共 {len(ans_list)} 題，備註更正 {len(remarks_map)} 題")
        return ans_list, remarks_map
    except Exception as e:
        print(f"❌ 抓取解答失敗: {e}")
        return [], {}

def find_all_pairs(file_paths):
    q_files = []
    ans_files = {}
    mod_files = {}

    for p in file_paths:
        name = os.path.basename(p).upper()
        # 【核心修正】：先移除關鍵字，再提取所有數字作為「辨識基因」
        # 這樣 109100_11 與 109100_ANS11 都會變成 "10910011"，達成完美配對
        clean_name = name.replace("ANS", "").replace("MOD", "")
        identifier = "".join(re.findall(r'\d+', clean_name))

        if "MOD" in name:
            mod_files[identifier] = p
        elif "ANS" in name:
            ans_files[identifier] = p
        else:
            # 既無 MOD 也無 ANS，視為題目檔
            q_files.append((identifier, p))

    pairs = []
    for q_id, q_path in q_files:
        # 優先順序：MOD > ANS > None
        if q_id in mod_files:
            pairs.append((q_path, mod_files[q_id]))
        elif q_id in ans_files:
            pairs.append((q_path, ans_files[q_id]))
        else:
            pairs.append((q_path, None))
            
    return pairs

# --- exam.py 修正處：精準字母抓取 ---



def normalize_name(name):
    return re.sub(r'[\W_]+', '', name).lower()


def strip_ans_mod(name):
    return re.sub(r'(?i)(ans|mod)', '', name)


def is_answer_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return bool(re.search(r'(?i)(ans|mod)', base))


def find_answer_match(question_path, candidates):
    q_base = normalize_name(os.path.splitext(os.path.basename(question_path))[0])
    for candidate in candidates:
        if candidate == question_path:
            continue
        c_base = normalize_name(strip_ans_mod(os.path.splitext(os.path.basename(candidate))[0]))
        if q_base == c_base:
            return candidate
    return None


def find_matching_files(paths):
    paths = [os.path.abspath(p) for p in paths]
    if len(paths) == 1:
        question_path = paths[0]
        if is_answer_filename(question_path):
            answer_path = None
            q_base = normalize_name(strip_ans_mod(os.path.splitext(os.path.basename(question_path))[0]))
            folder = os.path.dirname(question_path)
            for fname in os.listdir(folder):
                if fname.lower().endswith('.pdf'):
                    candidate = os.path.join(folder, fname)
                    if normalize_name(os.path.splitext(os.path.basename(candidate))[0]) == q_base and not is_answer_filename(candidate):
                        return candidate, question_path
            return None, question_path
        else:
            folder = os.path.dirname(question_path)
            q_base = normalize_name(os.path.splitext(os.path.basename(question_path))[0])
            for fname in os.listdir(folder):
                if fname.lower().endswith('.pdf'):
                    candidate = os.path.join(folder, fname)
                    if candidate == question_path:
                        continue
                    if normalize_name(strip_ans_mod(os.path.splitext(os.path.basename(candidate))[0])) == q_base and is_answer_filename(candidate):
                        return question_path, candidate
            return question_path, None

    question_candidates = [p for p in paths if not is_answer_filename(p)]
    answer_candidates = [p for p in paths if is_answer_filename(p)]

    if len(question_candidates) == 1 and answer_candidates:
        answer = find_answer_match(question_candidates[0], answer_candidates) or answer_candidates[0]
        return question_candidates[0], answer

    if question_candidates:
        question = question_candidates[0]
        answer = find_answer_match(question, answer_candidates) if answer_candidates else None
        return question, answer

    return paths[0], answer_candidates[0] if answer_candidates else None

# --- 4. 執行邏輯配對 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="將國考 PDF 轉成題庫字卡 JSON。")
    parser.add_argument('pdfs', nargs='+', help='一或多個 PDF 檔案路徑，支援題目與答案一起丟進來。')
    parser.add_argument('--output-dir', default='images', help='圖片輸出資料夾，預設 images')
    parser.add_argument('--json', default='questions.json', help='輸出 JSON 檔名，預設 questions.json')
    args = parser.parse_args()

    Q_PDF, A_PDF = find_matching_files(args.pdfs)
    output_dir = args.output_dir
    json_path = args.json

    if not Q_PDF or not os.path.exists(Q_PDF):
        raise FileNotFoundError(f'找不到題目 PDF：{Q_PDF}')

    if A_PDF and not os.path.exists(A_PDF):
        print(f'⚠️ 找不到答案 PDF：{A_PDF}，將只輸出題目字卡。')
        A_PDF = None

    print('🔍 正在讀取 PDF 資料...')
    img_map = get_pdf_images(Q_PDF, output_dir=output_dir)
    raw_qs, metadata = extract_exam_data(Q_PDF)
    if A_PDF:
        ans_list, remarks_map = parse_answer_pdf(A_PDF)
    else:
        ans_list, remarks_map = [], {}

    print("🧠 正在執行條件配對邏輯...")
    for q in raw_qs:
        # 1. 取得基本答案索引
        idx = int(q["id"]) - 1
        
        # 2. 檢查索引是否超出答案清單範圍 (解決 100 題導致 N/A 的問題)
        if idx < len(ans_list):
            raw_ans = ans_list[idx]
            
            # 3. 處理 # 號更正邏輯
            if raw_ans == "#" and q["id"] in remarks_map:
                # 根據你的需求，將 # 替換為備註中的句子
                q["answer"] = f"{remarks_map[q['id']]}"
            else:
                q["answer"] = raw_ans
        else:
            q["answer"] = "N/A"
        
        # ... (後續的補圖邏輯保持不變)
        
        # 2. 強大補圖邏輯
        needs_image = False
        
        # 條件 A：題目文字中包含關鍵字
        if any(k in q["text"] for k in ["圖", "下圖", "附圖"]):
            needs_image = True
            
        # 條件 B：選項是空的 (例如：選項全是化學式或數學圖片)
        # 判斷 options 字典是否為空，或雖然有 A 但內容是空的
        if not q["options"] or all(val == "" for val in q["options"].values()):
            needs_image = True
            
        # 執行補圖
        if needs_image and q["page"] in img_map and img_map[q["page"]]:
            q["image"] = img_map[q["page"]][0]
                    
            # 【進階建議】如果一頁有兩題都要圖，可以考慮用 pop(0) 
            # 但通常國考一頁圖對應一題，這行能解決 90% 的情況

    # 儲存 JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"metadata": metadata, "questions": raw_qs}, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 大功告成！已產生 {len(raw_qs)} 題字卡，並依據邏輯自動補完圖片。輸出：{json_path}")