from django import forms


class DeleteConfirmationForm(forms.Form):
    confirmation = forms.CharField(label='Type the slug (the name used in URLs) to confirm')
    label = None
    no_match_message = 'The confirmation does not match the slug'

    def __init__(self, *args, **kwargs):
        self.deletable = kwargs.pop('deletable')
        super().__init__(*args, **kwargs)
        if self.label:
            self.fields['confirmation'].label = self.label

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data['confirmation'] != self.deletable.slug:
            self.add_error('confirmation', self.no_match_message)

        return cleaned_data
