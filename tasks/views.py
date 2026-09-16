from datetime import datetime
from io import BytesIO
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa
from xhtml2pdf import default as pisa_default

from django.db.models import Count, Q

from .forms import KommentariiForm, ZadachaForm, VlozhenieForm, PereznachitForm
from .models import Zadacha, Vlozhenie
from .notifications import (
    uvedomit_o_novoi_zadache,
    uvedomit_o_proverke,
    uvedomit_o_dorabotke,
    uvedomit_o_podtverzhdenii,
    uvedomit_o_pereznachenii,
)

def _zaregistrirovat_shrift():
    """Регистрирует шрифт с поддержкой кириллицы и подменяет шрифт по умолчанию для xhtml2pdf"""
    if 'ArialCyr' in pdfmetrics.getRegisteredFontNames():
        return

    put_k_shriftam = settings.STATICFILES_DIRS[0] / 'fonts'
    pdfmetrics.registerFont(TTFont('ArialCyr', str(put_k_shriftam / 'arial.ttf')))
    pdfmetrics.registerFont(TTFont('ArialCyr-Bold', str(put_k_shriftam / 'arial-bold.ttf')))
    pdfmetrics.registerFontFamily(
        'ArialCyr',
        normal='ArialCyr',
        bold='ArialCyr-Bold',
        italic='ArialCyr',
        boldItalic='ArialCyr-Bold',
    )

    for imya in ('helvetica', 'arial', 'sans-serif', 'times', 'times new roman', 'courier'):
        pisa_default.DEFAULT_FONT[imya] = 'ArialCyr'



