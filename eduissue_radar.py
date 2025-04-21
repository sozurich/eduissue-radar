
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
from email.utils import parsedate_to_datetime
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
emotion_keywords = ["멘붕", "모르겠", "어렵", "답답", "복잡", "미치겠", "휴직", "힘들", "스트레스", "엉망"]

def extract_issues(df):
    issue_msgs = df[df['메시지'].str.contains('|'.join(issue_keywords))]
    all_words = ' '.join(issue_msgs['메시지'].tolist())
    nouns = re.findall(r'[\uAC00-\uD7A3]+', all_words)
    count = Counter(nouns)
    return issue_msgs, count.most_common(10)

def extract_emotions(df):
    emotion_msgs = df[df['메시지'].str.contains('|'.join(emotion_keywords))]
    all_words = ' '.join(emotion_msgs['메시지'].tolist())
    nouns = re.findall(r'[\uAC00-\uD7A3]+', all_words)
    count = Counter(nouns)
    return emotion_msgs, count.most_common(10)

def crawl_google_news(query):
    url = f"https://news.google.com/rss/search?q={query}+교과서&hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(url)
    soup = BeautifulSoup(res.content, 'html.parser')
    items = soup.find_all('item')
    results = []
    seen_titles = set()
    for item in items:
        title = item.title.text
        if title in seen_titles:
            continue
        seen_titles.add(title)
        description_html = item.description.text
        soup_desc = BeautifulSoup(description_html, 'html.parser')
        link_tag = soup_desc.find('a')
        original_link = link_tag['href'] if link_tag else item.link.text
        if item.pubDate:
            pub_date = parsedate_to_datetime(item.pubDate.text)
            display_date = pub_date.strftime('%Y-%m-%d')
        else:
            pub_date = datetime.now()
            display_date = "날짜 정보 없음"
        results.append({
            "제목": title,
            "링크": original_link,
            "날짜": pub_date,
            "표시날짜": display_date
        })
    results.sort(key=lambda x: x['날짜'], reverse=True)
    return results

st.title("📚 EduIssue Radar")
st.markdown("교과서 민원 메시지 + 감정 감지 + 뉴스 요약 분석기")

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

    tab1, tab2 = st.tabs(["📊 민원 및 감정 분석", "📰 뉴스 요약"])

    with tab1:
        st.success(f"{start_date} ~ {end_date} 기간의 메시지 {len(df_selected)}건 분석 중...")

        issue_df, top_issue_keywords = extract_issues(df_selected)
        st.subheader("🚨 민원 메시지 감지")
        st.write(issue_df[['날짜', '시간', '사용자', '메시지']])
        st.markdown("**민원 키워드 TOP10**")
        
    for i in range(0, len(top_issue_keywords), 3):
        cols = st.columns(3)
        row_items = top_issue_keywords[i:i+3]
        for j in range(len(row_items)):
            word, freq = row_items[j]
            cols[j].markdown(f"- **{word}** ({freq}회)")
    
            st.write(f"- {word} ({freq}회)")

        emotion_df, top_emotion_keywords = extract_emotions(df_selected)
        st.subheader("😥 감정 표현 감지")
        st.write(emotion_df[['날짜', '시간', '사용자', '메시지']])
        st.markdown("**감정 키워드 TOP10**")
        
    positive_words = ["좋아요", "감사", "도움", "잘됐", "다행"]
    negative_words = ["멘붕", "어렵", "답답", "미치겠", "힘들"]

    col_pos, col_neg = st.columns(2)
    col_pos.markdown("**😊 긍정 표현 (예시)**")
    for word in positive_words:
        col_pos.write(f"- {word}")

    col_neg.markdown("**😥 부정 표현 (예시)**")
    for word in negative_words:
        col_neg.write(f"- {word}")

    st.markdown("**감정 키워드 TOP10**")
    for i in range(0, len(top_emotion_keywords), 3):
        cols = st.columns(3)
        for j, (word, freq) in enumerate(top_emotion_keywords[i:i+3]):
            if j < len(cols):
                cols[j].markdown(f"- **{word}** ({freq}회)")
    
            st.write(f"- {word} ({freq}회)")

    with tab2:
        st.subheader("📰 뉴스 요약")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 📌 연관 뉴스 기사")
            for word, _ in top_issue_keywords[:3]:
                with st.expander(f"🔎 {word} 관련 뉴스"):
                    articles = crawl_google_news(word)
                    for article in articles[:5]:
                        st.markdown(f"**{article['제목']}** ({article['표시날짜']})")
                        st.link_button("🔗 뉴스 보러가기", url=article["링크"])

        with col2:
            st.markdown("### 📚 주제별 추천 뉴스")
            extra_topics = ["교과서", "AI 디지털교과서", "비상교육", "천재교육", "천재교과서", "미래엔", "아이스크림미디어", "동아출판", "지학사"]
            for topic in extra_topics:
                with st.expander(f"📘 {topic} 관련 뉴스"):
                    articles = crawl_google_news(topic)
                    for article in articles[:5]:
                        st.markdown(f"**{article['제목']}** ({article['표시날짜']})")
                        st.link_button("🔗 뉴스 보러가기", url=article["링크"])
