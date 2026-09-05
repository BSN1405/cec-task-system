from django.contrib import admin
from .models import Zadacha, Kommentarii, Otsenka


class KommentariiInline(admin.TabularInline):
    model = Kommentarii
    extra = 0
    readonly_fields = ('avtor', 'tekst', 'data_sozdaniya')
    can_delete = False


class OtsenkaInline(admin.StackedInline):
    model = Otsenka
    extra = 0


@admin.register(Zadacha)
class ZadachaAdmin(admin.ModelAdmin):
    list_display = ('zagolovok', 'otdel', 'postavil', 'ispolnitel', 'prioritet', 'status', 'srok_vypolneniya')
    list_filter = ('status', 'prioritet', 'otdel')
    search_fields = ('zagolovok', 'opisanie')
    inlines = [KommentariiInline, OtsenkaInline]


@admin.register(Kommentarii)
class KommentariiAdmin(admin.ModelAdmin):
    list_display = ('zadacha', 'avtor', 'data_sozdaniya')


@admin.register(Otsenka)
class OtsenkaAdmin(admin.ModelAdmin):
    list_display = ('zadacha', 'ball', 'otsenil', 'data_otsenki')