from .models import Uvedomlenie


def uvedomit_o_novoi_zadache(zadacha):
    Uvedomlenie.objects.create(
        poluchatel=zadacha.ispolnitel,
        zadacha=zadacha,
        tip=Uvedomlenie.TIP_NOVAYA_ZADACHA,
        tekst=f'Вам назначено новое поручение: "{zadacha.zagolovok}"',
    )


def uvedomit_o_proverke(zadacha):
    Uvedomlenie.objects.create(
        poluchatel=zadacha.postavil,
        zadacha=zadacha,
        tip=Uvedomlenie.TIP_NA_PROVERKE,
        tekst=f'{zadacha.ispolnitel} отправил(а) поручение "{zadacha.zagolovok}" на проверку',
    )


def uvedomit_o_dorabotke(zadacha):
    Uvedomlenie.objects.create(
        poluchatel=zadacha.ispolnitel,
        zadacha=zadacha,
        tip=Uvedomlenie.TIP_NA_DORABOTKE,
        tekst=f'Поручение "{zadacha.zagolovok}" отправлено на доработку',
    )


def uvedomit_o_podtverzhdenii(zadacha):
    Uvedomlenie.objects.create(
        poluchatel=zadacha.ispolnitel,
        zadacha=zadacha,
        tip=Uvedomlenie.TIP_PODTVERZHDENO,
        tekst=f'Выполнение поручения "{zadacha.zagolovok}" подтверждено',
    )