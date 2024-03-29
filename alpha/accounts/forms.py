from django import forms
from accounts.models import Account, VenueAccount, VenueType

from widgets import InTheLoopTagAutoSuggest, CityAutoSuggest
from taggit.forms import TagField
from accounts.models import REMINDER_TYPES

from event.widgets import AjaxCropWidget, GeoCompleteWidget
from userena.forms import EditProfileForm

from event.forms import JSONCharField
from gmapi.forms.widgets import LocationWidget
import selectable.forms as selectable
from event.lookups import CityLookup
from accounts.lookups import RegionLookup
from cities.models import Region
from localflavor.ca.forms import CAPhoneNumberField
from ckeditor.fields import RichTextFormField


class ReminderSettingsForm(forms.ModelForm):
    reminder_with_website = forms.BooleanField(required=False, label="")
    reminder_with_email = forms.BooleanField(required=False, label="")
    reminder_with_sms = forms.BooleanField(required=False, label="")
    reminder_active_type = forms.ChoiceField(widget=forms.RadioSelect, choices=REMINDER_TYPES)
    reminder_phonenumber = CAPhoneNumberField(required=False)

    class Meta:
        model = Account
        fields = (
            'reminder_with_website',
            'reminder_with_email',
            'reminder_with_sms',
            'reminder_email',
            'reminder_phonenumber',
            'reminder_days_before_event',
            'reminder_hours_before_event',
            'reminder_on_week_day',
            'reminder_active_type'
        )

    def __init__(self, *args, **kwargs):
        super(ReminderSettingsForm, self).__init__(*args, **kwargs)

        self.fields['reminder_days_before_event'].widget.attrs['maxlength'] = 2
        self.fields['reminder_hours_before_event'].widget.attrs['maxlength'] = 2


class InTheLoopSettingsForm(forms.ModelForm):
    in_the_loop_tags = TagField(widget=InTheLoopTagAutoSuggest())
    in_the_loop_with_website = forms.BooleanField(required=False, label="")
    in_the_loop_with_email = forms.BooleanField(required=False, label="")
    in_the_loop_with_sms = forms.BooleanField(required=False, label="")
    in_the_loop_phonenumber = CAPhoneNumberField(required=False)

    regions = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=Region.objects.filter(country__code="CA"),
        required=False
    )

    cities = TagField(
        widget=CityAutoSuggest(),
        required=False
    )

    class Meta:
        model = Account
        fields = (
            'in_the_loop_tags',
            'in_the_loop_with_website',
            'in_the_loop_with_email',
            'in_the_loop_with_sms',
            'in_the_loop_email',
            'in_the_loop_phonenumber',
            'regions',
            'cities',
            'all_of_canada'
        )


class VenueAccountForm(forms.ModelForm):
    picture_src = forms.CharField(
        widget=AjaxCropWidget(),
        required=False
    )

    types = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        queryset=VenueType.active_types.all(),
        required=False
    )

    phone = CAPhoneNumberField(required=False)
    about = RichTextFormField(required=False)

    class Meta:
        model = VenueAccount

        fields = (
            'phone',
            'fax',
            'email',
            'site',
            'facebook',
            'myspace',
            'twitter',
            'about',
            'cropping',
            'types'
        )


class NewVenueAccountForm(VenueAccountForm):
    place = JSONCharField(
        widget=GeoCompleteWidget(),
        required=False
    )

    location = forms.Field(widget=LocationWidget(), required=False)
    venue_identifier = forms.CharField(required=False, widget=forms.widgets.HiddenInput())
    venue_name = forms.CharField(required=False)
    street = forms.CharField(required=False)
    street_number = forms.CharField(required=False)
    city = forms.CharField(
        widget=selectable.AutoCompleteSelectWidget(CityLookup, allow_new=True),
        required=False
    )
    city_identifier = forms.CharField(required=False, widget=forms.widgets.HiddenInput())
    about = RichTextFormField(required=False)

    def clean(self):
        cleaned_data = self.cleaned_data

        place = cleaned_data["place"]

        if not cleaned_data["venue_identifier"] and\
            (not place["venue"] or \
            not place["latitude"] or \
            not place["longtitude"]):
            raise forms.ValidationError(u'You should choose venue from list')

        return cleaned_data


class AccountForm(EditProfileForm):
    native_region = selectable.AutoCompleteSelectField(
        lookup_class=RegionLookup,
        required=False,
        widget=selectable.AutoComboboxSelectWidget(lookup_class=RegionLookup)
    )    

    class Meta:
        model = Account
        fields = [
            'mugshot',
            'date_of_birth',
            'native_region',
            'tax_origin_confirmed',
            'not_from_canada',
        ]
