from django.contrib import admin

from .models import Course, CourseCategory, Module


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'active')
    list_editable = ('display_order', 'active')
    list_filter = ('active',)
    search_fields = ('name',)
    ordering = ('display_order', 'name')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'course_count')
    list_filter = ('active',)
    search_fields = ('name', 'description')
    ordering = ('name',)

    @admin.display(description='courses', ordering='courses__count')
    def course_count(self, obj: Module) -> int:
        return obj.courses.count()


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'title',
        'category',
        'credit_points',
        'active',
    )
    list_filter = ('active', 'category', 'modules')
    search_fields = ('code', 'title', 'description', 'notes')
    ordering = ('code',)
    autocomplete_fields = ('category',)
    filter_horizontal = ('modules',)
    list_select_related = ('category',)
    fieldsets = (
        (None, {
            'fields': ('code', 'title', 'description', 'active'),
        }),
        ('Classification', {
            'fields': ('category', 'modules'),
        }),
        ('Credits', {
            'fields': ('credit_points',),
        }),
        ('Notes', {
            'fields': ('notes',),
        }),
    )
