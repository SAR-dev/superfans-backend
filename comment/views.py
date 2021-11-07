from rest_framework.views import APIView
from .models import Comment
from activity.models import Activity
from group.models import Group
from post.models import Post
from .serializers import CommentListSerializer, CommentCreateSerializer, CommentChildCreateSerializer, CommentRetriveSerializer, CommentUpdateSerializer
from base_serializers import PostSerializer
from utils.paginations import PazeSizePagination
from rest_framework import generics, views, response, permissions, serializers
from rest_framework.exceptions import NotFound
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.core.serializers import serialize
from django_filters import rest_framework as filters


class IsCommentAuthor(permissions.BasePermission):
    message = 'You do not have enough permission!'

    def has_permission(self, request, view):
        try:
            comment = Comment.objects.get(pk=view.kwargs.get('pk'))
            return comment.author.id == request.user.id
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class IsPostGroupSubscriber(permissions.BasePermission):
    message = 'You do not have enough permission!'

    def has_permission(self, request, view):
        try:
            post = Post.cancomment.get(pk=view.kwargs.get('pk'))
            return post.group.subscribers.filter(pk=request.user.id).exists()
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class CanCommentAndVote(permissions.BasePermission):
    message = 'You do not have enough permission!'

    def has_permission(self, request, view):
        try:
            comment = Comment.objects.get(pk=view.kwargs.get('pk'))
            return comment.post.can_comment and comment.post.group.subscribers.filter(pk=request.user.id).exists()
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

class CanRaiseHands(permissions.BasePermission):
    message = 'You do not have enough permission!'

    def has_permission(self, request, view):
        try:
            comment = Comment.objects.get(pk=view.kwargs.get('pk'))
            return comment.post.can_comment and comment.post.group.subscribers.filter(pk=request.user.id).exists() and comment.parent is None
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class CommentCreateView(generics.CreateAPIView):
    def perform_create(self, serializer):
        try:
            post = Post.cancomment.get(id=self.kwargs["pk"])
            serializer.save(author=self.request.user,
                            post=post, is_active=True)
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    permission_classes = [IsPostGroupSubscriber]
    serializer_class = CommentCreateSerializer
    queryset = Comment.objects.all()


class CommentChildCreateView(generics.CreateAPIView):
    def perform_create(self, serializer):
        try:
            post = Post.cancomment.get(id=self.kwargs["pk"])
            parent = Comment.active.get(id=self.kwargs["parent"])
            if parent.post.id == post.id and parent.parent is None:
                serializer.save(author=self.request.user,
                                post=post, parent=parent, is_active=True)
            else:
                raise serializers.ValidationError("Invalid parent comment")
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    permission_classes = [IsPostGroupSubscriber]
    serializer_class = CommentCreateSerializer
    queryset = Comment.objects.all()


class CommentListView(generics.ListAPIView):
    # permission_classes = [IsPostGroupSubscriber]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommentListSerializer

    def get_queryset(self):
        try:
            return Comment.objects.select_related('post').filter(post__id=self.kwargs["pk"])
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class CommentRetriveView(generics.RetrieveAPIView):
    permission_classes = [CanCommentAndVote]
    serializer_class = CommentRetriveSerializer
    queryset = Comment.objects.all()
    
class CommentPostRetriveView(generics.RetrieveAPIView):
    permission_classes = [CanCommentAndVote]
    serializer_class = PostSerializer
    
    def get_object(self):
        try:
            comment = Comment.objects.get(pk=self.kwargs['pk'])
            post = Post.published.get(pk=comment.post.id)
            if post.status == "published":
                return post
            else:
                if post.author.id== self.request.user.id:
                    return post
                else:
                    raise NotFound(detail="Error 404, Not Found!", code=404)
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)


class CommentUpdateView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsCommentAuthor]
    serializer_class = CommentUpdateSerializer
    queryset = Comment.active.all()


class CommentVoteView(views.APIView):
    permission_classes = [CanCommentAndVote]

    def get(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            auth_user = self.request.user
            return response.Response({
                'count': comment.votes.count_up(),
                'upvoted': comment.votes.exists_up(auth_user.id),
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def post(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            auth_user = self.request.user
            comment.votes.up(auth_user.id)
            # comment clapped
            Activity.objects.create(target=comment.id, post=comment.post.id, group_id=comment.post.group.id,
                                    sender_id=request.user.id, reciever_id=comment.author.id, target_type="comment", verb="clapped")
            return response.Response({
                'count': comment.votes.count_up(),
                'upvoted': True,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def delete(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            auth_user = self.request.user
            comment.votes.delete(auth_user.id)
            # comment clapped
            Activity.objects.filter(target=comment.id, post=comment.post.id, group_id=comment.post.group.id,
                                    sender_id=request.user.id, reciever_id=comment.author.id, target_type="comment", verb="clapped").delete()
            return response.Response({
                'count': comment.votes.count_up(),
                'upvoted': False,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

class CommentHandsRaiseView(views.APIView):
    permission_classes = [CanRaiseHands]

    def get(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            raised = request.user in comment.hands.all()
            count = comment.hands.count()
            return response.Response({
                'raised': raised,
                'count': count,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def post(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            if request.user not in comment.hands.all():
                comment.hands.add(request.user)
                
            count = comment.hands.count()
            return response.Response({
                'raised': True,
                'count': count,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def delete(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            if request.user in comment.hands.all():
                comment.hands.remove(request.user)
                
            count = comment.hands.count()
            return response.Response({
                'raised': False,
                'count': count,
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)
        
class CommentPinnedView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            postId = comment.post.id
            post = Post.objects.get(pk=postId)
            pinned_comment = post.pinned_comment
            return response.Response({
                'pinned_comment': pinned_comment
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def post(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            postId = comment.post.id
            post = Post.objects.get(pk=postId)
            if (post.group.author.id == request.user.id or post.author.id == request.user.id) and comment.parent == None:
                post.pinned_comment = comment.id
                post.save()
            pinned_comment = post.pinned_comment
            return response.Response({
                'pinned_comment': pinned_comment
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)

    def delete(self, request, pk):
        try:
            comment = Comment.active.get(pk=pk)
            postId = comment.post.id
            post = Post.objects.get(pk=postId)
            if post.group.author.id == request.user.id or post.author.id == request.user.id:
                post.pinned_comment = None
                post.save()
            pinned_comment = post.pinned_comment
            return response.Response({
                'pinned_comment': pinned_comment
            })
        except ObjectDoesNotExist:
            raise NotFound(detail="Error 404, Not Found!", code=404)