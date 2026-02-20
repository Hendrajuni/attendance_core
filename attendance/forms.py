from django import forms

class ImportRosterForm(forms.Form):
    excel_file = forms.FileField(
        label='Select Excel File',
        help_text='Supported formats: .xlsx, .xls. Columns: NIK, Tanggal (YYYY-MM-DD), Kode Shift'
    )
