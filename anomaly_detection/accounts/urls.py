# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('upload/', views.upload_file, name='upload_file'),
    path('share/<int:file_id>/', views.share_file, name='share_file'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
]