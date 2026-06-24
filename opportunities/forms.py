from django import forms

from .models import Application, Opportunity


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ['title', 'organization', 'description', 'poster_image', 'location', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Opportunity title'}),
            'organization': forms.TextInput(attrs={'placeholder': 'Club or organization name'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe requirements and details'}),
            'location': forms.TextInput(attrs={'placeholder': 'City or area'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
        }


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['motivation']
        widgets = {
            'motivation': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Optional: explain why you are a good fit for this opportunity',
                }
            )
        }
