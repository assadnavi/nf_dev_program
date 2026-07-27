from django.urls import path

from . import views

urlpatterns = [
    path('', views.root, name='root'),

    # Admin dashboard
    path('dashboard/', views.program_list, name='program_list'),
    path('dashboard/programs/new/', views.program_create, name='program_create'),
    path('dashboard/programs/<int:program_id>/', views.program_detail, name='program_detail'),
    path('dashboard/applications/<int:application_id>/', views.application_detail, name='application_detail'),
    path(
        'dashboard/applications/<int:application_id>/documents/<str:field>/',
        views.application_document,
        name='application_document',
    ),

    # Public applicant-facing pages
    path('apply/<int:program_id>/', views.apply, name='apply'),
    path('application/<str:token>/', views.application_status, name='application_status'),
]
