from django.contrib.auth.models import AbstractUser
from django.db import models


class Otdel(models.Model):
    """Отдел учреждения"""
    nazvanie = models.CharField('Название отдела', max_length=150, unique=True)
    opisanie = models.TextField('Описание', blank=True)
    data_sozdaniya = models.DateTimeField('Дата создания', auto_now_add=True)

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['nazvanie']

    def __str__(self):
        return self.nazvanie


class Polzovatel(AbstractUser):
    """Кастомная модель пользователя с ролью и привязкой к отделу"""

    ROL_RUKOVODITEL = 'rukovoditel'
    ROL_SOTRUDNIK = 'sotrudnik'

    ROLI = [
        (ROL_RUKOVODITEL, 'Руководитель отдела'),
        (ROL_SOTRUDNIK, 'Сотрудник'),
    ]

    rol = models.CharField('Роль', max_length=20, choices=ROLI, default=ROL_SOTRUDNIK)
    otdel = models.ForeignKey(
        Otdel,
        verbose_name='Отдел',
        related_name='sotrudniki',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    dolzhnost = models.CharField('Должность', max_length=150, blank=True)
    telefon = models.CharField('Телефон', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'

    def is_rukovoditel(self):
        return self.rol == self.ROL_RUKOVODITEL

    def is_sotrudnik(self):
        return self.rol == self.ROL_SOTRUDNIK