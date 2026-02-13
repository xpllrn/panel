from django.urls import path

from . import views

app_name = "admin_portal"

urlpatterns = [
    path("home/", views.home_view, name="home"),
    path("members/", views.members_view, name="members"),
    path("profile/", views.profile_view, name="profile"),
]
