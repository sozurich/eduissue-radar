# EduIssue Radar - Streamlit 앱 (기간 분석 기능 포함)

import streamlit as st
import pandas as pd
import re
from collections import Counter, defaultdict
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# ...중략 (기존 내용 포함)...

# 🔥 자주 언급된 키워드
groupings = {
    '배송 관련': ['배송', '도착', '배달', '택배'],
    '지연/누락': ['지연', '누락', '연기'],
    '불량/오류': ['불량', '오류', '고장'],
    '정산/반품': ['정산', '반품', '환불'],
    '기타': []
}

sentiment_dict = {
    '배송': '부정', '지연': '부정', '누락': '부정', '오류': '부정', '불량': '부정',
    '짜증': '부정', '불편': '부정', '늦음': '부정',
    '만족': '긍정', '빠름': '긍정', '좋아요': '긍정', '정확': '긍정', '감사': '긍정'
}

summary = defaultdict(list)

for word, freq in top_keywords:
    categorized = False
    for topic, keywords in groupings.items():
        if any(k in word for k in keywords):
            summary[topic].append((word, freq))
            categorized = True
            break
    if not categorized:
        summary['기타'].append((word, freq))

example_sentences = {
    '배송 관련': ["배송이 아직 도착하지 않았어요", "택배가 오지 않았습니다"],
    '지연/누락': ["교과서가 누락되었어요", "배송이 너무 지연돼요"],
    '불량/오류': ["인쇄 오류가 있어요", "불량 교과서가 왔어요"],
    '정산/반품': ["정산이 안 됐어요", "반품하고 싶은데 어떻게 하나요?"],
    '기타': ["기타 이슈가 있습니다"]
}

for topic, words in summary.items():
    st.markdown(f"**🗂 {topic}**")
    for word, freq in words:
        sentiment = sentiment_dict.get(word, '중립')
        st.write(f"- {word} ({freq}회) [{sentiment}]")
    with st.expander("💬 대표 민원 예시 보기"):
        for sentence in example_sentences.get(topic, []):
            st.markdown(f"• {sentence}")
