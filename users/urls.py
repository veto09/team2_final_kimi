from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import oauth_views
from .views import UserViewSet

app_name = "users"

# --- API 라우터 ---
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")

api_urlpatterns = [
    path("", include(router.urls)),  # /api/에 마운트 예정
]

# --- 페이지(OAuth/Logout) 라우트 ---
page_urlpatterns = [
    # OAuth
    path("oauth/kakao/login/", oauth_views.kakao_login, name="kakao_login"),
    path("oauth/kakao/callback/", oauth_views.kakao_callback, name="kakao_callback"),
    path("oauth/naver/login/", oauth_views.naver_login, name="naver_login"),
    path("oauth/naver/callback/", oauth_views.naver_callback, name="naver_callback"),
    # ✅ 로그아웃(POST 전용)
    path(
        "logout/",
        LogoutView.as_view(next_page=getattr(settings, "LOGOUT_REDIRECT_URL", "/")),
        name="logout",
    ),
]
