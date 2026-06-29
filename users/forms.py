from django import forms
from django.contrib.auth.password_validation import validate_password
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
import re

from .models import User


class RegistrationForm(forms.ModelForm):
	password = forms.CharField(
		label='Password',
		help_text='Use at least 8 characters with uppercase, lowercase, number, and a special character.',
		widget=forms.PasswordInput(attrs={'placeholder': 'Enter a password'}),
	)
	confirm_password = forms.CharField(
		label='Confirm password',
		widget=forms.PasswordInput(attrs={'placeholder': 'Repeat the password'}),
	)

	class Meta:
		model = User
		fields = ['full_name', 'email', 'role']
		widgets = {
			'full_name': forms.TextInput(attrs={'placeholder': 'Enter your full name'}),
			'email': forms.EmailInput(attrs={'placeholder': 'Enter your email address'}),
			'role': forms.Select(),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_method = 'post'
		self.helper.form_tag = False
		self.helper.layout = Layout(
			'full_name',
			'email',
			'role',
			'password',
			'confirm_password',
		)

	def clean(self):
		cleaned_data = super().clean()
		password = cleaned_data.get('password')
		confirm_password = cleaned_data.get('confirm_password')

		if password:
			try:
				validate_password(password, user=self.instance)
			except forms.ValidationError as exc:
				self.add_error('password', exc)

			if not re.search(r'[A-Z]', password):
				self.add_error('password', 'Password must include at least one uppercase letter.')
			if not re.search(r'[a-z]', password):
				self.add_error('password', 'Password must include at least one lowercase letter.')
			if not re.search(r'\d', password):
				self.add_error('password', 'Password must include at least one number.')
			if not re.search(r'[^A-Za-z0-9]', password):
				self.add_error('password', 'Password must include at least one special character.')

		if password and confirm_password and password != confirm_password:
			self.add_error('confirm_password', 'Passwords do not match.')

		return cleaned_data

	def save(self, commit=True):
		user = super().save(commit=False)
		user.set_password(self.cleaned_data['password'])
		if commit:
			user.save()
		return user


class LoginForm(forms.Form):
	email = forms.EmailField(
		label='Email',
		widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address'}),
	)
	password = forms.CharField(
		label='Password',
		widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'}),
	)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.helper = FormHelper()
		self.helper.form_method = 'post'
		self.helper.form_tag = False
		self.helper.layout = Layout(
			'email',
			'password',
		)


class AdminUserCreateForm(forms.ModelForm):
	password = forms.CharField(
		label='Password',
		widget=forms.PasswordInput(attrs={'placeholder': 'Temporary password'}),
	)

	class Meta:
		model = User
		fields = ['full_name', 'email', 'role', 'is_active', 'is_staff']

	def save(self, commit=True):
		user = super().save(commit=False)
		user.set_password(self.cleaned_data['password'])
		if commit:
			user.save()
		return user


class AdminUserUpdateForm(forms.ModelForm):
	password = forms.CharField(
		label='New password (optional)',
		required=False,
		widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to keep current password'}),
	)

	class Meta:
		model = User
		fields = ['full_name', 'email', 'role', 'is_active', 'is_staff']

	def save(self, commit=True):
		user = super().save(commit=False)
		password = self.cleaned_data.get('password')
		if password:
			user.set_password(password)
		if commit:
			user.save()
		return user
