from apps.market.models import DailyPrice, Security
from rest_framework import serializers


class SecuritySerializer(serializers.ModelSerializer):
    exchange = serializers.CharField(source="exchange.code", read_only=True)

    class Meta:
        model = Security
        fields = [
            "id",
            "exchange",
            "symbol",
            "company_name",
            "isin",
            "sector",
            "industry",
            "security_type",
            "listing_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DailyPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyPrice
        fields = [
            "date",
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "source",
        ]
        read_only_fields = fields


class SecurityQuerySerializer(serializers.Serializer):
    exchange = serializers.CharField(required=False, max_length=16)


class PriceQuerySerializer(SecurityQuerySerializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    limit = serializers.IntegerField(default=100, min_value=1, max_value=1000)

    def validate(self, attrs):
        if "start" in attrs and "end" in attrs and attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("Start must not be after end.")
        return attrs


class HealthSerializer(serializers.Serializer):
    application = serializers.CharField()
    database = serializers.CharField()
    redis = serializers.CharField()
