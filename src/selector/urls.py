from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('segmenter/<int:doc_id>/', views.document_segmenter, name='document-segmenter'),
    path('segment_list', views.segment_list, name='segment-list'),
    path('compare/<int:id>', views.segment_compare, name='segment-compare'),
    path('recreate/<int:id>', views.segment_recreate, name='segment-recreate'),
    path('finalize/<int:id>', views.segment_finalize, name='segment-finalize'),
    path('finalize_admin/<int:id>', views.segment_finalize_admin, name='segment-finalize-admin'),
    path('image', views.pdf2image, name='image'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)