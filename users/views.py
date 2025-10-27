from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import redirect, render
from rest_framework import decorators, permissions, status, viewsets
from rest_framework.response import Response

from goals.models import Goal
from .forms import SetupForm, SignUpForm
from .models import UserProfile
from .serializers import UserSerializer

User = get_user_model()

ACTIVITY_MAP = {
    "sedentary": 1,
    "light": 2,
    "moderate": 3,
    "very_active": 5,
}


class IsSelfOrAdmin(permissions.BasePermission):
    """
    오브젝트 권한:
    - 관리자는 누구나 접근
    - 일반 유저는 자기 것만 접근 가능
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.id == request.user.id

class UserViewSet(viewsets.ModelViewSet):
    """
    사용자 뷰셋
    - 생성(회원가입): 인증 불필요 (AllowAny)
    - 목록/상세: 관리자만 전체, 일반 사용자는 자기 자신만
    - 수정/삭제: 자기 자신만, 또는 관리자
    - 비활성화(휴면)/재활성화: 커스텀 액션 제공
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """회원가입(create)은 인증 불필요"""
        if self.action == 'create':
            return [permissions.AllowAny()]
        return super().get_permissions()

    # ---- 공통 쿼리셋 제한 ----
    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    # ---- 생성: 회원가입 (인증 불필요) ----
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    # ---- 부분 수정/전체 수정: 자기 자신 또는 관리자 ----
    def update(self, request, *args, **kwargs):
        self.check_object_permissions(request, self.get_object())
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self.check_object_permissions(request, self.get_object())
        return super().partial_update(request, *args, **kwargs)

    # ---- 하드 삭제(탈퇴): 자기 자신은 비밀번호 확인 요구, 관리자는 바로 가능 ----
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if not request.user.is_staff:
            # 자기 계정 삭제 시 현재 비밀번호 검증 (보안)
            current_password = request.data.get("current_password")
            if not current_password or not request.user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    # ---- /users/api/users/me/ : 내 정보 전용 엔드포인트(GET/PATCH/DELETE) ----
    @decorators.action(detail=False, methods=["get", "patch", "delete"], url_path="me")
    def me(self, request):
        """
        GET   : 내 정보 조회
        PATCH : 내 정보 일부 수정 (email, first/last_name)
        DELETE: 내 계정 하드 삭제(탈퇴) - 비밀번호 확인 필요
        """
        user = request.user

        if request.method == "GET":
            return Response(self.get_serializer(user).data)

        if request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == "DELETE":
            current_password = request.data.get("current_password")
            if not current_password or not user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
            user.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- /users/api/users/{id}/deactivate/ : 휴면(비활성화) 전환 ----
    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsSelfOrAdmin])
    @transaction.atomic
    def deactivate(self, request, pk=None):
        """
        본인 또는 관리자가 호출 가능.
        - 일반 유저: 본인 비활성화 시 비밀번호 확인 권장
        - 결과: is_active=False (로그인/토큰 발급 불가)
        """
        user = self.get_object()
        if not request.user.is_staff:
            current_password = request.data.get("current_password")
            if not current_password or not request.user.check_password(current_password):
                return Response({"detail": "현재 비밀번호가 올바르지 않습니다."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"detail": "계정이 비활성화되었습니다.", "is_active": user.is_active})

    # ---- /users/api/users/{id}/reactivate/ : 재활성화 ----
    @decorators.action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    @transaction.atomic
    def reactivate(self, request, pk=None):
        """
        기본적으로 관리자만 재활성화(업무 규칙에 따라 self 허용도 가능).
        """
        if not request.user.is_staff:
            return Response({"detail": "관리자만 재활성화할 수 있습니다."}, status=status.HTTP_403_FORBIDDEN)
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response({"detail": "계정이 재활성화되었습니다.", "is_active": user.is_active})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("tasks:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created. Please sign in.")
            return redirect("login")
    else:
        form = SignUpForm()

    return render(request, "users/signup.html", {"form": form})


