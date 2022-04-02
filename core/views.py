from re import A
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import PostForm, ProfileSettingsForm, ProfileUpdateForm
from .models import Post, Profile, Hashtag, Notificaton, FriendRequest, UserFollowing
from django.views.generic import UpdateView, DeleteView
from django.utils.translation import gettext_lazy as _
from django.http import Http404, JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
import requests
import json
from django.db.models import Q
from itertools import chain
from django.views.generic import DetailView, DeleteView, TemplateView


def home(request):
    if request.user.is_authenticated:
        form = PostForm(request.POST)
        if request.method == "POST" and form.is_valid():
            f = form.instance
            f.user = request.user
            f.save()
            messages.success(request, _("Post created successfully"))
        ctx = {
            "posts": Post.objects.filter(Q(user=request.user) | Q(user__profile__only_friends=False) | Q(user__profile__only_friends=True, user__in=request.user.profile.friends.all())).order_by("-date_added"),
            "form": form,
            "profile": request.user.profile,
            "last_hashtags": Hashtag.objects.all().order_by("-date_added")[:5],
        }
        return render(request, "home.html", ctx)
    ctx = {"posts": Post.objects.all().order_by("-date_added"), "last_hashtags": Hashtag.objects.all().order_by("-date_added")[:5]}
    return render(request, "home.html", ctx)


class PostDetailView(DetailView):
    model = Post
    template_name = "post-detail.html"
    context_object_name = "post"


class IsOwnerOnlyMixin:
    def has_object_permission(self, request, obj):
        return super().has_object_permission(request, obj) and obj.user == request.user


class PostDeleteView(IsOwnerOnlyMixin, DeleteView):
    model = Post
    success_url = "/"


class PostUpdateView(IsOwnerOnlyMixin, UpdateView):
    model = Post
    fields = [
        "content",
    ]
    template_name = "post_update.html"
    success_url = "/"


def register(request):
    if not request.user.is_authenticated:
        if request.method == "POST":
            form = UserCreationForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, f"Account created successfully {request.user.username}")

                return redirect("login")

        else:
            form = UserCreationForm()
        return render(request, "users/register.html", {"form": form})
    else:
        return redirect("home")


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/profile.html"

    def post(self, request, *args, **kwargs):
        email_form = ProfileUpdateForm(request.POST or None, instance=Profile.objects.get(user=request.user))

        if "delete_email" in request.POST:
            a = Profile.objects.get(user=request.user)
            a.mail = None
            a.save()
            messages.success(request, _("Mail is deleted successfully"))
        if "save_email" in request.POST:
            if email_form.is_valid():
                f = email_form.instance
                f.user = request.user
                f.save()
                messages.success(request, _("Mail is updated successfully"))
        if request.POST.get("operation") == "add_pp":
            a = Profile.objects.get(user=request.user)
            a.image = request.FILES.get("image")
            print(request.FILES.get("image").name)
            a.save()
            messages.success(request, _("Profile picture is updated successfully"))
            response = {"mesage": "pic is updated"}
            return JsonResponse(response)

        super().get(request, email_form=email_form, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "email_form": kwargs.get("email_form", ProfileUpdateForm())}


class UserProfileView(LoginRequiredMixin, TemplateView):
    template_name = "users/user_profile.html"

    def dispatch(self, request, username, *args, **kwargs):
        if request.user.username == username:
            return redirect("profile")
        self.aforementioned_user = get_object_or_404(User, username=username)
        self.profile = get_object_or_404(Profile, user=self.aforementioned_user)  # The profile that wants to be followed

        self.flw_btn = UserFollowing.objects.filter(from_user=request.user, to_user=self.aforementioned_user).exists() and "Following" or "Follow"

        self.is_friend = self.profile.friends.filter(id=request.user.id).exists()
        return super().dispatch(request, username, *args, **kwargs)

    def private_ctx(self):
        if not self.profile.friends.filter(id=self.request.user.id):  # Arkadaş değilse
            req_btn = FriendRequest.objects.filter(from_user=self.request.user, to_user=self.profile).exists() and "Unrequest" or "Send Request"

            already_friend = False
            friend_btn = "Add Friend"
        else:  # Arkaşsa
            friend_btn = "Friend ✔️"
            already_friend = True
            req_btn = "Friend ✔️"
        return {
            "user": self.aforementioned_user,
            "follow_btn_text": self.flw_btn,
            "req_btn": req_btn,
            "already_friend": already_friend,
            "friend_btn": friend_btn,
            "is_friend": self.is_friend,
        }

    def public_ctx(self):
        return {
            "user": self.aforementioned_user,
            "follow_btn_text": self.flw_btn,
            "friend_btn": self.profile.friends.filter(id=self.request.user.id).exists() and "Friend ✔️" or "Add Friend",
            "is_friend": self.is_friend,
        }

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **(self.profile.is_private and self.private_ctx() or self.public_ctx())}


def read_the_notifications(request):
    profile = Profile.objects.get(user=request.user)
    if request.method == "POST":
        if Notificaton.objects.filter(to_user=profile, is_read=False).exists():
            notif = Notificaton.objects.filter(to_user=profile, is_read=False)
            notif.update(is_read=True)
            there_are_notifications = True
            info = _("Notifications are read")
        else:
            there_are_notifications = False
            info = _("No notifications")
    ctx = {"info": info, "there_are_notifications": there_are_notifications}
    return JsonResponse(ctx)


def search_results(request):
    if request.method == "GET":
        query = request.GET.get("q")
        if query:
            posts = Post.objects.filter(Q(content__icontains=query))
            hashtags = Hashtag.objects.filter(name__icontains=query)
            users = Profile.objects.filter(user__username__icontains=query)
            search_all = chain(posts, hashtags, users)
            return render(request, "search_results.html", {"search_all": search_all, "q": query})
        return redirect("homme")
    return redirect("profile")