@login_required
def dashboard(request):
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)
    else:
        zadachi = Zadacha.objects.filter(ispolnitel=polzovatel)

    # выполненные задачи уходят в архив — на dashboard показываем только активные
    zadachi = zadachi.exclude(status=Zadacha.STATUS_VYPOLNENA)

    status_filtr = request.GET.get('status', '')
    prioritet_filtr = request.GET.get('prioritet', '')
    srok_filtr = request.GET.get('srok', '')
    poisk = request.GET.get('poisk', '').strip()

    if status_filtr:
        zadachi = zadachi.filter(status=status_filtr)

    if prioritet_filtr:
        zadachi = zadachi.filter(prioritet=prioritet_filtr)

    if srok_filtr == 'prosrocheno':
        zadachi = zadachi.filter(srok_vypolneniya__lt=timezone.now().date())
    elif srok_filtr == 'segodnya':
        zadachi = zadachi.filter(srok_vypolneniya=timezone.now().date())
    elif srok_filtr == 'nedelya':
        cherez_nedelyu = timezone.now().date() + timezone.timedelta(days=7)
        zadachi = zadachi.filter(srok_vypolneniya__lte=cherez_nedelyu, srok_vypolneniya__gte=timezone.now().date())

    if poisk:
        zadachi = zadachi.filter(zagolovok__icontains=poisk)

    zagruzhennost = None
    if polzovatel.is_rukovoditel():
        zagruzhennost = polzovatel.otdel.sotrudniki.filter(rol='sotrudnik').annotate(
            aktivnykh=Count(
                'naznachennye_zadachi',
                filter=Q(naznachennye_zadachi__postavil=polzovatel) & ~Q(naznachennye_zadachi__status=Zadacha.STATUS_VYPOLNENA),
            )
        ).order_by('-aktivnykh')

    # статус "Выполнена" убираем из фильтра — эти задачи теперь в архиве
    statusy_dlya_filtra = [s for s in Zadacha.STATUSY if s[0] != Zadacha.STATUS_VYPOLNENA]

    context = {
        'zadachi': zadachi,
        'polzovatel': polzovatel,
        'status_filtr': status_filtr,
        'prioritet_filtr': prioritet_filtr,
        'srok_filtr': srok_filtr,
        'poisk': poisk,
        'statusy': statusy_dlya_filtra,
        'prioritety': Zadacha.PRIORITETY,
        'zagruzhennost': zagruzhennost,
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def sozdat_zadachu(request):
    polzovatel = request.user
    if not polzovatel.is_rukovoditel():
        raise PermissionDenied('Создавать поручения может только руководитель отдела.')

    if request.method == 'POST':
        form = ZadachaForm(request.POST, request.FILES, rukovoditel=polzovatel)
        if form.is_valid():
            zadacha = form.save(commit=False)
            zadacha.otdel = polzovatel.otdel
            zadacha.postavil = polzovatel
            try:
                zadacha.full_clean()
            except ValidationError as e:
                form.add_error(None, e)
            else:
                zadacha.save()
                zadacha.sozdana(polzovatel)

                fail = form.cleaned_data.get('fail')
                if fail:
                    Vlozhenie.objects.create(
                        zadacha=zadacha,
                        fail=fail,
                        zagruzil=polzovatel,
                    )

                uvedomit_o_novoi_zadache(zadacha)
                messages.success(request, 'Поручение создано и назначено сотруднику.')
                return redirect('dashboard')
    else:
        form = ZadachaForm(rukovoditel=polzovatel)

    return render(request, 'tasks/sozdat_zadachu.html', {'form': form})

@login_required
def detal_zadachi(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk)
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        if zadacha.postavil_id != polzovatel.id:
            raise PermissionDenied('Вы можете просматривать только поставленные вами поручения.')
    else:
        if zadacha.ispolnitel_id != polzovatel.id:
            raise PermissionDenied('Это поручение назначено не вам.')

    if request.method == 'POST' and 'tekst' in request.POST:
        kom_form = KommentariiForm(request.POST)
        if kom_form.is_valid():
            kommentarii = kom_form.save(commit=False)
            kommentarii.zadacha = zadacha
            kommentarii.avtor = polzovatel
            kommentarii.save()
            return redirect('detal_zadachi', pk=zadacha.pk)
    else:
        kom_form = KommentariiForm()

    vlozhenie_form = VlozhenieForm()

    pereznachit_form = None
    if polzovatel.is_rukovoditel() and zadacha.status != Zadacha.STATUS_VYPOLNENA:
        pereznachit_form = PereznachitForm(zadacha=zadacha)

    context = {
        'zadacha': zadacha,
        'polzovatel': polzovatel,
        'kom_form': kom_form,
        'vlozhenie_form': vlozhenie_form,
        'pereznachit_form': pereznachit_form,
    }
    return render(request, 'tasks/detal_zadachi.html', context)


@login_required
def zagruzit_fail(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk)
    polzovatel = request.user

    if polzovatel.id not in (zadacha.postavil_id, zadacha.ispolnitel_id):
        raise PermissionDenied('У вас нет доступа к этой задаче.')

    if request.method == 'POST':
        form = VlozhenieForm(request.POST, request.FILES)
        if form.is_valid():
            vlozhenie = form.save(commit=False)
            vlozhenie.zadacha = zadacha
            vlozhenie.zagruzil = polzovatel
            vlozhenie.save()
            messages.success(request, 'Файл прикреплён к задаче.')
        else:
            messages.error(request, 'Не удалось загрузить файл.')

    return redirect('detal_zadachi', pk=pk)


@login_required
def prinyat_zadachu(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, ispolnitel=request.user)
    if zadacha.status == Zadacha.STATUS_NOVAYA:
        zadacha.prinyat_k_ispolneniyu(request.user)
        messages.success(request, 'Поручение принято к исполнению.')
    return redirect('detal_zadachi', pk=pk)


@login_required
def nachat_rabotu(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, ispolnitel=request.user)
    if zadacha.status == Zadacha.STATUS_PRINYATA:
        zadacha.nachat_rabotu(request.user)
        messages.info(request, 'Поручение переведено в статус "В работе".')
    return redirect('detal_zadachi', pk=pk)


@login_required
def otpravit_na_proverku(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, ispolnitel=request.user)
    if zadacha.status in (Zadacha.STATUS_V_RABOTE, Zadacha.STATUS_NA_DORABOTKE):
        zadacha.otpravit_na_proverku(request.user)
        uvedomit_o_proverke(zadacha)
        messages.success(request, 'Поручение отправлено руководителю на проверку.')
    return redirect('detal_zadachi', pk=pk)


@login_required
def proverit_zadachu(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, postavil=request.user)
    if zadacha.status != Zadacha.STATUS_NA_PROVERKE:
        raise PermissionDenied('Это поручение сейчас не находится на проверке.')

    action = request.POST.get('action')

    if action == 'podtverdit':
        zadacha.podtverdit_vypolnenie(request.user)
        uvedomit_o_podtverzhdenii(zadacha)
        messages.success(request, 'Выполнение подтверждено.')
    elif action == 'na_dorabotku':
        zadacha.otpravit_na_dorabotku(request.user)
        uvedomit_o_dorabotke(zadacha)
        messages.info(request, 'Поручение отправлено на доработку.')

    return redirect('detal_zadachi', pk=pk)


@login_required
def uvedomleniya(request):
    spisok = request.user.uvedomleniya.all()
    spisok.filter(prochitano=False).update(prochitano=True)
    return render(request, 'tasks/uvedomleniya.html', {'spisok': spisok})

@login_required
def statistika(request):
    polzovatel = request.user
    if not polzovatel.is_rukovoditel():
        raise PermissionDenied('Статистика доступна только руководителю отдела.')

    zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)

    po_statusu = zadachi.values('status').annotate(kolichestvo=Count('id'))
    slovar_statusov = dict(Zadacha.STATUSY)
    statusy_labels = [slovar_statusov[row['status']] for row in po_statusu]
    statusy_dannye = [row['kolichestvo'] for row in po_statusu]

    po_prioritetu = zadachi.values('prioritet').annotate(kolichestvo=Count('id'))
    slovar_prioritetov = dict(Zadacha.PRIORITETY)
    prioritet_labels = [slovar_prioritetov[row['prioritet']] for row in po_prioritetu]
    prioritet_dannye = [row['kolichestvo'] for row in po_prioritetu]

    vsego = zadachi.count()
    prosrocheno = zadachi.exclude(status=Zadacha.STATUS_VYPOLNENA).filter(
        srok_vypolneniya__lt=timezone.now().date()
    ).count()
    vypolneno = zadachi.filter(status=Zadacha.STATUS_VYPOLNENA).count()

    context = {
        'vsego': vsego,
        'vypolneno': vypolneno,
        'prosrocheno': prosrocheno,
        'statusy_labels': statusy_labels,
        'statusy_dannye': statusy_dannye,
        'prioritet_labels': prioritet_labels,
        'prioritet_dannye': prioritet_dannye,
    }
    return render(request, 'tasks/statistika.html', context)

