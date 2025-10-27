from rest_framework import serializers
from .models import CustomUser, UserProfile, HealthData
from django.contrib.auth import get_user_model

#--- 추가 ----

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    유저 기본 직렬화기
    - username/id는 읽기전용 (아이디 변경 방지)
    - password는 쓰기 전용 (회원가입 시 필요)
    - is_active는 일반 PATCH로는 수정 불가(휴면/복구는 별도 액션에서 처리)
    """
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name", "is_active", "date_joined"]
        read_only_fields = ["id", "is_active", "date_joined"]
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        """비밀번호 해싱하여 유저 생성"""
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


# ---- 추가 끝 ----
class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id", "username", "email", "nickname",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()
    bmi = serializers.ReadOnlyField()
    bmi_category = serializers.ReadOnlyField()
    daily_calories = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "id", "user", "gender", "height_cm", "weight_kg",
            "target_weight_kg", "activity_level", "birth_date",
            "phone_number", "created_at", "updated_at",
            "age", "bmi", "bmi_category", "daily_calories"
        ]
        read_only_fields = ["id", "created_at", "updated_at", "age", "bmi", "bmi_category", "daily_calories"]

    def get_daily_calories(self, obj):
        return obj.calculate_daily_calories()


class HealthDataSerializer(serializers.ModelSerializer):
    blood_pressure_status = serializers.ReadOnlyField()
    weight_change = serializers.ReadOnlyField()

    class Meta:
        model = HealthData
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "blood_pressure_status", "weight_change"]
