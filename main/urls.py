from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login, name="login"),
    path("register", views.register, name="register"),
    path("activate_email", views.register, name="activate-email"),
    path("activate/<uidb64>/<token>", views.activate, name="activate"),
    path("logout", views.logout, name="logout"),
    path("forgot-password", views.forgot_password, name="forgot-password"),
    path("info/<email>", views.info, name="info"),
    path("change-password", views.change_password, name="change-password"),
    path("search/<page>", views.search, name="search"),
    path("history/<email>", views.history, name="history"),
    path("create-auction", views.create_auction, name="create-auction"),
    path("auction/<id>", views.auction, name="auction"),
    path("join-auction", views.join_auction, name="join-auction"),
    path("error", views.error, name="error"),
    path("add-card", views.add_card, name="add-card"),
    path("edit-auction/<id>", views.edit_auction, name="edit-auction")
]