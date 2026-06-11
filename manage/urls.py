from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'manage'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('texts/<slug:key>/edit/', views.SiteTextUpdateView.as_view(),
         name='site_text_edit'),

    path('categories/add/', views.CategoryCreateView.as_view(),
         name='category_add'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(),
         name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(),
         name='category_delete'),
    path('categories/bulk-delete/', views.CategoryBulkDeleteView.as_view(),
         name='category_bulk_delete'),

    path('modules/add/', views.ModuleCreateView.as_view(),
         name='module_add'),
    path('modules/<int:pk>/edit/', views.ModuleUpdateView.as_view(),
         name='module_edit'),
    path('modules/<int:pk>/delete/', views.ModuleDeleteView.as_view(),
         name='module_delete'),
    path('modules/bulk-delete/', views.ModuleBulkDeleteView.as_view(),
         name='module_bulk_delete'),

    path('courses/list/', views.CourseListPartialView.as_view(),
         name='course_list'),
    path('courses/add/', views.CourseCreateView.as_view(),
         name='course_add'),
    path('courses/<int:pk>/edit/', views.CourseUpdateView.as_view(),
         name='course_edit'),
    path('courses/<int:pk>/delete/', views.CourseDeleteView.as_view(),
         name='course_delete'),
    path('courses/bulk-delete/', views.CourseBulkDeleteView.as_view(),
         name='course_bulk_delete'),

    path('specializations/add/', views.SpecializationCreateView.as_view(),
         name='specialization_add'),
    path('specializations/<int:pk>/edit/',
         views.SpecializationUpdateView.as_view(),
         name='specialization_edit'),
    path('specializations/<int:pk>/delete/',
         views.SpecializationDeleteView.as_view(),
         name='specialization_delete'),
    path('specializations/bulk-delete/',
         views.SpecializationBulkDeleteView.as_view(),
         name='specialization_bulk_delete'),
]
