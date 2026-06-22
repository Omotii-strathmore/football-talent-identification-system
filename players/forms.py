from django import forms
from .models import PlayerProfile


class PlayerProfileForm(forms.ModelForm):

    class Meta:

        model = PlayerProfile

        fields = [
            'full_name',
            'age',
            'position',
            'location',
            'profile_photo',
            'bio'
        ]