from django_filters import rest_framework as filters
from group.models import Group
from activity.models import Activity
from utils.paginations import PazeSizePagination
from rest_framework import generics, views, response, permissions, exceptions, status
from rest_framework import filters as rest_framework_filters
from django.shortcuts import get_object_or_404
from django.core.serializers import serialize
from group.serializers.group import GroupListSerializer, GroupUpdateSerializer, GroupRetriveSerializer, GroupSubscribersSerializer, GroupBlacklistsSerializer
from rest_framework.exceptions import NotFound
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
User = get_user_model()


class IsNotBlacklisted(permissions.BasePermission):
    message = 'You can not view this route!'

    def has_permission(self, request, view):
        try:
            group = Group.objects.select_related('author').get(
                author__username=view.kwargs.get('username')
            )
            return not group.blacklists.filter(pk=request.user.id).exists() and request.user.is_authenticated
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return not obj.blacklists.filter(pk=request.user.id).exists() and request.user.is_authenticated
        return not obj.blacklists.filter(pk=request.user.id).exists() and request.user.is_authenticated


class IsGroupAuthor(permissions.BasePermission):
    message = 'You can not view this route!'

    def has_permission(self, request, view):
        try:
            group = Group.objects.select_related('author').get(
                author__username=view.kwargs.get('username')
            )
            return group.author.id == request.user.id
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupFilter(filters.FilterSet):
    o = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
        ),
    )

    class Meta:
        model = Group
        fields = {
            'about': ['icontains'],
            'author__username': ['icontains'],
            'author__first_name': ['icontains'],
            'author__last_name': ['icontains'],
        }


class GroupListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GroupListSerializer
    queryset = Group.objects.all()
    pagination_class = PazeSizePagination
    filter_backends = [rest_framework_filters.SearchFilter]
    search_fields = ['about', 'author__username', 'author__first_name', 'author__last_name']


class GroupSubscribedListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GroupListSerializer
    pagination_class = PazeSizePagination
    filterset_class = GroupFilter

    def get_queryset(self):
        try:
            return Group.objects.filter(subscribers=self.request.user.id)
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupRetriveView(generics.RetrieveAPIView):
    permission_classes = [IsNotBlacklisted]
    serializer_class = GroupRetriveSerializer

    def get_object(self):
        try:
            return Group.objects.select_related('author').get(
                author__username=self.kwargs['username']
            )
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupUpdateView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsGroupAuthor]
    serializer_class = GroupUpdateSerializer

    def get_object(self):
        try:
            return Group.objects.select_related('author').get(
                author__username=self.kwargs['username']
            )
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupSubscribeView(views.APIView):
    permission_classes = [IsNotBlacklisted]

    def get(self, request, username, token=None):
        try:
            user = User.objects.get(id=request.user.id)
            group = Group.objects.select_related('author').get(
                author__username=username
            )
            subscribed = group.subscribers.filter(pk=user.id).exists()
            return response.Response({
                'subscribed': subscribed,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def post(self, request, username, token=None):
        try:
            group = Group.objects.select_related('author').get(
                author__username=username
            )
            
            subscribed = False
            if group.subscribers.filter(pk=request.user.id).exists():
                subscribed = True
            elif group.status=='public':
                if group.token == token:
                    group.subscribers.add(request.user.id)
                    subscribed = True
                    # group joined
                    Activity.objects.create(target=request.user.id, group_id=group.id,
                                    sender_id=request.user.id, target_type="user", verb="joined")
                else:
                    return response.Response({"detail": "Invalid token!"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
            elif group.status=='private':
                group.subscribers.add(request.user.id)
                subscribed = True
            return response.Response({
                'subscribed': subscribed,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def delete(self, request, username, token=None):
        try:
            group = Group.objects.select_related('author').get(
                author__username=username
            )

            if group.author.id == request.user.id:
                return response.Response({"detail": "You can not unsubscribe your own group!"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
            else:
                subscribed = True
                if group.subscribers.filter(pk=request.user.id).exists():
                    group.subscribers.remove(request.user.id)
                    subscribed = False
                else:
                    subscribed = False
                return response.Response({
                    'subscribed': subscribed,
                })

        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

class GroupBlacklistSubscriberView(views.APIView):
    permission_classes = [IsGroupAuthor]

    def get(self, request, username, user_id):
        try:
            user = User.objects.get(id=user_id)
            group = Group.objects.select_related('author').get(
                author__username=username
            )
            blacklisted = False
            if group.blacklists.filter(pk=user.id).exists():
                blacklisted = True
            return response.Response({
                'blacklisted': blacklisted,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def post(self, request, username, user_id):
        try:
            group = Group.objects.select_related('author').get(
                author__username=username
            )
            if group.author.id != user_id:
                blacklisted = False
                if group.blacklists.filter(pk=user_id).exists():
                    blacklisted = True
                else:
                    group.subscribers.remove(user_id)
                    group.blacklists.add(user_id)
                    blacklisted = True
                return response.Response({
                    'blacklisted': blacklisted,
                })
            else:
                return response.Response({"detail": "You are author. You can not blacklist yourself."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def delete(self, request, username, user_id):
        try:
            group = Group.objects.select_related('author').get(
                author__username=username
            )

            blacklisted = True
            if group.blacklists.filter(pk=user_id).exists():
                group.blacklists.remove(user_id)
                blacklisted = False
            else:
                blacklisted = False
            return response.Response({
                'blacklisted': blacklisted,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupSubscribersView(generics.ListAPIView):
    permission_classes = [IsNotBlacklisted]
    serializer_class = GroupSubscribersSerializer
    pagination_class = PazeSizePagination

    def get_queryset(self):
        try:
            group = Group.objects.select_related('author').get(
                author__username=self.kwargs['username']
            )
            return group.subscribers.all()
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class GroupBlacklistView(generics.ListAPIView):
    permission_classes = [IsGroupAuthor]
    serializer_class = GroupBlacklistsSerializer
    pagination_class = PazeSizePagination

    def get_queryset(self):
        try:
            group = Group.objects.select_related('author').get(
                author__username=self.kwargs['username']
            )
            return group.blacklists.all()
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)
