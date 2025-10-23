# team2_final/urls.py
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.http import FileResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from tasks import urls as tasks_urls

# 앱별 urls
from users import urls as users_urls
from users import views as users_views

# 로컬 뷰
from . import views

# Public(AllowAny) JWT 뷰
from .auth_views import (
    PublicTokenObtainPairView,
    PublicTokenRefreshView,
    PublicTokenVerifyView,
)
from .healthz import healthz, readyz, simple_token
from .today_views import today_summary
from .views import landing


# ---------- 유틸성 뷰 ----------
def api_root_healthcheck(_request):
    """API 루트 상태 정보 (루트 충돌 피하려고 /api/health 로 이동)"""
    return JsonResponse(
        {
            "status": "ok",
            "message": "Workout & feedback API root",
        }
    )


def api_docs(_request):
    """프로젝트 루트의 openapi.json을 원본 그대로 반환"""
    doc_path = Path(settings.BASE_DIR) / "openapi.json"
    if not doc_path.exists():
        return JsonResponse({"detail": "openapi.json not found"}, status=404)
    return FileResponse(doc_path.open("rb"), content_type="application/json")


urlpatterns = [
    # ---------- 기본 페이지 ----------
    path("", landing, name="landing"),  # 루트는 landing만 사용
    # 편의 리다이렉트: 로그인만 유지 (logout 리다이렉트는 제거)
    path("users/login/", RedirectView.as_view(url="/accounts/login/", permanent=False)),
    # ✅ 실제 LogoutView 경로(POST 전용). 템플릿에서는 반드시 POST 폼으로 호출할 것.
    path(
        "logout/",
        LogoutView.as_view(next_page=getattr(settings, "LOGOUT_REDIRECT_URL", "/")),
        name="logout",
    ),
    # ---------- favicon ----------
    path(
        "favicon.ico", RedirectView.as_view(url="/static/favicon.ico", permanent=False)
    ),
    # ---------- 헬스체크 / 오늘 요약 ----------
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path("healthz", healthz),  # 슬래시 없는 버전도 허용
    path("readyz", readyz),
    path("auth/simple-token", simple_token, name="simple_token"),
    # 요약 엔드포인트 (둘 다 유지: 하위호환)
    path("api/today/", today_summary, name="today-summary"),
    path("api/today/summary/", today_summary, name="today-summary-alias"),
    # 추가 상태
    path("api/health/", api_root_healthcheck, name="api_root_healthcheck"),
    # ---------- Admin / 계정 ----------
    path("admin/", admin.site.urls),
    path(
        "accounts/", include("django.contrib.auth.urls")
    ),  # /accounts/login/, /accounts/logout/ (POST)
    # ---------- 유저 개별 페이지 ----------
    path("setup/", users_views.setup_view, name="user_setup"),
    path("profile/", users_views.profile_view, name="user_profile"),
    path(
        "signup/",
        RedirectView.as_view(pattern_name="login", permanent=False),
        name="user_signup",
    ),
    # ---------- JWT ----------
    # 기본 JWT
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Public JWT (AllowAny)
    path(
        "auth/token/",
        PublicTokenObtainPairView.as_view(),
        name="public_token_obtain_pair",
    ),
    path(
        "auth/token/refresh/",
        PublicTokenRefreshView.as_view(),
        name="public_token_refresh",
    ),
    path(
        "auth/token/verify/",
        PublicTokenVerifyView.as_view(),
        name="public_token_verify",
    ),
    # ---------- API 라우트 ----------
    path(
        "api/",
        include((users_urls.api_urlpatterns, "users_api"), namespace="users_api"),
    ),
    path("api/", include("goals.urls")),
    path(
        "api/",
        include((tasks_urls.api_urlpatterns, "tasks_api"), namespace="tasks_api"),
    ),
    path("api/", include("intakes.urls")),
    path("api/", include("feedbacks.urls")),
    path("api/ai/", include("ai.urls")),
    # ---------- 페이지 라우트 ----------
    path("users/", include((users_urls.page_urlpatterns, "users"), namespace="users")),
    path("tasks/", include((tasks_urls.page_urlpatterns, "tasks"), namespace="tasks")),
    # ---------- 레거시/오타 경로 흡수 ----------
    re_path(
        r"^task/(?P<rest>.*)$",
        RedirectView.as_view(url="/tasks/%(rest)s", permanent=False),
    ),
    path(
        "task/dashboard/",
        RedirectView.as_view(url="/tasks/dashboard/", permanent=False),
    ),
    # ---------- OpenAPI / 문서 ----------
    path("openapi.json", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("docs/raw", api_docs, name="api_docs"),
]

# ---------- 개발용 미디어 서빙 (업로드 이미지 표시용) ----------
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, "PROM_ENABLED", False):
    urlpatterns += [path("", include("django_prometheus.urls"))]
