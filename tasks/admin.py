from django.contrib import admin
from .models import Zadacha, Kommentarii, Vlozhenie, Uvedomlenie, IstoriyaStatusov, IstoriyaNaznacheniya


class KommentariiInline(admin.TabularInline):
    model = Kommentarii
    extra = 0
    readonly_fields = ('avtor', 'tekst', 'data_sozdaniya')
    can_delete = False


class VlozhenieInline(admin.TabularInline):
    model = Vlozhenie
    extra = 0
    readonly_fields = ('zagruzil', 'data_zagruzki')

class IstoriyaInline(admin.TabularInline):
    model = IstoriyaStatusov
    extra = 0
    readonly_fields = ('staryi_status', 'novyi_status', 'izmenil', 'data_izmeneniya')
    can_delete = False

class IstoriyaNaznacheniyaInline(admin.TabularInline):
    model = IstoriyaNaznacheniya
    extra = 0
    readonly_fields = ('staryi_ispolnitel', 'novyi_ispolnitel', 'izmenil', 'prichina', 'data_izmeneniya')
    can_delete = False

@admin.register(Zadacha)
class ZadachaAdmin(admin.ModelAdmin):
    list_display = ('zagolovok', 'otdel', 'postavil', 'ispolnitel', 'prioritet', 'status', 'srok_vypolneniya')
    list_filter = ('status', 'prioritet', 'otdel')
    search_fields = ('zagolovok', 'opisanie')
    inlines = [KommentariiInline, VlozhenieInline, IstoriyaInline, IstoriyaNaznacheniyaInline]


@admin.register(Kommentarii)
class KommentariiAdmin(admin.ModelAdmin):
    list_display = ('zadacha', 'avtor', 'data_sozdaniya')


@admin.register(Uvedomlenie)
class UvedomlenieAdmin(admin.ModelAdmin):
    list_display = ('poluchatel', 'tip', 'zadacha', 'prochitano', 'data_sozdaniya')
    list_filter = ('tip', 'prochitano')

