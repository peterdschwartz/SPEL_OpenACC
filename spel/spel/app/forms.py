from django import forms
from .models import SubroutineActiaveGlobalVars

class S(forms.ModelForm):
    class Meta:
        model = SubroutineActiaveGlobalVars
        fields = [
            "id",
            "subroutine",
            "variable_name"
        ]