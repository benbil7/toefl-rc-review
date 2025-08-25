import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from collections import Counter

# 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# API 설정
API_BASE_URL = st.secrets.get("API_BASE_URL", "YOUR_APPS_SCRIPT_URL")

# API 헤더
headers = {"Content-Type": "application/json"}

# 세션 상태 초기화
if 'current_session' not in st.session_state:
    st.session_state.current_session = None
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'current_question_idx' not in st.session_state:
    st.session_state.current_question_idx = 0
if 'show_results' not in st.session_state:
    st.session_state.show_results = False
if 'skill_tags' not in st.session_state:
    st.session_state.skill_tags = []

# API 호출 함수들
def api_get(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def api_post(endpoint, data):
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", 
                                headers=headers, 
                                json=data)
        return response.json() if response.status_code == 200 else None
    except:
        return None

# 스킬 태그 로드
def load_skill_tags():
    tags = api_get("/skill-tags")
    if tags:
        st.session_state.skill_tags = tags.get('tags', [])
    return st.session_state.skill_tags

# 페이지 설정
st.set_page_config(page_title="TOEFL RC 복습 시스템", layout="wide")

# 사이드바 네비게이션
page = st.sidebar.selectbox("페이지 선택", ["Dashboard", "오늘 학습", "오답 노트"])

# Dashboard 페이지
if page == "Dashboard":
    st.title("📊 TOEFL RC 학습 대시보드")
    
    # 대시보드 데이터 로드
    dashboard_data = api_get("/dashboard")
    
    if dashboard_data:
        # 메트릭 카드
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("오늘 목표", f"{dashboard_data.get('due_today', 0)}/{dashboard_data.get('daily_target', 10)}")
        with col2:
            st.metric("누적 학습일", dashboard_data.get('total_days', 0))
        with col3:
            st.metric("연속 학습일", dashboard_data.get('streak_days', 0))
        with col4:
            st.metric("백로그", dashboard_data.get('backlog', 0))
        
        st.divider()
        
        # 차트 영역
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 취약 유형 TOP 3")
            weak_skills = dashboard_data.get('weak_skills', [])
            if weak_skills:
                fig, ax = plt.subplots(figsize=(8, 4))
                skills = [s['skill'] for s in weak_skills[:3]]
                counts = [s['wrong_count'] for s in weak_skills[:3]]
                ax.barh(skills, counts, color=['#ff6b6b', '#ffa06b', '#ffcb6b'])
                ax.set_xlabel('오답 횟수')
                st.pyplot(fig)
            else:
                st.info("아직 분석할 데이터가 없습니다.")
        
        with col2:
            st.subheader("📅 최근 14일 학습 히트맵")
            heatmap_data = dashboard_data.get('heatmap', [])
            if heatmap_data:
                # 히트맵 생성
                dates = [d['date'] for d in heatmap_data]
                counts = [d['count'] for d in heatmap_data]
                
                fig, ax = plt.subplots(figsize=(8, 4))
                # 2주 데이터를 2행으로 표시
                data_matrix = np.array(counts).reshape(2, 7)
                im = ax.imshow(data_matrix, cmap='YlOrRd', aspect='auto')
                
                ax.set_xticks(range(7))
                ax.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
                ax.set_yticks(range(2))
                ax.set_yticklabels(['지난주', '이번주'])
                
                # 값 표시
                for i in range(2):
                    for j in range(7):
                        text = ax.text(j, i, data_matrix[i, j],
                                     ha="center", va="center", color="black")
                
                plt.colorbar(im, ax=ax)
                st.pyplot(fig)
            else:
                st.info("학습 기록이 없습니다.")
        
        st.divider()
        
        # 설정 영역
        st.subheader("⚙️ 설정")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            rest_day = st.radio("휴무일 선택", 
                              ["없음", "토요일", "일요일"],
                              index=["없음", "토요일", "일요일"].index(
                                  dashboard_data.get('rest_day', '없음')))
        
        with col2:
            daily_target = st.number_input("일일 목표 문항", 
                                          value=dashboard_data.get('daily_target', 10),
                                          min_value=1, max_value=50)
        
        with col3:
            email = st.text_input("알림 이메일", 
                                 value=dashboard_data.get('email', ''))
        
        if st.button("설정 저장"):
            settings_data = {
                'rest_day': rest_day if rest_day != "없음" else None,
                'daily_target': daily_target,
                'email': email
            }
            result = api_post("/settings", settings_data)
            if result:
                st.success("설정이 저장되었습니다!")
            else:
                st.error("설정 저장 실패")

