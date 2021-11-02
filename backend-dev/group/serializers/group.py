from base_serializers import UserSerializer, ProfileSerializer, GroupSerializer, ImageSerializer, CategorySerializer
from rest_framework import serializers
from group.models import Group, Category
from post.models import Post
from award.models import Award
from django.contrib.auth import get_user_model
User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'color', 'name', 'slug', 'about']

class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award
        fields = ['id', 'name', 'logo', 'description', 'price']

class GroupListSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    subscribers_count = serializers.ReadOnlyField()
    subscribed = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'title', 'about',  'status', 'subscribers_count',
                  'subscribed', 'author', 'created_at', 'updated_at']

    def get_subscribed(self, obj):
        return obj.subscribers.filter(pk=self.context.get('request').user.id).exists()


class GroupRetriveSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    subscribers_count = serializers.ReadOnlyField()
    subscribed = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'title', 'about',  'status', 'subscribers_count',
                  'subscribed', 'post_count', 'author', 'is_author', 'created_at', 'updated_at']

    def get_post_count(self, obj):
        return Post.published.filter(group=obj).count()

    def get_subscribed(self, obj):
        return obj.subscribers.filter(pk=self.context.get('request').user.id).exists()
    
    def get_is_author(self, obj):
        return obj.author.id == self.context.get('request').user.id


class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['about', 'title', 'status', 'token']


class GroupSubscribersSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name',
                  'last_name', 'is_active', 'avatar']


class GroupBlacklistsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name',
                  'last_name', 'is_active', 'avatar']
