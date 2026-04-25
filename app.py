import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import datetime


import sqlite3
from datetime import datetime, date
def get_notification_count(conn):
    # 「2日前」の日付を取得
    two_days_ago = (datetime.date.today() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    c = conn.cursor()
    
    # 2日前に解いて、かつ結果が「○」ではない問題をカウント
    # (同じ日に複数回解いている可能性も考慮して、その日の最新の結果を見ます)
    query = """
        SELECT COUNT(DISTINCT problem_id) 
        FROM results 
        WHERE date = ? AND result IN ('×', '△', '不明')
    """
    c.execute(query, (two_days_ago,))
    return c.fetchone()[0]
import google.generativeai as genai
from PIL import Image
import io

# --- 設定と初期化 ---
st.set_page_config(page_title="MathLog - 数学問題管理", layout="wide")
# --- ここから追加：Twitter風モダンUIカスタムCSS ---
st.markdown("""
    <style>
    /* ========================================= */
    /* 【☀️ ライトモード（標準）のデザイン】 */
    /* ========================================= */
    .stApp { background-color: #F5F8FA; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    [data-testid="stExpander"] {
        background-color: white !important;
        border-radius: 16px !important;
        border: 1px solid #E1E8ED !important;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.03) !important;
        margin-bottom: 15px;
    }
    
    [data-testid="stExpander"] summary {
        font-weight: 600; padding: 10px; color: #14171A !important;
    }

    .stButton > button {
        border-radius: 9999px !important; background-color: #1DA1F2 !important;
        color: white !important; border: none !important; font-weight: bold !important;
        padding: 10px 24px !important; box-shadow: 0px 4px 6px rgba(29, 161, 242, 0.2);
    }

    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div {
        border-radius: 12px !important; border: 1px solid #E1E8ED !important; background-color: white !important;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}

    /* ========================================= */
    /* 【🌙 ダークモード時のデザイン（スマホ設定連動）】 */
    /* ========================================= */
    @media (prefers-color-scheme: dark) {
        .stApp { background-color: #15202B !important; }
        
        [data-testid="stExpander"] {
            background-color: #192734 !important; border: 1px solid #38444D !important;
        }
        
        /* ⚠️ここが重要：あらゆるテキストを白系に変更して見やすくする */
        [data-testid="stExpander"] summary,
        p, h1, h2, h3, h4, h5, h6, label, span, div, .stMarkdown { 
            color: #E1E8ED !important; 
        }

        .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div {
            background-color: #22303C !important; border: 1px solid #38444D !important; color: #FFFFFF !important;
        }

        [data-testid="stSidebar"] section { background-color: #15202B !important; }
    }
    </style>
""", unsafe_allow_html=True)
# --- 追加ここまで ---

# Gemini APIの設定（サイドバーで入力を促す）
st.sidebar.title("⚙️ 設定")
api_key = st.sidebar.text_input("Gemini API Key", type="password")
if api_key:
    genai.configure(api_key=api_key)

# データベースの初期化
def init_db():
    conn = sqlite3.connect('math_study.db')
    c = conn.cursor()
    # 問題テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS problems
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  university TEXT, year TEXT, unit TEXT, 
                  difficulty TEXT, est_time INTEGER, 
                  summary TEXT, problem_img BLOB)''')
    # 学習記録テーブル
    c.execute('''CREATE TABLE IF NOT EXISTS records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  problem_id INTEGER, solve_date TEXT, 
                  time_taken INTEGER, understanding TEXT, 
                  answer_img BLOB)''')
    conn.commit()
    conn.close()

init_db()

# --- ヘルパー関数 ---
def parse_time_logic(s):
    """C＊＊。 のような形式を解析して(難易度, 分)を返す"""
    if not s: return "A", 0
    diff = s[0].upper()
    symbols = s[1:]
    minutes = (symbols.count("＊") + symbols.count("*")) * 10
    minutes += (symbols.count("。") + symbols.count(".")) * 5
    return diff, minutes

def analyze_with_gemini(image_bytes, prompt_type):
    """Geminiを使って画像を解析"""
    if not api_key:
        return "APIキーを設定してください"
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    img = Image.open(io.BytesIO(image_bytes))
    
    prompts = {
        "info": "この数学の問題画像から、出題された「大学名」と「年度」を特定してください。返答は '〇〇大学, 20XX年' という形式だけにしてください。不明な場合は '不明, 不明' としてください。",
        "summary": "この数学の問題の解答のポイントや必要な公式、考え方の流れを「解答要素のまとめ」として簡潔な箇条書きで作成してください。"
    }
    
    response = model.generate_content([prompts[prompt_type], img])
    return response.text

# --- UIコンポーネント ---
st.title("📚 MathLog マスター")

# 👇ここから差し替え👇
with st.sidebar:
    st.markdown("<h2 style='text-align: center; color: #1DA1F2;'>📚 MathLog</h2>", unsafe_allow_html=True)
    st.write("") # 少し隙間を空ける
    
    menu = option_menu(
        menu_title=None,  
        options=["ホーム", "新規問題登録", "問題一覧・復習", "分析ダッシュボード"],
        icons=["house", "pencil-square", "journal-bookmark", "bar-chart-line"], 
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#8899A6", "font-size": "18px"}, 
            "nav-link": {
                "font-size": "15px", 
                "text-align": "left", 
                "margin":"5px", 
                "border-radius": "12px"
            },
            "nav-link-selected": {
                "background-color": "#1DA1F2", 
                "color": "white", 
                "font-weight": "bold"
            },
        }
    )

# 1. ホーム（統計表示）
if menu == "ホーム":
    conn = sqlite3.connect('math_study.db')
    df_records = pd.read_sql_query("SELECT * FROM records", conn)
    conn.close()
    
    st.header("📊 本日の学習状況")
    today_str = date.today().strftime("%Y-%m-%d")
    today_data = df_records[df_records['solve_date'] == today_str]
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("今日の勉強時間", f"{today_data['time_taken'].sum()} 分")
    with col2:
        st.metric("累計勉強時間", f"{df_records['time_taken'].sum()} 分")

# 2. 新規問題登録
elif menu == "新規問題登録":
    st.header("📝 新規問題の登録")
    
    uploaded_file = st.file_uploader("問題の画像をアップロード", type=['png', 'jpg', 'jpeg'])
    
    if uploaded_file:
        img_bytes = uploaded_file.read()
        st.image(img_bytes, caption="アップロード画像", width=400)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 Geminiで大学・年度を判定"):
                res = analyze_with_gemini(img_bytes, "info")
                st.session_state['auto_info'] = res
            
            info = st.session_state.get('auto_info', "大学名, 年度").split(",")
            univ = st.text_input("大学名", value=info[0].strip())
            year = st.text_input("年度", value=info[1].strip() if len(info)>1 else "")
            unit = st.selectbox("単元", ["数I・A", "数II・B", "数III・C", "微分積分", "ベクトル", "数列", "確率", "その他"])

        with col2:
            diff_raw = st.text_input("難易度・目安時間 (例: C＊＊。)", help="A-D + ＊(10分)/。(5分)")
            difficulty, est_time = parse_time_logic(diff_raw)
            if diff_raw:
                st.caption(f"解析結果: 難易度{difficulty} / 目安時間 {est_time}分")

        if st.button("🤖 Geminiで解答要素をまとめる"):
            st.session_state['auto_summary'] = analyze_with_gemini(img_bytes, "summary")
        
        summary = st.text_area("解答要素のまとめ", value=st.session_state.get('auto_summary', ""), height=200)
        
        if st.button("💾 データベースに保存"):
            conn = sqlite3.connect('math_study.db')
            c = conn.cursor()
            c.execute("INSERT INTO problems (university, year, unit, difficulty, est_time, summary, problem_img) VALUES (?,?,?,?,?,?,?)",
                      (univ, year, unit, difficulty, est_time, summary, img_bytes))
            conn.commit()
            conn.close()
            st.success("問題を登録しました！")

# 3. 問題一覧・復習
elif menu == "問題一覧・復習":
    st.header("🔍 問題一覧と復習記録")


    
    conn = sqlite3.connect('math_study.db')
    df_p = pd.read_sql_query("SELECT id, university, year, unit, difficulty, est_time FROM problems", conn)
    
    # フィルタ
    col_f1, col_f2 = st.columns(2)
    f_univ = col_f1.multiselect("大学で絞り込み", df_p['university'].unique())
    f_unit = col_f2.multiselect("単元で絞り込み", df_p['unit'].unique())
    
    filtered_df = df_p
    if f_univ: filtered_df = filtered_df[filtered_df['university'].isin(f_univ)]
    if f_unit: filtered_df = filtered_df[filtered_df['unit'].isin(f_unit)]
    
    for _, row in filtered_df.iterrows():
        with st.expander(f"{row['university']} ({row['year']}) - {row['unit']} [難易度:{row['difficulty']}]"):
            # 問題情報の表示
            c = conn.cursor()
            c.execute("SELECT problem_img, summary FROM problems WHERE id=?", (row['id'],))
            p_data = c.fetchone()
            st.image(p_data[0], width=500)
            with st.expander("🔍 解答要素のまとめを表示（ネタバレ注意）"):
                st.info(p_data[1])
            
            st.divider()
            with st.expander("✏️ 問題の情報を編集する"):
                with st.form(f"edit_form_{row['id']}"):
                    st.write("変更したい箇所を書き換えて「更新」を押してください")
                    
                    # 今のデータを初期値として入れておく
                    edit_unit = st.text_input("単元", value=row['unit'])
                    edit_diff = st.text_input("難易度", value=row['difficulty'])
                    edit_summary = st.text_area("解答要素のまとめ", value=p_data[1], height=150)
                    
                    if st.form_submit_button("🔄 情報を更新する"):
                        # データベースを上書きするSQLコマンド
                        c.execute("UPDATE problems SET unit=?, difficulty=?, summary=? WHERE id=?", 
                                  (edit_unit, edit_diff, edit_summary, row['id']))
                        conn.commit()
                        st.success("更新しました！")
                        st.rerun() # 画面をリロードして即座に反映
            # 過去の記録
            st.subheader("解いた記録")
            df_r = pd.read_sql_query(f"SELECT solve_date, time_taken, understanding FROM records WHERE problem_id={row['id']}", conn)
            st.table(df_r)
            
            # 新規記録
            st.subheader("新規記録を追加")
            c1, c2, c3 = st.columns(3)
            with c1:
                u_date = st.date_input("解いた日", key=f"date_{row['id']}")
            with c2:
                u_time = st.number_input("かかった時間(分)", min_value=0, key=f"time_{row['id']}")
            with c3:
                u_und = st.select_slider("理解度", options=["×", "△", "○"], key=f"und_{row['id']}")
            
            ans_file = st.file_uploader("自分の解答画像をアップロード", type=['png', 'jpg', 'jpeg'], key=f"ans_{row['id']}")
            
            if st.button("記録を保存", key=f"btn_{row['id']}"):
                ans_bytes = ans_file.read() if ans_file else None
                c.execute("INSERT INTO records (problem_id, solve_date, time_taken, understanding, answer_img) VALUES (?,?,?,?,?)",
                          (row['id'], u_date.strftime("%Y-%m-%d"), u_time, u_und, ans_bytes))
                conn.commit()
                st.rerun()
    conn.close()