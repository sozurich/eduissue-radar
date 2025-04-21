
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
import requests

def parse_kakao_text(file):
    text = file.read().decode('utf-8')
    lines = text.splitlines()
    parsed = []
    current_date = None
    date_pattern = r'-{10,}\s*(\d{4}년 \d{1,2}월 \d{1,2}일.*?)\s*-{10,}'
    msg_pattern = r'\[(.*?)\] \[(오전|오후) (\d{1,2}:\d{2})\] (.+)'
    for line in lines:
        dm = re.match(date_pattern, line)
        if dm:
            current_date = dm.group(1)
            continue
        mm = re.match(msg_pattern, line)
        if mm and current_date:
            user, ampm, time_str, msg = mm.groups()
            hour, minute = map(int, time_str.split(':'))
            if ampm == '오후' and hour != 12:
                hour += 12
            timestamp = f"{hour:02}:{minute:02}"
            parsed.append({"날짜": current_date, "사용자": user, "시간": timestamp, "메시지": msg})
    return pd.DataFrame(parsed)

issue_keywords = ["배송","지연","누락","불량","부족","정산","반품","추가","오류"]
def extract_issues(df):
    msgs = df[df['메시지'].str.contains('|'.join(issue_keywords))]
    words = ' '.join(msgs['메시지'].tolist())
    nouns = re.findall(r'[\uAC00-\uD7A3]+', words)
    cnt = Counter(nouns)
    return msgs, cnt.most_common(10)

def crawl_naver_openapi(query):
    client_id = st.secrets.get("NAVER_CLIENT_ID", None)
    client_secret = st.secrets.get("NAVER_CLIENT_SECRET", None)
    if not client_id or not client_secret:
        st.error("NAVER_CLIENT_ID 및 NAVER_CLIENT_SECRET을 Secrets에 설정해주세요.")
        return []
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query + " 교과서",
        "display": 5,
        "sort": "date"
    }
    res = requests.get("https://openapi.naver.com/v1/search/news.json", headers=headers, params=params)
    if res.status_code != 200:
        st.error(f"네이버 API 호출 오류: {res.status_code}")
        return []
    data = res.json().get("items", [])
    results = []
    for it in data:
        title = it.get("title", "").replace("<b>", "").replace("</b>", "")
        link = it.get("originallink") or it.get("link")
        date_str = it.get("pubDate", "")
        try:
            pub = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
        except:
            pub = datetime.now()
        results.append({"제목": title, "링크": link, "날짜": pub, "표시날짜": pub.strftime('%Y-%m-%d')})
    return results

def render_articles(articles):
    if not articles:
        st.markdown("뉴스가 없습니다.")
    else:
        for art in articles:
            with st.container():
                st.markdown(f"**{art['제목']}** ({art['표시날짜']})")
                st.link_button("🔗 뉴스 보러가기", url=art["링크"])

st.title("📚 EduIssue Radar")
st.markdown("교과서 민원 메시지 + 네이버 OpenAPI 뉴스 요약")

uploaded = st.file_uploader("카카오톡 채팅 .txt 파일 업로드", type="txt")
if uploaded:
    df = parse_kakao_text(uploaded)
    df['날짜'] = pd.to_datetime(
        df['날짜'].str.extract(r'(\d{4}년 \d{1,2}월 \d{1,2}일)')[0],
        format='%Y년 %m월 %d일',
        errors='coerce'
    ).fillna(pd.Timestamp.today())
    min_d, max_d = df['날짜'].min().date(), df['날짜'].max().date()
    st.markdown(f"**분석 가능한 날짜:** {min_d} ~ {max_d}")
    sd, ed = st.date_input("분석 기간 선택", [min_d, max_d])
    df_sel = df[(df['날짜'] >= pd.to_datetime(sd)) & (df['날짜'] <= pd.to_datetime(ed))]

    tab1, tab2 = st.tabs(["📊 민원 분석", "📰 뉴스 요약"])
    with tab1:
        st.success(f"{sd} ~ {ed} 메시지 {len(df_sel)}건 분석")
        iss_df, top = extract_issues(df_sel)
        st.subheader("🚨 민원 메시지")
        st.write(iss_df[['날짜','시간','사용자','메시지']])
        st.markdown("**민원 키워드 TOP10**")
        for i in range(0, len(top), 3):
            cols = st.columns(3)
            for j,(kw,cnt) in enumerate(top[i:i+3]):
                cols[j].markdown(f"- **{kw}** ({cnt}회)")
    with tab2:
        st.subheader("📰 연관 뉴스")
        _, top_issues = extract_issues(df_sel)
        topics = [kw for kw,_ in top_issues[:3]]
        for t in topics:
            arts = crawl_naver_openapi(t)
            with st.expander(f"🔎 {t} 관련 뉴스"):
                render_articles(arts)
