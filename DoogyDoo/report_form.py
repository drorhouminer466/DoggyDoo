from django import forms
from .models import Employees_collections

class ReportForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=15, required=False)

# class EmployeeForm(forms.ModelForm):
#     # first_name = forms.CharField(max_length=100, required=True)
#     # last_name = forms.CharField(max_length=100, required=True)
#     # phone_number=forms.NumberInput(required=True)
#     # email = forms.EmailField(required=True)
#     # user_name = forms.CharField(max_length=15, required=True)
#     # password=forms.PasswordInput(max_length=15, required=True)
#     # employee_type=
#         fields = ['first_name', 'last_name', 'phone_number', 'email', 'user_name', 'password', 'employee_type']
#         widgets = {
#             'password': forms.PasswordInput(),
#         }