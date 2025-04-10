# EduIssue Radar - Streamlit 앱 (기간 분석 기능 포함)

import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# 1. 텍스트 파일 파싱 함수 (줄 단위 날짜 매핑)
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

# 2. 키워드 기반 민원 메시지 필터링
issue_keywords = ["배송", "지연", "누락", "불량", "부족", "정산", "반품", "추가", "오류"]

def extract_issues(df):
    issue_msgs = df[df['메시지'].str.contains('|'.join(issue_keywords))]
    all_words = ' '.join(issue_msgs['메시지'].tolist())
    nouns = re.findall(r'[가-힣]+', all_words)
    count = Counter(nouns)
    return issue_msgs, count.most_common(10)

# 3. 뉴스 크롤러 함수 (네이버 뉴스 검색)
def crawl_news(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://search.naver.com/search.naver?where=news&query={query}"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    news_items = soup.select(".list_news .news_area")
    seen_titles = set()
    results = []
    for item in news_items:
        title_tag = item.select_one(".news_tit")
        if title_tag:
            title = title_tag.text.strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)
            link = title_tag['href']
            press = item.select_one(".info_group span").text if item.select_one(".info_group span") else "언론사 미확인"
            date_tag = item.select_one(".info_group span:nth-of-type(2)")
            pub_date = date_tag.text if date_tag else "날짜 미확인"
            results.append({"제목": title, "링크": link, "언론사": press, "날짜": pub_date})
        if len(results) >= 5:
            break
    return results

# 4. Streamlit 인터페이스
st.title("📚 EduIssue Radar")
st.markdown("교과서 민원 메시지 + 뉴스 키워드 통합 분석기")

uploaded_file = st.file_uploader("카카오톡 채팅 .txt 파일을 업로드하세요", type="txt")

if uploaded_file:
    df = parse_kakao_text(uploaded_file)
    df['날짜'] = df['날짜'].fillna(method='ffill')
    df['날짜'] = pd.to_datetime(df['날짜'].str.extract(r'(\d{4}년 \d{1,2}월 \d{1,2}일)')[0], format="%Y년 %m월 %d일")

    min_date = df['날짜'].min()
    max_date = df['날짜'].max()

    st.markdown(f"**분석 가능한 날짜 범위:** {min_date.date()} ~ {max_date.date()}")
    start_date, end_date = st.date_input("분석할 기간을 선택하세요", [min_date, max_date])

    df_selected = df[(df['날짜'] >= pd.to_datetime(start_date)) & (df['날짜'] <= pd.to_datetime(end_date))]

    st.success(f"{start_date} ~ {end_date} 기간의 메시지 {len(df_selected)}건 분석 중...")

    issue_df, top_keywords = extract_issues(df_selected)
    st.subheader("🔍 민원 메시지 요약")
    st.write(issue_df[['날짜', '시간', '사용자', '메시지']])

    st.subheader("🔥 자주 언급된 키워드")
    for word, freq in top_keywords:
        st.write(f"- {word} ({freq}회)")

    # 🎯 연관 뉴스 기사 + 주제별 뉴스 2단 컬럼 분할 + 접이식 구성
    st.subheader("📰 뉴스 요약")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📌 연관 뉴스 기사")
        for word, _ in top_keywords[:3]:
            with st.expander(f"🔎 {word} 관련 뉴스"):
                articles = crawl_news(word + " 교과서")
                for article in articles:
                    st.markdown(
                        f"- [{article['제목']}]({article['링크']})  \n"
                        f"  ⏱ {article['날짜']} | 📰 {article['언론사']}"
                    )

    with col2:
        st.markdown("### 📚 주제별 추천 뉴스")
        extra_topics = ["교과서", "AI 디지털교과서", "비상교육", "천재교육", "천재교과서", "미래엔", "아이스크림미디어", "동아출판", "지학사"]
        for topic in extra_topics:
            with st.expander(f"📘 {topic} 관련 뉴스"):
                articles = crawl_news(topic)
                for article in articles:
                    st.markdown(
                        f"- [{article['제목']}]({article['링크']})  \n"
                        f"  📰 {article['언론사']}"
                    )
