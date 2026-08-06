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
            'secondary_position',
            'height_cm',
            'weight_kg',
            'current_club',
            'previous_club',
            'previous_club_duration',
            'location',
            'profile_photo',
            'bio',
            'football_experience',
            'special_traits',
            'contact_email',
            'contact_phone',
            'consent_to_share_contact',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact_email'].required = False
        self.fields['contact_phone'].required = False
        self.fields['secondary_position'].required = False
        self.fields['height_cm'].required = False
        self.fields['weight_kg'].required = False
        self.fields['current_club'].required = False
        self.fields['previous_club'].required = False
        self.fields['previous_club_duration'].required = False
        self.fields['special_traits'].required = False
        self.fields['football_experience'].required = False
        self.fields['contact_email'].help_text = 'Optional. Interested scouts could reach out using this email.'
        self.fields['contact_phone'].help_text = 'Optional. Interested scouts could reach out using this phone number.'
        self.fields['consent_to_share_contact'].help_text = (
            'With your consent, scouts can view these details and contact you directly.'
        )
        self.fields['special_traits'].help_text = 'Enter special traits such as Playmaker, Flair, or Finesse shooter.'
        self.fields['football_experience'].help_text = 'Share your club history, achievements, and football experience.'
        self.fields['previous_club'].help_text = 'Enter the last club or academy you played for before your current club.'
        self.fields['previous_club_duration'].help_text = 'Example: 7 months, 1 year, or 2 years.'

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
            'secondary_position',
            'height_cm',
            'weight_kg',
            'current_club',
            'previous_club',
            'previous_club_duration',
            'location',
            'football_experience',
            'special_traits',
        ]

        widgets = {
            'location': forms.TextInput(
                attrs={
                    'placeholder': 'Where are you from? (Type or select a county)',
                    'list': 'kenya-counties',
                    'autocomplete': 'off',
                }
            ),
            'football_experience': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Describe your club experience and achievements',
                }
            ),
            'special_traits': forms.TextInput(
                attrs={
                    'placeholder': 'e.g. Playmaker, Flair, Finesse shooter',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].help_text = 'Choose or type a county name from the 47 counties list.'
        self.fields['secondary_position'].label = 'Secondary position'
        self.fields['height_cm'].label = 'Height (cm)'
        self.fields['weight_kg'].label = 'Weight (kg)'
        self.fields['current_club'].label = 'Current club'
        self.fields['previous_club'].label = 'Previous club'
        self.fields['previous_club_duration'].label = 'Duration at previous club'
        self.fields['football_experience'].label = 'Football experience'
        self.fields['special_traits'].label = 'Special traits'
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