@login_required
def setup_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    initial = {
        "name": request.user.nickname or request.user.username,
        "age": profile.age or "",
        "weight": profile.weight_kg or "",
        "height": profile.height_cm or "",
        "goal": Goal.objects.filter(user=request.user).values_list("goal_type", flat=True).first() or "maintain",
        "activity_level": next((key for key, value in ACTIVITY_MAP.items() if value == profile.activity_level), "moderate"),
    }

    goal_options = [{"value": value, "label": label} for value, label in SetupForm.GOAL_CHOICES]
    activity_options = [
        {"value": "sedentary", "label": "Sedentary", "desc": "Little to no exercise"},
        {"value": "light", "label": "Light", "desc": "Light exercise 1-3 days/week"},
        {"value": "moderate", "label": "Moderate", "desc": "Moderate exercise 3-5 days/week"},
        {"value": "very_active", "label": "Very Active", "desc": "Hard exercise 6-7 days/week"},
    ]

    if request.method == "POST":
        form = SetupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            request.user.nickname = data["name"]
            request.user.save(update_fields=["nickname"])

            profile.height_cm = int(data["height"])
            profile.weight_kg = float(data["weight"])
            profile.activity_level = ACTIVITY_MAP.get(data["activity_level"], 3)

            # 나이를 통해 대략적인 생년월일 추정 (올해 기준)
            today = date.today()
            try:
                birth_date = today.replace(year=today.year - int(data["age"]))
            except ValueError:
                # 윤년 등 예외 처리
                birth_date = today.replace(month=3, day=1, year=today.year - int(data["age"]))
            profile.birth_date = birth_date

            profile.save()

            Goal.objects.update_or_create(
                user=request.user,
                defaults={"goal_type": data["goal"]},
            )

            messages.success(request, "프로필 정보가 업데이트되었습니다.")
            return redirect("tasks:dashboard")
    else:
        form = SetupForm(initial=initial)

    return render(
        request,
        "users/setup.html",
        {
            "form": form,
            "goal_options": goal_options,
            "activity_options": activity_options,
        },
    )


@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    primary_goal = Goal.objects.filter(user=request.user).values_list("goal_type", flat=True).first()

    goal_labels = {
        "lose_weight": "Lose Weight",
        "gain_muscle": "Gain Muscle",
        "maintain": "Maintain Weight",
        "endurance": "Build Endurance",
    }

    activity_labels = {
        1: "Sedentary",
        2: "Light Activity",
        3: "Moderate Activity",
        4: "Very Active",
        5: "Athlete",
    }

    bmi = profile.bmi or 0
    achievements = [
        {"id": 1, "name": "First Week Complete", "desc": "Completed your first week of workouts", "icon": "🏆", "earned": True},
        {"id": 2, "name": "Consistency Champion", "desc": "7 days in a row of logging meals", "icon": "⭐", "earned": True},
        {"id": 3, "name": "Protein Power", "desc": "Hit protein goals 5 days straight", "icon": "💪", "earned": False},
        {"id": 4, "name": "Early Bird", "desc": "Complete 10 morning workouts", "icon": "🌅", "earned": False},
    ]

    weekly_stats = {
        "workouts_completed": 6,
        "workouts_planned": 7,
        "avg_calories": 2150,
        "streak_days": 12,
        "goal_progress": 85,
    }

    workout_percent = (weekly_stats["workouts_completed"] / weekly_stats["workouts_planned"]) * 100 if weekly_stats["workouts_planned"] else 0
    workout_label = f"{weekly_stats['workouts_completed']}/{weekly_stats['workouts_planned']}"

    avatar_initial = (request.user.nickname or request.user.username or "")[0:1].upper()

    return render(
        request,
        "users/profile.html",
        {
            "profile": profile,
            "bmi": bmi,
            "goal_label": goal_labels.get(primary_goal, "Maintain Weight"),
            "activity_label": activity_labels.get(profile.activity_level, "Moderate Activity"),
            "achievements": achievements,
            "weekly_stats": weekly_stats,
            "workout_percent": workout_percent,
            "workout_label": workout_label,
            "avatar_initial": avatar_initial or "H",
        },
    )
