# 🏋️ Team2 Final — Healthcare Todo App

AI 기반 **운동·식단·생활 루틴 관리 웹앱**
Django + DRF + Postgres + Docker Compose 기반 프로젝트

---

## 🚀 기능 요약

- **Workout 관리**
  - 주간 운동 플랜 생성/수정
  - TaskItem(세트, 반복수, 강도, 완료여부) 저장
  - Dashboard에서 오늘 운동 진척도 확인

- **식단 관리**
  - 사진 업로드 → AI 자동 분석 (칼로리·영양소 추출)
  - NutritionLog 집계 + DailyGoal 반영

- **Dashboard**
  - 오늘의 운동/식단/목표 합계
  - 진행도 Progress Ring 시각화

- **AI 인사이트**
  - Hugging Face 이미지/텍스트 모델 연동
  - 개인 맞춤 식단/운동 추천

- **기타**
  - JWT 로그인 (SimpleJWT)
  - 관리자 페이지(/admin/)
  - OpenAPI 문서 (/docs, /redoc, /openapi.json)
  - Prometheus 메트릭 지원 (옵션)

---

## ⚙️ 개발/운영 환경

### 1) 로컬 개발 (Postgres 컨테이너)
```bash
# DB 띄우기
docker compose -f docker-compose.local.yml up -d

# Django 서버 실행
python manage.py runserver

접속: http://127.0.0.1:8000

DB 연결: DATABASE_URL=postgresql://team2_user:supersecret@127.0.0.1:55432/team2_final

healthz: http://127.0.0.1:8000/healthz

readyz: http://127.0.0.1:8000/readyz

2) 퍼블릭 배포 (EC2 + Docker Compose)
ssh -i team2.pem ubuntu@<EC2_IP>
cd ~/team2_final
docker compose up -d --build


접속: http://<EC2_IP>:8000

healthz: http://<EC2_IP>:8000/healthz

readyz: http://<EC2_IP>:8000/readyz

🗂 데이터 초기화 & Seed
# 관리자 계정 생성
python manage.py createsuperuser

# 운동 데이터 2개월치 시드
python manage.py seed_demo --user swj6824 \
  --start 2025-08-20 --end 2025-10-17 \
  --ex_file tasks/fixtures/exercises.json --reset_demo

🔒 보안 규칙

.env, .pem, .key 등 비밀파일은 절대 커밋 금지

Hugging Face 토큰 등 API Key는 GitHub Secrets / 환경변수로만 주입

.gitignore에 이미 추가됨

✅ 라스트 체크리스트

 로컬 /healthz, /readyz → 200 OK

 EC2 /healthz, /readyz → 200 OK

 DB 연결 (로컬/EC2 둘 다 Postgres 정상)

 Seed Demo (운동 데이터 2개월치 반영 완료)

 Superuser 생성 및 로그인 확인
