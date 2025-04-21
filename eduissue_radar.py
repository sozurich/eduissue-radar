
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
import requests
from bs4 import BeautifulSoup

# 1. 파싱 함수
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

# 2. 민원 메시지 필터링
issue_keywords = ["배송", "지연", "누락", "불량", "부족", "정산", "반품", "추가", "오류"]

def extract_issues(df):
    msgs = df[df['메시지'].str.contains('|'.join(issue_keywords))]
    all_words = ' '.join(msgs['메시지'].tolist())
    nouns = re.findall(r'[\uAC00-\uD7A3]+', all_words)
    count = Counter(nouns)
    return msgs, count.most_common(10)

# 3. 뉴스 크롤링
def crawl_google_news(query):
    url = f"https://news.google.com/rss/search?q={query}+교과서&hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, 'html.parser')
    items = soup.find_all('item')
    results = []
    seen = set()
    for item in items:
        title = item.title.text
        if title in seen:
            continue
        seen.add(title)
        desc_html = item.description.text
        soup_desc = BeautifulSoup(desc_html, 'html.parser')
        link_tag = soup_desc.find('a')
        link = link_tag['href'] if link_tag else item.link.text
        if item.pubDate:
            pub_date = parsedate_to_datetime(item.pubDate.text)
            display_date = pub_date.strftime('%Y-%m-%d')
        else:
            pub_date = datetime.now()
            display_date = "날짜 정보 없음"
        results.append({"제목": title, "링크": link, "날짜": pub_date, "표시날짜": display_date})
    results.sort(key=lambda x: x['날짜'], reverse=True)
    return results

# 4. 기사 렌더링 함수
def render_articles(articles):
    if not articles:
        st.markdown("뉴스가 없습니다.")
    else:
        for article in articles[:5]:
            with st.container():
                st.markdown(f"**{article['제목']}** ({article['표시날짜']})")
                st.link_button("🔗 뉴스 보러가기", url=article["링크"])

# 5. Streamlit UI
st.title("📚 EduIssue Radar")
st.markdown("교과서 민원 메시지 + 뉴스 요약 분석기")

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

    tab1, tab2 = st.tabs(["📊 민원 분석", "📰 뉴스 요약"])

    with tab1:
        st.success(f"{start_d} ~ {end_d} 메시지 {len(df_sel)}건 분석")
        issue_df, top_issues = extract_issues(df_sel)
        st.subheader("🚨 민원 메시지")
        st.write(issue_df[['날짜', '시간', '사용자', '메시지']])
        st.markdown("**민원 키워드 TOP10**")
        # 키워드 3열 레이아웃
        for i in range(0, len(top_issues), 3):
            cols = st.columns(3)
            for j, (kw, cnt) in enumerate(top_issues[i:i+3]):
                cols[j].markdown(f"- **{kw}** ({cnt}회)")

    with tab2:
        st.subheader("📰 연관 뉴스 기사")
        extra_topics = [kw for kw, _ in top_issues[:3]]
        for word in extra_topics:
            with st.expander(f"🔎 {word} 관련 뉴스"):
                arts = crawl_google_news(word)
                render_articles(arts)
        st.markdown("### 📚 주제별 추천 뉴스")
        topics = ["교과서", "AI 디지털교과서", "비상교육", "천재교육", "천재교과서", "미래엔", "아이스크림미디어", "동아출판", "지학사"]
        for topic in topics:
            with st.expander(f"📘 {topic} 관련 뉴스"):
                arts = crawl_google_news(topic)
                render_articles(arts)