def delete_all_notifications(request):
    Notificaton.objects.filter(to_user=request.user.profile).delete()
    return redirect("notifications_list")


def read_the_friend_notifications(request):
    if Notificaton.objects.filter(to_user=request.user.profile, notification_type="friend_request", is_read=False).update(is_read=True):
        there_are_friend_notifications = True
        info = _("Notifications are read")
    else:
        there_are_friend_notifications = False
        info = _("No notifications")
    ctx = {"info": info, "there_are_friend_notifications": there_are_friend_notifications}
    return JsonResponse(ctx)


def read_all_notifications(request):
    Notificaton.objects.filter(to_user=request.user.profile, is_read=False).update(is_read=True)


def notifications_list(request):
    read_all_notifications(request)
    return render(request, "notifications.html", {"notifs": Notificaton.objects.filter(to_user=request.user.profile).order_by("-date_added") or "None"})


# For Private Profiles
def send_friend_request(request):
    if request.method == "POST":
        username = request.POST.get("username", None)
        profile = get_object_or_404(Profile, user__username=username)  # The profile that wants to be friended
        if FriendRequest.objects.filter(from_user=request.user, to_user=profile).exists():  # already followed the profile
            req = FriendRequest.objects.get(from_user=request.user, to_user=profile)  # remove user from followings
            req.delete()
            notif = Notificaton.objects.get(from_user=request.user, to_user=profile, notification_type="friend_request")
            notif.delete()
            status = "unrequested"
            print("unrequested")
        else:
            req = FriendRequest(from_user=request.user, to_user=profile)
            req.save()
            status = "requested"
            Notificaton.objects.get_or_create(from_user=request.user, to_user=profile, notification_type="friend_request")
            print("requested")

    ctx = {"status": status}
    return JsonResponse(ctx)


# Adds to friends if user is not private, otherwise works inside "accept_friend_request" functions
def add_friend(request):
    if request.method == "POST":
        username = request.POST.get("username", None)
        that_user = get_object_or_404(User, username=username)  # The profile that wants to be friended
        request_profile = get_object_or_404(Profile, user=request.user)  # The profile that wants to be friended

        if request_profile.friends.filter(id=that_user.id).exists():  # already friend the profile
            # remove user from friends
            request_profile.friends.remove(that_user)

            that_userprofile = that_user.profile
            that_userprofile.friends.remove(request.user)

            if Notificaton.objects.filter(from_user=request.user, to_user=that_userprofile, notification_type="friend_now").exists():
                notif = Notificaton.objects.get(from_user=request.user, to_user=that_userprofile, notification_type="friend_now")
                notif.delete()
            elif Notificaton.objects.filter(from_user=that_user, to_user=request_profile, notification_type="friend_now"):
                notif2 = Notificaton.objects.get(from_user=that_user, to_user=request_profile, notification_type="friend_now")
                notif2.delete()
            status = False
            print("removed")
        else:
            # add user to friends
            request_profile.friends.add(that_user)
            that_userprofile = that_user.profile
            that_userprofile.friends.add(request.user)

            status = True
            Notificaton.objects.get_or_create(from_user=request.user, to_user=that_userprofile, notification_type="friend_now")
            Notificaton.objects.get_or_create(from_user=that_user, to_user=request_profile, notification_type="friend_now")
        # For Accept Function..
        if FriendRequest.objects.filter(from_user=that_user, to_user=request.user.profile).exists():
            req = FriendRequest.objects.get(from_user=that_user, to_user=request.user.profile)
            req.delete()
            notif = Notificaton.objects.get(from_user=that_user, to_user=request.user.profile, notification_type="friend_request")
            notif.delete()
            print("ok")

    ctx = {"status": status}
    return JsonResponse(ctx)


def accept_friend_request(request):
    if request.method == "POST":
        return add_friend(request)
    else:
        return JsonResponse({"status": False})


def delete_friend_request(request):
    if request.method == "POST":
        username = request.POST.get("username", None)
        that_user = get_object_or_404(User, username=username)
        req = FriendRequest.objects.get(from_user=that_user, to_user=request.user.profile).delete()
        Notificaton.objects.get(from_user=that_user, to_user=request.user.profile, notification_type="friend_request").delete()
        return JsonResponse({"status": bool(req)})


def followings_list(request):
    followings_list = UserFollowing.objects.filter(from_user=request.user)
    is_friend = False
    ctx = {"list": followings_list, "is_friend": is_friend}
    return render(request, "users/followings_list.html", ctx)


def friends_list(request):
    friends_list = request.user.profile.friends.all()
    is_friend = True
    ctx = {"list": friends_list, "is_friend": is_friend}
    return render(request, "users/friends.html", ctx)


def settings(request):
    form = ProfileSettingsForm(request.POST or None, instance=request.user.profile)
    if form.is_valid():
        form.save()
    return render(request, "users/settings.html", {"form": form})


def logout(request):
    if request.user in request.session:
        del request.session["user_"]
    auth.logout(request)
    return render(request, "users/logout.html")


def hashtag(request, stra):
    posts = Post.objects.filter(hashtags__name=stra)
    related_posts = Post.objects.filter(hashtags__name__icontains=stra).exclude(hashtags__name=stra)
    if not Post.objects.filter(hashtags__name=stra):
        return redirect("home")
    else:
        ctx = {"hash_name": stra, "related_posts": related_posts, "posts": posts}
        return render(request, "hashtag.html", ctx)
