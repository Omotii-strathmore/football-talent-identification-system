from django import forms
from .models import PlayerProfile, PlayerVideo


KENYA_COUNTIES = [
    'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo-Marakwet', 'Embu',
    'Garissa', 'Homa Bay', 'Isiolo', 'Kajiado', 'Kakamega', 'Kericho',
    'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii', 'Kisumu', 'Kitui', 'Kwale',
    'Laikipia', 'Lamu', 'Machakos', 'Makueni', 'Mandera', 'Marsabit',
    'Meru', 'Migori', 'Mombasa', "Murang'a", 'Nairobi', 'Nakuru',
    'Nandi', 'Narok', 'Nyamira', 'Nyandarua', 'Nyeri', 'Samburu',
    'Siaya', 'Taita-Taveta', 'Tana River', 'Tharaka-Nithi', 'Trans Nzoia',
    'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir', 'West Pokot'
]


class PlayerProfileForm(forms.ModelForm):

    class Meta:

        model = PlayerProfile

        fields = [
            'full_name',
            'age',
            'position',
            'location',
            'profile_photo',
            'bio',
            'contact_email',
            'contact_phone',
            'consent_to_share_contact',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact_email'].required = False
        self.fields['contact_phone'].required = False
        self.fields['contact_email'].help_text = 'Optional. Interested scouts could reach out using this email.'
        self.fields['contact_phone'].help_text = 'Optional. Interested scouts could reach out using this phone number.'
        self.fields['consent_to_share_contact'].help_text = (
            'With your consent, scouts can view these details and contact you directly.'
        )

    def clean(self):
        cleaned_data = super().clean()
        consent = cleaned_data.get('consent_to_share_contact')
        email = (cleaned_data.get('contact_email') or '').strip()
        phone = (cleaned_data.get('contact_phone') or '').strip()

        if consent and not email and not phone:
            raise forms.ValidationError(
                'Add at least one communication option (email or contact) before giving consent.'
            )

        return cleaned_data


class PlayerOnboardingForm(forms.ModelForm):
    KENYA_COUNTIES = KENYA_COUNTIES

    age = forms.IntegerField(
        min_value=12,
        max_value=28,
        widget=forms.NumberInput(
            attrs={
                'placeholder': 'Your age (12-28)',
                'min': 12,
                'max': 28,
            }
        ),
        help_text='Allowed age range: 12 to 28 years.',
    )

    class Meta:

        model = PlayerProfile

        fields = [
            'age',
            'position',
            'location'
        ]

        widgets = {
            'location': forms.TextInput(
                attrs={
                    'placeholder': 'Where are you From? (Type or select a county)',
                    'list': 'kenya-counties',
                    'autocomplete': 'off',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].help_text = 'Choose or type a county name from the 47 counties list.'

    def clean_location(self):
        entered_location = (self.cleaned_data.get('location') or '').strip()
        for county in KENYA_COUNTIES:
            if entered_location.lower() == county.lower():
                return county
        raise forms.ValidationError('Please select or type one of Kenya\'s 47 counties.')


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