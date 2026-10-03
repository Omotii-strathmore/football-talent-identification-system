import re

from django import forms
from django.core.validators import FileExtensionValidator

from scouts.models import Scout


# Ordered from goal to attack, as they appear on a pitch.
SPECIALIZATION_CHOICES = (
	('goalkeeping', 'goalkeeping'),
	('defence', 'defence'),
	('midfield', 'midfield'),
	('attacking', 'attacking'),
	('general', 'general'),
)


# Placeholder answers people type just to get past the box.
_PLACEHOLDER_NAMES = {
	'test', 'testing', 'asdf', 'qwerty', 'abc', 'xyz', 'none', 'na', 'n/a', 'nil', 'null', 'nothing',
	'unknown', 'club', 'team', 'academy', 'organization', 'organisation', 'scout', 'football', 'soccer',
	'fc', 'sc', 'hello', 'hi', 'name', 'my club', 'no club', 'independent',
}


def clean_organization_name(value):
	"""Reject names that are clearly not a real club or organisation.

	This cannot prove a club exists; the administrator does that by checking the
	verification document. It only stops empty, random or placeholder answers.
	"""
	name = re.sub(r'\s+', ' ', (value or '')).strip()
	message = 'Please enter the full, real name of your club, academy or organisation (for example "Gor Mahia Youth Academy").'
	letters = re.findall(r'[^\W\d_]', name)
	if len(name) < 3 or len(letters) < 3:
		raise forms.ValidationError(message)
	if len(name) > 100:
		raise forms.ValidationError('Please keep the name under 100 characters.')
	if not re.fullmatch(r"[\w\s&.,'()/-]+", name):
		raise forms.ValidationError("Please use only letters, numbers, spaces and simple punctuation (& . , ' - ( ) /).")
	if name.lower() in _PLACEHOLDER_NAMES:
		raise forms.ValidationError(message)
	lowered = name.lower()
	# The same character four or more times in a row, e.g. "aaaa".
	if re.search(r'(.)\1{3,}', lowered):
		raise forms.ValidationError(message)
	if not re.search(r'[aeiouy]', lowered):
		raise forms.ValidationError(message)
	# Keyboard mashing such as "asdfgh" produces long runs of consonants.
	if re.search(r'[bcdfghjklmnpqrstvwxz]{5,}', lowered):
		raise forms.ValidationError(message)
	if name == name.lower():
		name = name.title()
	return name


class ScoutOnboardingForm(forms.ModelForm):
	specialization = forms.ChoiceField(
		choices=SPECIALIZATION_CHOICES,
		widget=forms.Select(attrs={'class': 'form-select'}),
		help_text='Select one specialization.',
	)
	profile_photo = forms.ImageField(
		required=False,
		label='Photo',
		help_text='Optional. Add a clear profile photo.',
		widget=forms.ClearableFileInput(attrs={'accept': 'image/*'}),
	)
	verification_document = forms.FileField(
		required=True,
		label='Verification Document',
		help_text='Upload a PDF or Word document to verify your scout profile.',
		validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])],
		widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),
	)

	class Meta:
		model = Scout
		fields = ["organization", "scouts_for", "specialization", "verification_document", "profile_photo"]
		widgets = {
			"organization": forms.TextInput(attrs={"placeholder": "Organization worked with"}),
		}


	def clean_organization(self):
		return clean_organization_name(self.cleaned_data.get('organization'))

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if 'scouts_for' in self.fields:
			self.fields['scouts_for'].required = False

	def clean_scouts_for(self):
		# Scouts who skip the question look for both Stars and Starlets.
		return self.cleaned_data.get('scouts_for') or 'both'


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


	def clean_organization(self):
		return clean_organization_name(self.cleaned_data.get('organization'))


class ScoutResubmitForm(forms.ModelForm):
	"""Lets a rejected scout send a new verification document for another review."""
	verification_document = forms.FileField(
		required=True,
		label='New verification document',
		help_text='A coaching licence, a signed club or academy letter, or an official accreditation. PDF or Word.',
		validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])],
		widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'}),
	)

	class Meta:
		model = Scout
		fields = ["organization", "scouts_for", "verification_document"]
		labels = {"organization": "Who do you scout for?", "scouts_for": "Which players do you scout?"}
		help_texts = {"scouts_for": "Stars are men's football and Starlets are women's football. Your document must match this choice."}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['scouts_for'].required = False

	def clean_scouts_for(self):
		# Keep the earlier choice if none was sent.
		return self.cleaned_data.get('scouts_for') or self.instance.scouts_for or 'both'

	def clean_organization(self):
		return clean_organization_name(self.cleaned_data.get('organization'))
