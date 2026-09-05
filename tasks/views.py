from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Zadacha


@login_required
def dashboard(request):
    polzovatel = request.user

    if polzovatel.is_rukovoditel():
        # руководитель видит только задачи, которые сам поставил в своём отделе
        zadachi = Zadacha.objects.filter(postavil=polzovatel, otdel=polzovatel.otdel)
    else:
        # сотрудник видит только назначенные ему задачи
        zadachi = Zadacha.objects.filter(ispolnitel=polzovatel)

    context = {
        'zadachi': zadachi,
        'polzovatel': polzovatel,
    }
    return render(request, 'tasks/dashboard.html', context)