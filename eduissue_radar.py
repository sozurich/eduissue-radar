
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
import requests

# 1. Kakao 텍스트 파싱
def parse_kakao_text(file):
    text = file.read().decode('utf-8')
    lines = text.splitlines()
    parsed=[]
    current_date=None
    date_pattern=r'-{10,}\s*(\d{4}년 \d{1,2}월 \d{1,2}일.*?)\s*-{10,}'
    msg_pattern=r'\[(.*?)\] \[(오전|오후) (\d{1,2}:\d{2})\] (.+)'
    for line in lines:
        dm=re.match(date_pattern,line)
        if dm:
            current_date=dm.group(1)
            continue
        mm=re.match(msg_pattern,line)
        if mm and current_date:
            user,ampm,time_str,msg=mm.groups()
            hour,minute=map(int,time_str.split(':'))
            if ampm=='오후' and hour!=12: hour+=12
            timestamp=f"{hour:02}:{minute:02}"
            parsed.append({"날짜":current_date,"사용자":user,"시간":timestamp,"메시지":msg})
    return pd.DataFrame(parsed)

# 2. 민원 키워드 추출
issue_keywords=["배송","지연","누락","불량","부족","정산","반품","추가","오류"]
def extract_issues(df):
    msgs=df[df['메시지'].str.contains('|'.join(issue_keywords))]
    words=' '.join(msgs['메시지'].tolist())
    nouns=re.findall(r'[\uAC00-\uD7A3]+',words)
    cnt=Counter(nouns)
    return msgs,cnt.most_common(10)

# 3. 네이버 뉴스 크롤링
def crawl_naver_openapi(query):
    client_id=st.secrets.get('NAVER_CLIENT_ID')
    client_secret=st.secrets.get('NAVER_CLIENT_SECRET')
    if not client_id or not client_secret:
        st.error('NAVER API 키를 설정해주세요.')
        return []
    headers={'X-Naver-Client-Id':client_id,'X-Naver-Client-Secret':client_secret}
    params={'query':query+' 교과서','display':5,'sort':'date'}
    res=requests.get('https://openapi.naver.com/v1/search/news.json',headers=headers,params=params)
    if res.status_code!=200:
        st.error(f'네이버 API 오류: {res.status_code}')
        return []
    items=res.json().get('items',[])
    results=[]
    for it in items:
        title=it.get('title','').replace('<b>','').replace('</b>','')
        link=it.get('originallink') or it.get('link')
        date_str=it.get('pubDate','')
        try:
            pub=datetime.strptime(date_str,'%a, %d %b %Y %H:%M:%S %z')
        except:
            pub=datetime.now()
        results.append({'제목':title,'링크':link,'날짜':pub,'표시날짜':pub.strftime('%Y-%m-%d')})
    return results

# 4. Local summarizer
def local_summarize(text,max_sentences=5):
    # split into sentences
    sents=re.split(r'(?<=[.!?])\s+|\n',text)
    # calculate word freq
    words=re.findall(r'[\w가-힣]+',text.lower())
    stop=set(['이거','그거','저희','합니다','입니다','그리고','하지만','요','해요'])
    freq=Counter(w for w in words if len(w)>1 and w not in stop)
    # score sentences
    scored=[]
    for i,s in enumerate(sents):
        w=re.findall(r'[\w가-힣]+',s.lower())
        score=sum(freq.get(wd,0) for wd in w)
        scored.append((score,i,s))
    top=sorted(scored,reverse=True)[:max_sentences]
    top_sorted=sorted(top,key=lambda x:x[1])
    summary=' '.join(s for _,_,s in top_sorted)
    return summary or '로컬 요약을 위한 충분한 텍스트가 없습니다.'

# 5. UI
st.title('📚 EduIssue Radar')
st.markdown('교과서 민원 메시지 분석 + 로컬 요약')

uploaded=st.file_uploader('카카오톡 채팅 .txt 파일 업로드',type='txt')
if uploaded:
    df=parse_kakao_text(uploaded)
    df['날짜']=pd.to_datetime(df['날짜'].str.extract(r'(\d{4}년 \d{1,2}월 \d{1,2}일)',expand=False),format='%Y년 %m월 %d일',errors='coerce').dt.date
    min_d,max_d=df['날짜'].min(),df['날짜'].max()
    st.markdown(f'**분석 가능한 날짜:** {min_d} ~ {max_d}')
    sd,ed=st.date_input('분석 기간 선택',[min_d,max_d])
    df_sel=df[(df['날짜']>=sd)&(df['날짜']<=ed)]
    iss_df,top=extract_issues(df_sel)

    tab1,tab2,tab3=st.tabs(['📊 민원 분석','📰 키워드 뉴스','📝 요약'])
    with tab1:
        st.success(f'{sd} ~ {ed} 메시지 {len(df_sel)}건')
        st.write(iss_df[['날짜','시간','사용자','메시지']])
        st.markdown('**민원 키워드 TOP10**')
        for i in range(0,len(top),3):
            cols=st.columns(3)
            for j,(kw,cnt) in enumerate(top[i:i+3]):
                cols[j].markdown(f'- **{kw}** ({cnt}회)')
    with tab2:
        st.subheader('🔍 연관 뉴스')
        for kw,_ in top[:3]:
            with st.expander(f'{kw} 관련 뉴스'):
                arts=crawl_naver_openapi(kw)
                for a in arts:
                    st.markdown(f"- [{a['제목']}]({a['링크']}) ({a['표시날짜']})")
        st.subheader('📚 주제별 추천 뉴스')
        extras=['교과서','AI 디지털교과서','비상교육','천재교육','미래엔']
        for topic in extras:
            with st.expander(f'{topic} 관련 뉴스'):
                arts=crawl_naver_openapi(topic)
                for a in arts:
                    st.markdown(f"- [{a['제목']}]({a['링크']}) ({a['표시날짜']})")
    with tab3:
        st.subheader('📝 로컬 요약')
        msgs=df_sel['메시지'].tolist()
        text=' '.join(msgs)
        count=st.slider('요약 문장 수',1,10,5)
        if st.button('✅ 요약 실행'):
            summary=local_summarize(text,count)
            st.write(summary)
        else:
            st.markdown('버튼을 눌러 요약을 실행하세요.')
