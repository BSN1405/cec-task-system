from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Polzovatel, Otdel


@admin.register(Otdel)
class OtdelAdmin(admin.ModelAdmin):
    list_display = ('nazvanie', 'data_sozdaniya')
    search_fields = ('nazvanie',)


@admin.register(Polzovatel)
class PolzovatelAdmin(UserAdmin):
    list_display = ('username', 'get_full_name', 'rol', 'otdel', 'dolzhnost', 'is_active')
    list_filter = ('rol', 'otdel', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')

    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('rol', 'otdel', 'dolzhnost', 'telefon')
        }),
    )