def _sobrat_otchet(request):
    """Общая логика фильтрации — используется и для HTML-страницы, и для PDF"""
    polzovatel = request.user

    zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)

    data_ot = request.GET.get('data_ot', '')
    data_do = request.GET.get('data_do', '')
    sotrudnik_id = request.GET.get('sotrudnik', '')

    if data_ot:
        zadachi = zadachi.filter(data_sozdaniya__date__gte=datetime.strptime(data_ot, '%Y-%m-%d').date())
    if data_do:
        zadachi = zadachi.filter(data_sozdaniya__date__lte=datetime.strptime(data_do, '%Y-%m-%d').date())
    if sotrudnik_id:
        zadachi = zadachi.filter(ispolnitel_id=sotrudnik_id)

    zadachi = zadachi.select_related('ispolnitel').order_by('ispolnitel__last_name', '-data_sozdaniya')

    return zadachi, data_ot, data_do, sotrudnik_id


@login_required
def otchet(request):
    polzovatel = request.user
    if not polzovatel.is_rukovoditel():
        raise PermissionDenied('Отчёт доступен только руководителю отдела.')

    zadachi, data_ot, data_do, sotrudnik_id = _sobrat_otchet(request)
    sotrudniki = polzovatel.otdel.sotrudniki.filter(rol='sotrudnik')

    context = {
        'zadachi': zadachi,
        'sotrudniki': sotrudniki,
        'data_ot': data_ot,
        'data_do': data_do,
        'sotrudnik_id': sotrudnik_id,
        'polzovatel': polzovatel,
    }
    return render(request, 'tasks/otchet.html', context)


@login_required
def otchet_pdf(request):
    polzovatel = request.user
    if not polzovatel.is_rukovoditel():
        raise PermissionDenied('Отчёт доступен только руководителю отдела.')

    _zaregistrirovat_shrift()

    zadachi, data_ot, data_do, sotrudnik_id = _sobrat_otchet(request)

    context = {
        'zadachi': zadachi,
        'polzovatel': polzovatel,
        'data_ot': data_ot,
        'data_do': data_do,
        'segodnya': timezone.now().date(),
    }
    html = render_to_string('tasks/otchet_pdf.html', context)

    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="otchet.pdf"'
    return response

@login_required
def arkhiv(request):
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel, status=Zadacha.STATUS_VYPOLNENA)
    else:
        zadachi = Zadacha.objects.filter(ispolnitel=polzovatel, status=Zadacha.STATUS_VYPOLNENA)

    poisk = request.GET.get('poisk', '').strip()
    if poisk:
        zadachi = zadachi.filter(zagolovok__icontains=poisk)

    zadachi = zadachi.order_by('-data_podtverzhdeniya')

    context = {'zadachi': zadachi, 'polzovatel': polzovatel, 'poisk': poisk}
    return render(request, 'tasks/arkhiv.html', context)

@login_required
def pereznachit_zadachu(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, postavil=request.user)

    if request.method == 'POST':
        form = PereznachitForm(request.POST, zadacha=zadacha)
        if form.is_valid():
            try:
                staryi_ispolnitel = zadacha.pereznachit(
                    form.cleaned_data['novyi_ispolnitel'],
                    request.user,
                    form.cleaned_data['prichina'],
                )
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
            else:
                uvedomit_o_pereznachenii(zadacha, staryi_ispolnitel)
                messages.success(request, f'Поручение переназначено сотруднику {zadacha.ispolnitel}.')
        else:
            messages.error(request, 'Выберите корректного нового исполнителя.')

    return redirect('detal_zadachi', pk=pk)

@login_required
def udalit_vlozhenie(request, pk):
    vlozhenie = get_object_or_404(Vlozhenie, pk=pk)
    zadacha = vlozhenie.zadacha
    polzovatel = request.user

    if polzovatel.id not in (vlozhenie.zagruzil_id, zadacha.postavil_id):
        raise PermissionDenied('Вы не можете открепить этот файл.')

    if request.method == 'POST':
        put_k_failu = vlozhenie.fail.path
        vlozhenie.delete()
        if os.path.exists(put_k_failu):
            os.remove(put_k_failu)
        messages.success(request, 'Файл откреплён.')

    return redirect('detal_zadachi', pk=zadacha.pk)