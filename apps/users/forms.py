from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegistrationForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=[
            (User.Role.EMPLOYER, "Employer"),
            (User.Role.CANDIDATE, "Candidate")
        ],
        required=True,
        help_text="Select your account type."
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        label="Confirm Password",
    )

    class Meta:
        model = User
        fields = ["email", "role", "phone"]

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")

        if password and password2 and password != password2:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user