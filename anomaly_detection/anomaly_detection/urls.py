# anomaly_detection/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/home/'), name='root'),  # Redirect root to signup
    path('', include('accounts.urls')),

]