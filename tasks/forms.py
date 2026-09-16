from django import forms
from .models import Zadacha, Kommentarii, Vlozhenie


class ZadachaForm(forms.ModelForm):
    fail = forms.FileField(label='Прикрепить файл (необязательно)', required=False)

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
        if rukovoditel is not None and rukovoditel.otdel_id:
            sotrudniki = rukovoditel.otdel.sotrudniki.filter(rol='sotrudnik')
            self.fields['ispolnitel'].queryset = sotrudniki
            self.fields['ispolnitel'].label_from_instance = self._podpis_sotrudnika

    @staticmethod
    def _podpis_sotrudnika(sotrudnik):
        imya = sotrudnik.get_full_name() or sotrudnik.username
        if sotrudnik.dolzhnost:
            return f'{imya} — {sotrudnik.dolzhnost}'
        return imya


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


class PereznachitForm(forms.Form):
    novyi_ispolnitel = forms.ModelChoiceField(
        queryset=None,
        label='Новый исполнитель',
    )
    prichina = forms.CharField(
        label='Причина (необязательно)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, zadacha=None, **kwargs):
        super().__init__(*args, **kwargs)
        if zadacha is not None:
            sotrudniki = zadacha.otdel.sotrudniki.filter(rol='sotrudnik').exclude(id=zadacha.ispolnitel_id)
            self.fields['novyi_ispolnitel'].queryset = sotrudniki
            self.fields['novyi_ispolnitel'].label_from_instance = self._podpis_sotrudnika

    @staticmethod
    def _podpis_sotrudnika(sotrudnik):
        imya = sotrudnik.get_full_name() or sotrudnik.username
        if sotrudnik.dolzhnost:
            return f'{imya} — {sotrudnik.dolzhnost}'
        return imya