from django import forms
from django.utils import timezone
import os

from .models import Application, Opportunity


class OpportunityForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.scout = kwargs.pop('scout', None)
        super().__init__(*args, **kwargs)
        self.fields['max_applications'].required = False
        self.fields['max_applications'].help_text = 'Optional. Set how many applications you want before closing early.'

    class Meta:
        model = Opportunity
        fields = ['title', 'organization', 'description', 'poster_image', 'location', 'deadline', 'max_applications']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Opportunity title'}),
            'organization': forms.TextInput(attrs={'placeholder': 'Club or organization name'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe requirements and details'}),
            'location': forms.TextInput(attrs={'placeholder': 'City or area'}),
            'deadline': forms.DateInput(attrs={'type': 'date', 'min': timezone.localdate().isoformat()}),
            'max_applications': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Optional application cap'}),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        today = timezone.localdate()
        if deadline and deadline < today:
            raise forms.ValidationError('Deadline must be today or a future date.')
        return deadline

    def clean_poster_image(self):
        poster = self.cleaned_data.get('poster_image')
        if not poster:
            return poster

        uploaded_name = os.path.basename(poster.name).lower()
        existing_posters = Opportunity.objects.exclude(pk=self.instance.pk).exclude(poster_image='')
        for opportunity in existing_posters:
            if not opportunity.poster_image:
                continue
            existing_name = os.path.basename(opportunity.poster_image.name).lower()
            if existing_name == uploaded_name:
                raise forms.ValidationError('This poster image is already used in another opportunity. Please upload a different poster.')

        return poster

    def clean_max_applications(self):
        limit = self.cleaned_data.get('max_applications')
        if limit is not None and limit < 1:
            raise forms.ValidationError('Application limit must be at least 1.')
        return limit

    def clean(self):
        cleaned_data = super().clean()

        title = (cleaned_data.get('title') or '').strip()
        organization = (cleaned_data.get('organization') or '').strip()
        location = (cleaned_data.get('location') or '').strip()
        deadline = cleaned_data.get('deadline')

        if title and organization and location and deadline:
            queryset = Opportunity.objects.exclude(pk=self.instance.pk).filter(
                title__iexact=title,
                organization__iexact=organization,
                location__iexact=location,
                deadline=deadline,
            )
            if self.scout is not None:
                queryset = queryset.filter(scout=self.scout)

            if queryset.exists():
                raise forms.ValidationError('This opportunity has already been posted. Please update the existing one instead of posting a duplicate.')

        return cleaned_data


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
