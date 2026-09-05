from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Zadacha(models.Model):
    """Служебное поручение / задача сотруднику"""

    PRIORITET_NIZKII = 'nizkii'
    PRIORITET_SREDNII = 'srednii'
    PRIORITET_VYSOKII = 'vysokii'

    PRIORITETY = [
        (PRIORITET_NIZKII, 'Низкий'),
        (PRIORITET_SREDNII, 'Средний'),
        (PRIORITET_VYSOKII, 'Высокий'),
    ]

    STATUS_NOVAYA = 'novaya'
    STATUS_PRINYATA = 'prinyata'
    STATUS_V_RABOTE = 'v_rabote'
    STATUS_NA_PROVERKE = 'na_proverke'
    STATUS_NA_DORABOTKE = 'na_dorabotke'
    STATUS_VYPOLNENA = 'vypolnena'

    STATUSY = [
        (STATUS_NOVAYA, 'Новая'),
        (STATUS_PRINYATA, 'Принята к исполнению'),
        (STATUS_V_RABOTE, 'В работе'),
        (STATUS_NA_PROVERKE, 'На проверке'),
        (STATUS_NA_DORABOTKE, 'Отправлена на доработку'),
        (STATUS_VYPOLNENA, 'Выполнена'),
    ]

    zagolovok = models.CharField('Заголовок', max_length=250)
    opisanie = models.TextField('Описание поручения')

    otdel = models.ForeignKey(
        'accounts.Otdel',
        verbose_name='Отдел',
        related_name='zadachi',
        on_delete=models.CASCADE,
    )
    postavil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Поставил задачу (руководитель)',
        related_name='postavlennye_zadachi',
        on_delete=models.PROTECT,
    )
    ispolnitel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Исполнитель',
        related_name='naznachennye_zadachi',
        on_delete=models.PROTECT,
    )

    prioritet = models.CharField('Приоритет', max_length=20, choices=PRIORITETY, default=PRIORITET_SREDNII)
    status = models.CharField('Статус', max_length=20, choices=STATUSY, default=STATUS_NOVAYA)

    srok_vypolneniya = models.DateField('Срок выполнения')
    data_sozdaniya = models.DateTimeField('Дата постановки', auto_now_add=True)
    data_obnovleniya = models.DateTimeField('Дата обновления', auto_now=True)
    data_vypolneniya = models.DateTimeField('Дата отправки на проверку', null=True, blank=True)
    data_podtverzhdeniya = models.DateTimeField('Дата подтверждения', null=True, blank=True)

    class Meta:
        verbose_name = 'Служебное поручение'
        verbose_name_plural = 'Служебные поручения'
        ordering = ['-data_sozdaniya']

    def __str__(self):
        return f'{self.zagolovok} ({self.get_status_display()})'

    def clean(self):
        # Руководитель может ставить задачи только сотрудникам своего отдела
        if self.postavil_id and self.ispolnitel_id:
            if self.postavil.rol != self.postavil.ROL_RUKOVODITEL:
                raise ValidationError('Ставить задачи может только руководитель отдела.')
            if self.ispolnitel.otdel_id != self.postavil.otdel_id:
                raise ValidationError('Исполнитель должен быть сотрудником того же отдела, что и руководитель.')

    def prosrochena(self):
        """Просрочена ли задача"""
        return self.status != self.STATUS_VYPOLNENA and self.srok_vypolneniya < timezone.now().date()

    # --- переходы статуса ---

    def prinyat_k_ispolneniyu(self):
        self.status = self.STATUS_PRINYATA
        self.save(update_fields=['status', 'data_obnovleniya'])

    def nachat_rabotu(self):
        self.status = self.STATUS_V_RABOTE
        self.save(update_fields=['status', 'data_obnovleniya'])

    def otpravit_na_proverku(self):
        self.status = self.STATUS_NA_PROVERKE
        self.data_vypolneniya = timezone.now()
        self.save(update_fields=['status', 'data_vypolneniya', 'data_obnovleniya'])

    def podtverdit_vypolnenie(self):
        self.status = self.STATUS_VYPOLNENA
        self.data_podtverzhdeniya = timezone.now()
        self.save(update_fields=['status', 'data_podtverzhdeniya', 'data_obnovleniya'])

    def otpravit_na_dorabotku(self):
        self.status = self.STATUS_NA_DORABOTKE
        self.save(update_fields=['status', 'data_obnovleniya'])


class Kommentarii(models.Model):
    """Комментарий к задаче (переписка руководителя и сотрудника по ходу работы)"""

    zadacha = models.ForeignKey(
        Zadacha,
        verbose_name='Задача',
        related_name='kommentarii',
        on_delete=models.CASCADE,
    )
    avtor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Автор комментария',
        on_delete=models.CASCADE,
    )
    tekst = models.TextField('Текст комментария')
    data_sozdaniya = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['data_sozdaniya']

    def __str__(self):
        return f'Комментарий от {self.avtor} к задаче "{self.zadacha.zagolovok}"'


class Otsenka(models.Model):
    """Оценка руководителем выполненной задачи (0-10 баллов)"""

    zadacha = models.OneToOneField(
        Zadacha,
        verbose_name='Задача',
        related_name='otsenka',
        on_delete=models.CASCADE,
    )
    ball = models.PositiveSmallIntegerField(
        'Балл',
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    kommentarii_rukovoditelya = models.TextField('Комментарий руководителя', blank=True)
    otsenil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Оценил',
        on_delete=models.PROTECT,
    )
    data_otsenki = models.DateTimeField('Дата оценки', auto_now_add=True)

    class Meta:
        verbose_name = 'Оценка'
        verbose_name_plural = 'Оценки'

    def __str__(self):
        return f'Оценка {self.ball}/10 за "{self.zadacha.zagolovok}"'