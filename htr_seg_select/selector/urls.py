from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('segment_list', views.segment_list, name='segment-list'),
    path('pick/<str:folder_name>', views.segment_pick, name='segment-pick'),
    path('compare/<str:doc_name>/<str:page_name>', views.segment_compare, name='segment-compare'),
    path('recreate/<str:doc_name>/<str:page_name>', views.segment_recreate, name='segment-recreate'),
    path('finalize/<str:doc_name>/<str:page_name>', views.segment_finalize, name='segment-finalize'),
    path('image', views.pdf2image, name='image'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)