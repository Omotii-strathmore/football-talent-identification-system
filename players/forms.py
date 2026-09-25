from django import forms
from .models import PlayerProfile, PlayerVideo, _calculate_age


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
            'date_of_birth',
            'position',
            'secondary_position',
            'height_cm',
            'weight_kg',
            'current_club',
            'previous_club',
            'previous_club_start_year',
            'previous_club_end_year',
            'location',
            'profile_photo',
            'bio',
            'football_experience',
            'special_traits',
            'contact_email',
            'contact_phone',
            'consent_to_share_contact',
        ]

        widgets = {
            'date_of_birth': forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'class': 'dob-picker-input',
                    'placeholder': 'Select your date of birth',
                    'autocomplete': 'off',
                },
            ),
            'previous_club_start_year': forms.NumberInput(attrs={'placeholder': 'From year, e.g. 2019'}),
            'previous_club_end_year': forms.NumberInput(attrs={'placeholder': 'To year, e.g. 2021'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_of_birth'].input_formats = ['%Y-%m-%d']
        self.fields['date_of_birth'].required = False
        self.fields['date_of_birth'].help_text = 'Keeps your age accurate automatically. Allowed range: 12 to 28 years old.'
        self.fields['contact_email'].required = False
        self.fields['contact_phone'].required = False
        self.fields['secondary_position'].required = False
        self.fields['height_cm'].required = False
        self.fields['weight_kg'].required = False
        self.fields['current_club'].required = False
        self.fields['previous_club'].required = False
        self.fields['previous_club_start_year'].required = False
        self.fields['previous_club_end_year'].required = False
        self.fields['special_traits'].required = False
        self.fields['football_experience'].required = False
        self.fields['contact_email'].help_text = 'Optional. Interested scouts could reach out using this email.'
        self.fields['contact_phone'].help_text = 'Optional. Interested scouts could reach out using this phone number.'
        self.fields['consent_to_share_contact'].help_text = (
            'With your consent, scouts can view these details and contact you directly.'
        )
        self.fields['special_traits'].help_text = 'Enter special traits such as Playmaker, Flair, or Finesse shooter.'
        self.fields['football_experience'].label = 'Achievements at previous club'
        self.fields['football_experience'].help_text = 'Briefly describe what you achieved there, e.g. top scorer, captain, promotion.'
        self.fields['previous_club'].help_text = 'Enter the last club or academy you played for before your current club.'
        self.fields['previous_club_start_year'].label = 'From year'
        self.fields['previous_club_end_year'].label = 'To year'

    def clean(self):
        cleaned_data = super().clean()

        dob = cleaned_data.get('date_of_birth')
        if dob:
            age = _calculate_age(dob)
            if age < 12 or age > 28:
                self.add_error('date_of_birth', 'Age must be between 12 and 28 years old.')

        start_year = cleaned_data.get('previous_club_start_year')
        end_year = cleaned_data.get('previous_club_end_year')
        if start_year and end_year and end_year < start_year:
            self.add_error('previous_club_end_year', 'End year cannot be before the start year.')

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

    date_of_birth = forms.DateField(
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            format='%Y-%m-%d',
            attrs={
                'class': 'dob-picker-input',
                'placeholder': 'Select your date of birth',
                'autocomplete': 'off',
            },
        ),
        help_text='Allowed age range: 12 to 28 years.',
    )

    class Meta:

        model = PlayerProfile

        fields = [
            'date_of_birth',
            'position',
            'location',
        ]

        widgets = {
            'location': forms.TextInput(
                attrs={
                    'placeholder': 'Where are you from? (Type or select a county)',
                    'list': 'kenya-counties',
                    'autocomplete': 'off',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].help_text = 'Choose or type a county name from the 47 counties list.'

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        age = _calculate_age(dob)
        if age < 12 or age > 28:
            raise forms.ValidationError('Age must be between 12 and 28 years old.')
        return dob

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
            'category',
            'description',
            'video_file',
        ]

        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Video title'}),
            'description': forms.Textarea(
                attrs={
                    'rows': 2,
                    'placeholder': 'Optional: what should scouts look out for in this clip?',
                }
            ),
            'video_file': forms.FileInput(attrs={'accept': 'video/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['category'].label = 'Video type'

    def clean_video_file(self):
        video_file = self.cleaned_data.get('video_file')
        if video_file:
            max_size_mb = 100
            if video_file.size > max_size_mb * 1024 * 1024:
                raise forms.ValidationError(f'Video file is too large. Please keep it under {max_size_mb}MB.')
        return video_file