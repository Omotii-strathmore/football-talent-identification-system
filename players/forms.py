from django import forms
from .models import PlayerProfile, PlayerVideo


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


class PlayerOnboardingForm(forms.ModelForm):

    class Meta:

        model = PlayerProfile

        fields = [
            'age',
            'position',
            'location'
        ]

        widgets = {
            'age': forms.NumberInput(attrs={'placeholder': 'Your age'}),
            'location': forms.TextInput(attrs={'placeholder': 'Current location'}),
        }


class PlayerVideoForm(forms.ModelForm):

    class Meta:

        model = PlayerVideo

        fields = [
            'title',
            'video_file',
        ]

        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Video title'}),
        }