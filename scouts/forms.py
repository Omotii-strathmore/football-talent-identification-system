from django import forms

from scouts.models import Scout


SPECIALIZATION_CHOICES = (
	('midfield', 'midfield'),
	('goalkeeping', 'goalkeeping'),
	('attacking', 'attacking'),
	('defence', 'defence'),
	('general', 'general'),
)


class ScoutOnboardingForm(forms.ModelForm):
	specialization = forms.ChoiceField(
		choices=SPECIALIZATION_CHOICES,
		widget=forms.Select(attrs={'class': 'form-select'}),
		help_text='Select one specialization.',
	)

	class Meta:
		model = Scout
		fields = ["organization", "specialization", "verification_document", "profile_photo"]
		widgets = {
			"organization": forms.TextInput(attrs={"placeholder": "Organization worked with"}),
		}


class ScoutEditDetailsForm(forms.ModelForm):
	specialization = forms.ChoiceField(
		choices=SPECIALIZATION_CHOICES,
		widget=forms.Select(attrs={'class': 'form-select'}),
		help_text='Select one specialization.',
	)

	class Meta:
		model = Scout
		fields = ["organization", "specialization", "profile_photo"]
		widgets = {
			"organization": forms.TextInput(attrs={"placeholder": "Organization worked with"}),
		}
