from django.conf import settings
from django.core.exceptions import ValidationError
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
        if self.postavil_id and self.ispolnitel_id:
            if self.postavil.rol != self.postavil.ROL_RUKOVODITEL:
                raise ValidationError('Ставить задачи может только руководитель отдела.')
            if self.ispolnitel.otdel_id != self.postavil.otdel_id:
                raise ValidationError('Исполнитель должен быть сотрудником того же отдела, что и руководитель.')

    def prosrochena(self):
        return self.status != self.STATUS_VYPOLNENA and self.srok_vypolneniya < timezone.now().date()

    # --- переходы статуса ---

    def _zapisat_istoriyu(self, staryi_status, izmenil):
        IstoriyaStatusov.objects.create(
            zadacha=self,
            staryi_status=staryi_status,
            novyi_status=self.status,
            izmenil=izmenil,
        )

    def sozdana(self, izmenil):
        """Вызывается один раз сразу после создания задачи"""
        self._zapisat_istoriyu('', izmenil)

    def prinyat_k_ispolneniyu(self, izmenil):
        staryi = self.status
        self.status = self.STATUS_PRINYATA
        self.save(update_fields=['status', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi, izmenil)

    def nachat_rabotu(self, izmenil):
        staryi = self.status
        self.status = self.STATUS_V_RABOTE
        self.save(update_fields=['status', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi, izmenil)

    def otpravit_na_proverku(self, izmenil):
        staryi = self.status
        self.status = self.STATUS_NA_PROVERKE
        self.data_vypolneniya = timezone.now()
        self.save(update_fields=['status', 'data_vypolneniya', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi, izmenil)

    def podtverdit_vypolnenie(self, izmenil):
        staryi = self.status
        self.status = self.STATUS_VYPOLNENA
        self.data_podtverzhdeniya = timezone.now()
        self.save(update_fields=['status', 'data_podtverzhdeniya', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi, izmenil)

    def otpravit_na_dorabotku(self, izmenil):
        staryi = self.status
        self.status = self.STATUS_NA_DORABOTKE
        self.save(update_fields=['status', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi, izmenil)

    def pereznachit(self, novyi_ispolnitel, izmenil, prichina=''):
        """Передаёт задачу другому сотруднику того же отдела, сбрасывая статус в 'Новая'"""
        if self.status == self.STATUS_VYPOLNENA:
            raise ValidationError('Нельзя переназначить уже выполненное поручение.')
        if novyi_ispolnitel.otdel_id != self.otdel_id or novyi_ispolnitel.rol != novyi_ispolnitel.ROL_SOTRUDNIK:
            raise ValidationError('Новый исполнитель должен быть сотрудником того же отдела.')
        if novyi_ispolnitel.id == self.ispolnitel_id:
            raise ValidationError('Этот сотрудник уже является исполнителем данной задачи.')

        staryi_ispolnitel = self.ispolnitel
        staryi_status = self.status

        IstoriyaNaznacheniya.objects.create(
            zadacha=self,
            staryi_ispolnitel=staryi_ispolnitel,
            novyi_ispolnitel=novyi_ispolnitel,
            izmenil=izmenil,
            prichina=prichina,
        )

        self.ispolnitel = novyi_ispolnitel
        self.status = self.STATUS_NOVAYA
        self.save(update_fields=['ispolnitel', 'status', 'data_obnovleniya'])
        self._zapisat_istoriyu(staryi_status, izmenil)

        return staryi_ispolnitel


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


def put_vlozhenii(instance, filename):
    return f'zadachi/{instance.zadacha_id}/{filename}'


class Vlozhenie(models.Model):
    """Файл, прикреплённый к задаче (результат работы, отчёт и т.д.)"""

    zadacha = models.ForeignKey(
        Zadacha,
        verbose_name='Задача',
        related_name='vlozheniya',
        on_delete=models.CASCADE,
    )
    fail = models.FileField('Файл', upload_to=put_vlozhenii)
    opisanie = models.CharField('Описание файла', max_length=250, blank=True)
    zagruzil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Загрузил',
        on_delete=models.CASCADE,
    )
    data_zagruzki = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'
        ordering = ['-data_zagruzki']

    def __str__(self):
        return f'{self.fail.name} ({self.zadacha.zagolovok})'


class Uvedomlenie(models.Model):
    """Внутрисистемное уведомление пользователю"""

    TIP_NOVAYA_ZADACHA = 'novaya_zadacha'
    TIP_NA_PROVERKE = 'na_proverke'
    TIP_NA_DORABOTKE = 'na_dorabotke'
    TIP_PODTVERZHDENO = 'podtverzhdeno'
    TIP_SROK_BLIZKO = 'srok_blizko'
    TIP_PEREZNACHENO = 'pereznacheno'

    TIPY = [
        (TIP_NOVAYA_ZADACHA, 'Новая задача'),
        (TIP_NA_PROVERKE, 'Отправлено на проверку'),
        (TIP_NA_DORABOTKE, 'Отправлено на доработку'),
        (TIP_PODTVERZHDENO, 'Выполнение подтверждено'),
        (TIP_SROK_BLIZKO, 'Срок скоро истекает'),
        (TIP_PEREZNACHENO, 'Поручение переназначено'),
    ]

    poluchatel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Получатель',
        related_name='uvedomleniya',
        on_delete=models.CASCADE,
    )
    zadacha = models.ForeignKey(
        Zadacha,
        verbose_name='Задача',
        related_name='uvedomleniya',
        on_delete=models.CASCADE,
    )
    tip = models.CharField('Тип', max_length=30, choices=TIPY)
    tekst = models.CharField('Текст уведомления', max_length=300)
    prochitano = models.BooleanField('Прочитано', default=False)
    data_sozdaniya = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-data_sozdaniya']

    def __str__(self):
        return f'{self.get_tip_display()} для {self.poluchatel}'

class IstoriyaStatusov(models.Model):
    """История изменений статуса задачи — кто и когда переводил в какой статус"""

    zadacha = models.ForeignKey(
        Zadacha,
        verbose_name='Задача',
        related_name='istoriya',
        on_delete=models.CASCADE,
    )
    staryi_status = models.CharField('Был статус', max_length=20, choices=Zadacha.STATUSY, blank=True)
    novyi_status = models.CharField('Стал статус', max_length=20, choices=Zadacha.STATUSY)
    izmenil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Кто изменил',
        on_delete=models.PROTECT,
    )
    data_izmeneniya = models.DateTimeField('Дата изменения', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись истории статуса'
        verbose_name_plural = 'История статусов'
        ordering = ['data_izmeneniya']

    def __str__(self):
        return f'{self.zadacha.zagolovok}: {self.staryi_status or "—"} → {self.novyi_status}'

class IstoriyaNaznacheniya(models.Model):
    """История переназначений задачи другому исполнителю"""

    zadacha = models.ForeignKey(
        Zadacha,
        verbose_name='Задача',
        related_name='istoriya_naznacheniy',
        on_delete=models.CASCADE,
    )
    staryi_ispolnitel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Был исполнитель',
        related_name='+',
        on_delete=models.SET_NULL,
        null=True,
    )
    novyi_ispolnitel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Стал исполнитель',
        related_name='+',
        on_delete=models.CASCADE,
    )
    izmenil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='Кто переназначил',
        related_name='+',
        on_delete=models.PROTECT,
    )
    prichina = models.CharField('Причина переназначения', max_length=300, blank=True)
    data_izmeneniya = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись переназначения'
        verbose_name_plural = 'История переназначений'
        ordering = ['data_izmeneniya']

    def __str__(self):
        return f'{self.zadacha.zagolovok}: {self.staryi_ispolnitel} → {self.novyi_ispolnitel}'