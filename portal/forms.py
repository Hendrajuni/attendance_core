from django import forms
from attendance.models import Department

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'location_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location_type': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Nama Departemen',
            'location_type': 'Tipe Lokasi',
        }
