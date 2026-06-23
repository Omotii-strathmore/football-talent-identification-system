from django import forms

from scouts.models import Scout


class ScoutOnboardingForm(forms.ModelForm):
	class Meta:
		model = Scout
		fields = ["organization", "specialization", "verification_document", "profile_photo"]
		widgets = {
			"organization": forms.TextInput(attrs={"placeholder": "Organization worked with"}),
			"specialization": forms.TextInput(attrs={"placeholder": "Scouting specialization"}),
		}
