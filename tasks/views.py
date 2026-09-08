from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Count

from .forms import KommentariiForm, ZadachaForm, VlozhenieForm
from .models import Zadacha

from .notifications import (
    uvedomit_o_novoi_zadache,
    uvedomit_o_proverke,
    uvedomit_o_dorabotke,
    uvedomit_o_podtverzhdenii,
)


@login_required
def dashboard(request):
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)
    else:
        zadachi = Zadacha.objects.filter(ispolnitel=polzovatel)

    # --- фильтры ---
    status_filtr = request.GET.get('status', '')
    prioritet_filtr = request.GET.get('prioritet', '')
    srok_filtr = request.GET.get('srok', '')
    poisk = request.GET.get('poisk', '').strip()

    if status_filtr:
        zadachi = zadachi.filter(status=status_filtr)

    if prioritet_filtr:
        zadachi = zadachi.filter(prioritet=prioritet_filtr)

    if srok_filtr == 'prosrocheno':
        zadachi = zadachi.exclude(status=Zadacha.STATUS_VYPOLNENA).filter(
            srok_vypolneniya__lt=timezone.now().date()
        )
    elif srok_filtr == 'segodnya':
        zadachi = zadachi.filter(srok_vypolneniya=timezone.now().date())
    elif srok_filtr == 'nedelya':
        cherez_nedelyu = timezone.now().date() + timezone.timedelta(days=7)
        zadachi = zadachi.filter(srok_vypolneniya__lte=cherez_nedelyu, srok_vypolneniya__gte=timezone.now().date())

    if poisk:
        zadachi = zadachi.filter(zagolovok__icontains=poisk)

    context = {
        'zadachi': zadachi,
        'polzovatel': polzovatel,
        'status_filtr': status_filtr,
        'prioritet_filtr': prioritet_filtr,
        'srok_filtr': srok_filtr,
        'poisk': poisk,
        'statusy': Zadacha.STATUSY,
        'prioritety': Zadacha.PRIORITETY,
    }
    return render(request, 'tasks/dashboard.html', context)


@login_required
def sozdat_zadachu(request):
    polzovatel = request.user
    if not polzovatel.is_rukovoditel():
        raise PermissionDenied('Создавать поручения может только руководитель отдела.')

    if request.method == 'POST':
        form = ZadachaForm(request.POST, rukovoditel=polzovatel)
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

    context = {
        'zadacha': zadacha,
        'polzovatel': polzovatel,
        'kom_form': kom_form,
        'vlozhenie_form': vlozhenie_form,
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