from django.contrib import admin
from .models import Tag, Problem, TestCase


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color']
    prepopulated_fields = {'slug': ('name',)}


class TestCaseInline(admin.TabularInline):
    # shows test cases INSIDE the problem page — very convenient
    model   = TestCase
    extra   = 2           # show 2 blank rows by default
    fields  = ['order', 'is_sample', 'is_active', 'input_data', 'expected_output']
    ordering = ['order']


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display  = ['title', 'difficulty', 'time_limit_seconds',
                     'memory_limit_mb', 'is_active', 'created_at']
    list_filter   = ['difficulty', 'is_active', 'tags']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal   = ['tags']    # nice tag picker UI
    readonly_fields     = ['created_at']
    inlines = [TestCaseInline]        # test cases on same page as problem


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display  = ['problem', 'order', 'is_sample', 'is_active']
    list_filter   = ['is_sample', 'is_active', 'problem']
    ordering      = ['problem', 'order']