# 오늘 학습 페이지
elif page == "오늘 학습":
    st.title("📚 오늘의 학습")
    
    # 오늘 due 문항 로드
    if not st.session_state.current_session:
        today = datetime.now().strftime('%Y-%m-%d')
        due_data = api_get(f"/due?date={today}")
        
        if due_data and due_data.get('questions'):
            st.session_state.current_session = due_data['questions']
            st.session_state.answers = {}
            st.session_state.current_question_idx = 0
            st.session_state.show_results = False
    
    if st.session_state.current_session:
        questions = st.session_state.current_session
        current_q = questions[st.session_state.current_question_idx]
        
        # 진행률 표시
        progress = (st.session_state.current_question_idx + 1) / len(questions)
        st.progress(progress)
        st.write(f"문항 {st.session_state.current_question_idx + 1} / {len(questions)}")
        
        # 레이아웃: 좌측 지문, 우측 문항
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📖 지문")
            # 지문 컨테이너 (스크롤 가능)
            passage_container = st.container()
            with passage_container:
                st.markdown(f"""
                <div style="height: 500px; overflow-y: auto; padding: 20px; 
                           background-color: #f9f9f9; border-radius: 10px;">
                    <h4>{current_q.get('passage_title', 'Passage')}</h4>
                    <p>{current_q.get('passage_text', 'No passage text available.')}</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.subheader("❓ 문항")
            
            if not st.session_state.show_results:
                # 문항 표시
                st.write(current_q['question_text'])
                
                # 선택지
                options = json.loads(current_q.get('options', '[]'))
                q_id = current_q['question_id']
                
                answer = st.radio(
                    "답안 선택:",
                    options,
                    key=f"q_{q_id}",
                    index=None if q_id not in st.session_state.answers else 
                          options.index(st.session_state.answers[q_id]['answer'])
                )
                
                # 플래그
                flagged = st.checkbox("🚩 플래그 표시", 
                                     value=st.session_state.answers.get(q_id, {}).get('flagged', False))
                
                if answer:
                    st.session_state.answers[q_id] = {
                        'answer': answer,
                        'flagged': flagged
                    }
                
                # 네비게이션
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("◀ 이전") and st.session_state.current_question_idx > 0:
                        st.session_state.current_question_idx -= 1
                        st.rerun()
                
                with col2:
                    if st.session_state.current_question_idx == len(questions) - 1:
                        if st.button("제출하기", type="primary"):
                            st.session_state.show_results = True
                            st.rerun()
                
                with col3:
                    if st.button("다음 ▶") and st.session_state.current_question_idx < len(questions) - 1:
                        st.session_state.current_question_idx += 1
                        st.rerun()
            
            else:
                # 결과 표시
                st.success("✅ 제출 완료!")
                
                # 채점 결과
                q_id = current_q['question_id']
                user_answer = st.session_state.answers.get(q_id, {}).get('answer', '')
                correct_answer = current_q['answer']
                is_correct = user_answer == correct_answer
                
                if is_correct:
                    st.success(f"정답입니다! ✅")
                else:
                    st.error(f"오답입니다. 정답: {correct_answer}")
                    st.write(f"당신의 답: {user_answer}")
                
                # 해설
                st.write("**해설:**")
                st.info(current_q.get('explanation', 'No explanation available.'))
                
                # 오답노트 추가
                if not is_correct:
                    with st.expander("오답노트에 추가"):
                        # 스킬 태그 로드
                        tags = load_skill_tags()
                        tag_names = [t['name'] for t in tags]
                        
                        # 태그 선택
                        selected_tags = st.multiselect("유형 태그 선택", tag_names)
                        
                        # 새 태그 추가
                        new_tag = st.text_input("새 태그 추가")
                        if st.button("태그 추가") and new_tag:
                            result = api_post("/skill-tags", {
                                'action': 'create',
                                'name': new_tag
                            })
                            if result:
                                st.success(f"태그 '{new_tag}' 추가됨")
                                load_skill_tags()
                                st.rerun()
                        
                        # 메모
                        memo = st.text_area("메모")
                        
                        if st.button("오답노트 저장"):
                            # 제출 데이터 준비
                            submit_data = [{
                                'question_id': q_id,
                                'user_answer': user_answer,
                                'correct': False,
                                'flagged': st.session_state.answers.get(q_id, {}).get('flagged', False),
                                'add_to_wrongnote': True,
                                'memo': memo,
                                'skill_tags': selected_tags
                            }]
                            
                            result = api_post("/submit", submit_data)
                            if result:
                                st.success("오답노트에 저장되었습니다!")
                
                # 다음 문항으로
                if st.session_state.current_question_idx < len(questions) - 1:
                    if st.button("다음 문항 ▶"):
                        st.session_state.current_question_idx += 1
                        st.session_state.show_results = False
                        st.rerun()
                else:
                    st.balloons()
                    st.success("모든 문항을 완료했습니다! 🎉")
                    
                    # 전체 제출
                    if st.button("학습 종료"):
                        # 모든 답안 제출
                        submit_data = []
                        for q in questions:
                            q_id = q['question_id']
                            if q_id in st.session_state.answers:
                                user_ans = st.session_state.answers[q_id]['answer']
                                submit_data.append({
                                    'question_id': q_id,
                                    'user_answer': user_ans,
                                    'correct': user_ans == q['answer'],
                                    'flagged': st.session_state.answers[q_id].get('flagged', False),
                                    'add_to_wrongnote': False,
                                    'memo': '',
                                    'skill_tags': []
                                })
                        
                        result = api_post("/submit", submit_data)
                        if result:
                            st.success("학습 기록이 저장되었습니다!")
                            # 세션 초기화
                            st.session_state.current_session = None
                            st.session_state.answers = {}
                            st.session_state.current_question_idx = 0
                            st.session_state.show_results = False
                            st.rerun()
    else:
        st.info("오늘 학습할 문항이 없습니다. 🎯")

# 오답 노트 페이지
elif page == "오답 노트":
    st.title("📝 오답 노트")
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["오답 목록", "새 오답 추가", "태그 관리"])
    
    with tab1:
        # 오답 목록
        wrong_notes = api_get("/wrongnotes")
        
        if wrong_notes and wrong_notes.get('notes'):
            # 필터링
            col1, col2 = st.columns(2)
            with col1:
                # 스킬 태그 필터
                tags = load_skill_tags()
                tag_names = ['전체'] + [t['name'] for t in tags]
                selected_tag = st.selectbox("유형 필터", tag_names)
            
            with col2:
                # 정렬
                sort_by = st.selectbox("정렬 기준", ["최신순", "오래된순", "오답 횟수순"])
            
            # 데이터프레임 생성
            df = pd.DataFrame(wrong_notes['notes'])
            
            # 필터 적용
            if selected_tag != '전체':
                df = df[df['skill_tags'].apply(lambda x: selected_tag in x if x else False)]
            
            # 정렬 적용
            if sort_by == "최신순":
                df = df.sort_values('date_added', ascending=False)
            elif sort_by == "오래된순":
                df = df.sort_values('date_added', ascending=True)
            elif sort_by == "오답 횟수순":
                df = df.sort_values('wrong_count', ascending=False)
            
            # 테이블 표시
            st.dataframe(
                df[['date_added', 'question_text', 'skill_tags', 'wrong_count']],
                use_container_width=True,
                hide_index=True
            )
            
            # 상세 보기
            st.subheader("상세 보기")
            if not df.empty:
                selected_idx = st.selectbox("문항 선택", df.index, 
                                           format_func=lambda x: f"{df.loc[x, 'question_text'][:50]}...")
                
                if selected_idx is not None:
                    note = df.loc[selected_idx]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**문항:**")
                        st.write(note['question_text'])
                        st.write(f"**정답:** {note['correct_answer']}")
                        st.write(f"**내 답:** {note['user_answer']}")
                    
                    with col2:
                        st.write("**해설:**")
                        st.info(note.get('explanation', 'No explanation'))
                        st.write("**메모:**")
                        st.write(note.get('why_wrong', 'No memo'))
                    
                    # 편집/삭제
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("편집", key=f"edit_{selected_idx}"):
                            st.session_state.editing_note = note
                    with col2:
                        if st.button("삭제", key=f"delete_{selected_idx}", type="secondary"):
                            result = api_post("/wrongnote/delete", {'note_id': note['note_id']})
                            if result:
                                st.success("삭제되었습니다.")
                                st.rerun()
        else:
            st.info("오답 노트가 비어있습니다.")
    
    with tab2:
        # 새 오답 추가
        st.subheader("새 오답 붙여넣기")
        
        with st.form("add_wrong_note"):
            passage_text = st.text_area("지문", height=200)
            question_text = st.text_area("문항", height=100)
            
            col1, col2 = st.columns(2)
            with col1:
                options = st.text_area("선택지 (줄바꿈으로 구분)", height=100)
                correct_answer = st.text_input("정답")
            
            with col2:
                user_answer = st.text_input("내 답")
                
                # 스킬 태그
                tags = load_skill_tags()
                tag_names = [t['name'] for t in tags]
                selected_tags = st.multiselect("유형 태그", tag_names)
            
            explanation = st.text_area("해설", height=100)
            memo = st.text_area("메모", height=100)
            
            submitted = st.form_submit_button("오답 추가")
            
            if submitted:
                # 오답 데이터 준비
                wrong_note_data = {
                    'passage_text': passage_text,
                    'question_text': question_text,
                    'options': options.split('\n') if options else [],
                    'correct_answer': correct_answer,
                    'user_answer': user_answer,
                    'explanation': explanation,
                    'why_wrong': memo,
                    'skill_tags': selected_tags
                }
                
                result = api_post("/wrongnote", wrong_note_data)
                if result:
                    st.success("오답이 추가되었습니다!")
                    st.rerun()
                else:
                    st.error("오답 추가 실패")
    
    with tab3:
        # 태그 관리
        st.subheader("유형 태그 관리")
        
        # 현재 태그 목록
        tags = load_skill_tags()
        
        if tags:
            st.write("**현재 태그 목록:**")
            for tag in tags:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    new_name = st.text_input(f"태그 이름", value=tag['name'], 
                                            key=f"tag_name_{tag['tag_id']}")
                with col2:
                    if st.button("수정", key=f"edit_tag_{tag['tag_id']}"):
                        result = api_post("/skill-tags", {
                            'action': 'update',
                            'tag_id': tag['tag_id'],
                            'name': new_name
                        })
                        if result:
                            st.success(f"태그 수정됨")
                            load_skill_tags()
                            st.rerun()
                with col3:
                    if st.button("삭제", key=f"del_tag_{tag['tag_id']}", type="secondary"):
                        result = api_post("/skill-tags", {
                            'action': 'delete',
                            'tag_id': tag['tag_id']
                        })
                        if result:
                            st.success(f"태그 삭제됨")
                            load_skill_tags()
                            st.rerun()
        
        # 새 태그 추가
        st.divider()
        st.write("**새 태그 추가:**")
        new_tag = st.text_input("태그 이름", key="new_tag_add")
        if st.button("추가") and new_tag:
            result = api_post("/skill-tags", {
                'action': 'create',
                'name': new_tag
            })
            if result:
                st.success(f"태그 '{new_tag}' 추가됨")
                load_skill_tags()
                st.rerun()

# 푸터
st.sidebar.divider()
st.sidebar.caption("TOEFL RC 복습 시스템 v1.0")
st.sidebar.caption("에빙하우스 간격 반복 학습법 적용")