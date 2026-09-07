from django import forms
from .models import Zadacha, Otsenka, Kommentarii, Vlozhenie


class ZadachaForm(forms.ModelForm):
    class Meta:
        model = Zadacha
        fields = ['zagolovok', 'opisanie', 'ispolnitel', 'prioritet', 'srok_vypolneniya']
        widgets = {
            'srok_vypolneniya': forms.DateInput(attrs={'type': 'date'}),
            'opisanie': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'zagolovok': 'Заголовок',
            'opisanie': 'Описание',
            'ispolnitel': 'Исполнитель',
            'prioritet': 'Приоритет',
            'srok_vypolneniya': 'Срок выполнения',
        }

    def __init__(self, *args, rukovoditel=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Исполнителя можно выбрать только из отдела руководителя
        if rukovoditel is not None and rukovoditel.otdel_id:
            self.fields['ispolnitel'].queryset = rukovoditel.otdel.sotrudniki.filter(
                rol='sotrudnik'
            )


class OtsenkaForm(forms.ModelForm):
    class Meta:
        model = Otsenka
        fields = ['ball', 'kommentarii_rukovoditelya']
        labels = {
            'ball': 'Оценка (0-10)',
            'kommentarii_rukovoditelya': 'Комментарий к оценке',
        }


class KommentariiForm(forms.ModelForm):
    class Meta:
        model = Kommentarii
        fields = ['tekst']
        widgets = {
            'tekst': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Написать комментарий...'})
        }
        labels = {'tekst': ''}

class VlozhenieForm(forms.ModelForm):
    class Meta:
        model = Vlozhenie
        fields = ['fail', 'opisanie']
        labels = {
            'fail': 'Файл',
            'opisanie': 'Описание (необязательно)',
        }