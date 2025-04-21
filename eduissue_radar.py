
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

def parse_kakao_text(file):
    text = file.read().decode('utf-8')
    lines = text.splitlines()
    parsed = []
    current_date = None
    date_pattern = r'-{10,}\s*(\d{4}년 \d{1,2}월 \d{1,2}일.*?)\s*-{10,}'
    msg_pattern = r'\[(.*?)\] \[(오전|오후) (\d{1,2}:\d{2})\] (.+)'
    for line in lines:
        date_match = re.match(date_pattern, line)
        if date_match:
            current_date = date_match.group(1)
            continue
        msg_match = re.match(msg_pattern, line)
        if msg_match and current_date:
            user, ampm, time, msg = msg_match.groups()
            hour, minute = map(int, time.split(':'))
            if ampm == '오후' and hour != 12:
                hour += 12
            timestamp = f"{hour:02}:{minute:02}"
            parsed.append({"날짜": current_date, "사용자": user, "시간": timestamp, "메시지": msg})
    return pd.DataFrame(parsed)

issue_keywords = ["배송", "지연", "누락", "불량", "부족", "정산", "반품", "추가", "오류"]
def extract_issues(df):
    msgs = df[df['메시지'].str.contains('|'.join(issue_keywords))]
    all_words = ' '.join(msgs['메시지'].tolist())
    nouns = re.findall(r'[\uAC00-\uD7A3]+', all_words)
    count = Counter(nouns)
    return msgs, count.most_common(10)

def crawl_naver_news(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://search.naver.com/search.naver?where=news&query={query}"
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return []
    soup = BeautifulSoup(res.text, 'html.parser')
    items = soup.select('.list_news .news_area')
    results = []
    seen = set()
    for item in items:
        title_tag = item.select_one('.news_tit')
        if not title_tag:
            continue
        title = title_tag.text.strip()
        if title in seen:
            continue
        seen.add(title)
        link = title_tag['href']
        press = item.select_one('.info_group span.press').text if item.select_one('.info_group span.press') else ''
        date_text = item.select_one('.info_group .date').text if item.select_one('.info_group .date') else ''
        try:
            pub_date = datetime.strptime(date_text, "%Y.%m.%d. %H:%M")
            display_date = pub_date.strftime('%Y-%m-%d')
        except:
            pub_date = datetime.now()
            display_date = date_text or '날짜 정보 없음'
        results.append({"제목": title, "링크": link, "언론사": press, "날짜": pub_date, "표시날짜": display_date})
    results.sort(key=lambda x: x['날짜'], reverse=True)
    return results

def render_articles(articles):
    if not articles:
        st.markdown("뉴스가 없습니다.")
    else:
        for article in articles[:5]:
            with st.container():
                st.markdown(f"**{article['제목']}** <{article['언론사']}> ({article['표시날짜']})")
                st.link_button("🔗 뉴스 보러가기", url=article["링크"])

st.title("📚 EduIssue Radar")
st.markdown("교과서 민원 메시지 + 최신 네이버 뉴스 (최근 7일) 분석기")

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
    start_d, end_d = st.date_input("분석 기간 선택", [min_d, max_d])
    df_sel = df[(df['날짜'] >= pd.to_datetime(start_d)) & (df['날짜'] <= pd.to_datetime(end_d))]

    tab1, tab2 = st.tabs(["📊 민원 분석", "📰 최신 네이버 뉴스"])

    with tab1:
        st.success(f"{start_d} ~ {end_d} 메시지 {len(df_sel)}건 분석")
        issue_df, top_issues = extract_issues(df_sel)
        st.subheader("🚨 민원 메시지")
        st.write(issue_df[['날짜', '시간', '사용자', '메시지']])
        st.markdown("**민원 키워드 TOP10**")
        for i in range(0, len(top_issues), 3):
            cols = st.columns(3)
            for j, (kw, cnt) in enumerate(top_issues[i:i+3]):
                cols[j].markdown(f"- **{kw}** ({cnt}회)")

    with tab2:
        st.subheader("📰 연관 뉴스 (최근 7일)")
        threshold = datetime.now() - timedelta(days=7)
        _, top_issues = extract_issues(df_sel)
        extra_topics = [kw for kw, _ in top_issues[:3]]
        for word in extra_topics:
            with st.expander(f"🔎 {word} 관련 뉴스"):
                arts = [a for a in crawl_naver_news(word) if a['날짜'] >= threshold]
                render_articles(arts)

        st.subheader("📚 주제별 최신 뉴스 (최근 7일)")
        topics = ["교과서", "AI 디지털교과서", "비상교육", "천재교육", "천재교과서", "미래엔", "아이스크림미디어", "동아출판", "지학사"]
        for topic in topics:
            with st.expander(f"📘 {topic} 관련 뉴스"):
                arts = [a for a in crawl_naver_news(topic) if a['날짜'] >= threshold]
                render_articles(arts)
