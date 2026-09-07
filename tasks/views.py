from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import KommentariiForm, OtsenkaForm, ZadachaForm, VlozhenieForm
from .models import Zadacha


@login_required
def dashboard(request):
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)
    else:
        zadachi = Zadacha.objects.filter(ispolnitel=polzovatel)

    context = {'zadachi': zadachi, 'polzovatel': polzovatel}
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

    otsenka_form = None
    if polzovatel.is_rukovoditel() and zadacha.status == Zadacha.STATUS_NA_PROVERKE:
        otsenka_form = OtsenkaForm()

    vlozhenie_form = VlozhenieForm()

    context = {
        'zadacha': zadacha,
        'polzovatel': polzovatel,
        'kom_form': kom_form,
        'otsenka_form': otsenka_form,
        'vlozhenie_form': vlozhenie_form,
    }
    return render(request, 'tasks/detal_zadachi.html', context)

@login_required
def zagruzit_fail(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk)
    polzovatel = request.user

    # прикреплять файл может либо руководитель, поставивший задачу, либо исполнитель
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
        zadacha.prinyat_k_ispolneniyu()
        messages.success(request, 'Поручение принято к исполнению.')
    return redirect('detal_zadachi', pk=pk)


@login_required
def nachat_rabotu(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, ispolnitel=request.user)
    if zadacha.status == Zadacha.STATUS_PRINYATA:
        zadacha.nachat_rabotu()
        messages.info(request, 'Поручение переведено в статус "В работе".')
    return redirect('detal_zadachi', pk=pk)


@login_required
def otpravit_na_proverku(request, pk):
    zadacha = get_object_or_404(Zadacha, pk=pk, ispolnitel=request.user)
    if zadacha.status in (Zadacha.STATUS_V_RABOTE, Zadacha.STATUS_NA_DORABOTKE):
        zadacha.otpravit_na_proverku()
        messages.success(request, 'Поручение отправлено руководителю на проверку.')
    return redirect('detal_zadachi', pk=pk)


@login_required
def proverit_zadachu(request, pk):
    """Руководитель подтверждает выполнение (с оценкой) или отправляет на доработку"""
    zadacha = get_object_or_404(Zadacha, pk=pk, postavil=request.user)
    if zadacha.status != Zadacha.STATUS_NA_PROVERKE:
        raise PermissionDenied('Это поручение сейчас не находится на проверке.')

    action = request.POST.get('action')

    if action == 'podtverdit':
        form = OtsenkaForm(request.POST)
        if form.is_valid():
            otsenka = form.save(commit=False)
            otsenka.zadacha = zadacha
            otsenka.otsenil = request.user
            otsenka.save()
            zadacha.podtverdit_vypolnenie()
            messages.success(request, 'Выполнение подтверждено, оценка выставлена.')
        else:
            messages.error(request, 'Укажите корректную оценку от 0 до 10.')
    elif action == 'na_dorabotku':
        zadacha.otpravit_na_dorabotku()
        messages.info(request, 'Поручение отправлено на доработку.')

    return redirect('detal_zadachi', pk=pk)