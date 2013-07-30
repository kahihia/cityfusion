# Create your views here.

from models import Account, VenueAccount
from event.models import Event, FeaturedEvent, Venue
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils.translation import ugettext as _

from accounts.forms import ReminderSettingsForm, InTheLoopSettingsForm, VenueAccountForm, NewVenueAccountForm

from django.conf import settings

from django.utils import simplejson as json
from django.db.models.loading import get_model
from django.contrib.contenttypes.models import ContentType

from utils import remind_account_about_events, inform_account_about_events_with_tag
from django.contrib.auth.decorators import login_required
from accounts.decorators import ajax_login_required

from userena import settings as userena_settings
from userena.utils import get_profile_model, get_user_model
from userena.views import ExtraContextTemplateView

from django.contrib.gis.geos import Point
from cities.models import City, Country
from django.db.models import Q
from event.utils import find_nearest_city
from advertising.models import AdvertisingOrder
from accounts.forms import AccountForm


MAX_SUGGESTIONS = getattr(settings, 'TAGGIT_AUTOSUGGEST_MAX_SUGGESTIONS', 10)

TAG_MODEL = getattr(settings, 'TAGGIT_AUTOSUGGEST_MODEL', ('taggit', 'Tag'))
TAG_MODEL = get_model(*TAG_MODEL)


@ajax_login_required
def remind_me(request, event_id):
    profile = Account.objects.get(user_id=request.user.id)
    event = Event.future_events.get(id=event_id)
    profile.reminder_events.add(event)

    return HttpResponse(json.dumps({
        "id": event.id,
        "name": event.name
    }), mimetype='application/json')


@login_required
def remove_remind_me(request, event_id):
    profile = Account.objects.get(user_id=request.user.id)
    event = Event.future_events.get(id=event_id)
    profile.reminder_events.remove(event)

    return HttpResponseRedirect("/account/%s/" % request.user.username)


@ajax_login_required
def add_in_the_loop(request):
    profile = Account.objects.get(user_id=request.user.id)
    tags = request.GET.getlist("tag[]")
    profile.in_the_loop_tags.add(*tags)

    return HttpResponse(json.dumps({
        "tags": tags
    }), mimetype='application/json')

    return render_to_response('accounts/ajax_result_add_in_the_loop.html', {
        "tags": tags
    }, context_instance=RequestContext(request))


@login_required
def reminder_settings(request):
    account = Account.objects.get(user_id=request.user.id)
    form = ReminderSettingsForm(instance=account)
    if request.method == 'POST':
        form = ReminderSettingsForm(instance=account, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reminder options updated.')
            return HttpResponseRedirect('/account/%s/' % request.user.username)

    return render_to_response('accounts/reminder_settings.html', {
        "form": form
    }, context_instance=RequestContext(request))

@login_required
def in_the_loop_settings(request):
    account = Account.objects.get(user_id=request.user.id)
    form = InTheLoopSettingsForm(instance=account)

    if request.method == 'POST':
        form = InTheLoopSettingsForm(instance=account, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'In the loop options updated.')
            return HttpResponseRedirect('/account/%s/' % request.user.username)

    return render_to_response('accounts/in_the_loop_settings.html', {
        "form": form
    }, context_instance=RequestContext(request))


def in_the_loop_tags(request):
    """
    Returns a list of JSON objects with a `name` and a `value` property that
    all start like your query string `q` (not case sensitive).
    """
    query = request.GET.get('q', '')
    limit = request.GET.get('limit', MAX_SUGGESTIONS)
    try:
        request.GET.get('limit', MAX_SUGGESTIONS)
        limit = min(int(limit), MAX_SUGGESTIONS)  # max or less
    except ValueError:
        limit = MAX_SUGGESTIONS

    tag_name_qs = TAG_MODEL.objects.filter(
        name__icontains=query,
        taggit_taggeditem_items__content_type=ContentType.objects.get_for_model(Event)
    ).values_list('name', flat=True).distinct()

    data = [{'name': n, 'value': n} for n in tag_name_qs[:limit]]

    return HttpResponse(json.dumps(data), mimetype='application/json')

def cities_autosuggest(request):
    query = request.GET.get('q', '')
    limit = request.GET.get('limit', MAX_SUGGESTIONS)
    try:
        request.GET.get('limit', MAX_SUGGESTIONS)
        limit = min(int(limit), MAX_SUGGESTIONS)  # max or less
    except ValueError:
        limit = MAX_SUGGESTIONS

    cities = City.objects.filter(
        name__icontains=query
    )

    data = [{'name': city.__unicode__(), 'value': str(city.id) } for city in cities[:limit]]

    return HttpResponse(json.dumps(data), mimetype='application/json')


def remind_preview(request):
    message = remind_account_about_events(
        Account.objects.get(user__email="jaromudr@gmail.com"),
        Event.future_events.all()[0:1]
    )

    return HttpResponse(message)


def in_the_loop_preview(request):
    message = inform_account_about_events_with_tag(
        Account.objects.get(user__email="jaromudr@gmail.com"),
        Event.future_events.all()[0:1],
        {
            "opa": ["Montreal"],
            "hmm": ["Ottava", "Odessa"]
        }
    )

    return HttpResponse(message)


@login_required
def private_venue_account(request, slug):
    venue_account = VenueAccount.objects.get(slug=slug)

    venue_events = Event.future_events.filter(venue=venue_account.venue)
    venue_featured_events = Event.featured_events.filter(venue=venue_account.venue)
    venue_archived_events = Event.archived_events.filter(venue=venue_account.venue)
    featured_events_stats = FeaturedEvent.objects.filter(event__venue_id=venue_account.venue.id)

    tabs_page = "private-venue-account"

    active_tab = request.session.get(tabs_page, "venue-events")

    return render_to_response('venue_accounts/private_venue_account.html', {
                'venue_account': venue_account,
                'venue_events': venue_events,
                'venue_featured_events': venue_featured_events,
                'venue_archived_events': venue_archived_events,
                'featured_events_stats': featured_events_stats,
                'tabs_page': tabs_page,
                'active_tab': active_tab,
                'private': True

        }, context_instance=RequestContext(request))


def public_venue_account(request, slug):
    venue_account = VenueAccount.objects.get(slug=slug)

    venue_events = Event.future_events.filter(venue=venue_account.venue)
    venue_featured_events = Event.featured_events.filter(venue=venue_account.venue)

    tabs_page = "public-venue-account"

    active_tab = request.session.get(tabs_page, "venue-events")

    return render_to_response('venue_accounts/public_venue_account.html', {
                'venue_account': venue_account,
                'venue_events': venue_events,
                'venue_featured_events': venue_featured_events,
                'tabs_page': tabs_page,
                'active_tab': active_tab,
                'private': False
        }, context_instance=RequestContext(request))


@login_required
def edit_venue_account(request, slug):
    venue_account = VenueAccount.objects.get(slug=slug)
    form = VenueAccountForm(
        instance=venue_account,
        initial={
            "picture_src": "/media/%s" % venue_account.picture,
        }
    )

    if request.method == 'POST':
        if request.POST["picture_src"]:
            venue_account.picture.name = request.POST["picture_src"].replace(settings.MEDIA_URL, "")

        form = VenueAccountForm(instance=venue_account, data=request.POST)

        if form.is_valid():
            form.save()
            types = form.cleaned_data['types']
            venue_account.types = types
            return HttpResponseRedirect(reverse('private_venue_account', args=(venue_account.slug, )))

    return render_to_response('venue_accounts/edit_venue_account.html', {
            'venue_account': venue_account,
            'form': form
        }, context_instance=RequestContext(request))


def save_venue(request):
    name = request.POST["venue_name"]
    street = request.POST["street"]
    location = Point((
        float(request.POST["location_lng"]),
        float(request.POST["location_lat"])
    ))

    if request.POST["city_identifier"]:
        city = City.objects.get(id=int(request.POST["city_identifier"]))

    else:
        cities = City.objects.filter(
            Q(name_std=request.POST["geo_city"].encode('utf8')) |
            Q(name=request.POST["geo_city"])
        )

        if cities.count() > 1:
            city = find_nearest_city(cities, location)
        elif not cities.count():
            city = City.objects.distance(location).order_by('distance')[0]
        else:
            city = cities[0]

    country = Country.objects.get(name='Canada')
    venue, created = Venue.objects.get_or_create(name=name, street=street, city=city, country=country, location=location)

    return venue  


@login_required
def create_venue_account(request):
    account = Account.objects.get(user_id=request.user.id)
    form = NewVenueAccountForm()

    venue_account = VenueAccount()

    if request.method == 'POST':
        form = NewVenueAccountForm(data=request.POST)

        if form.is_valid():
            venue = save_venue(request)

            try:
                venue_account = VenueAccount.objects.get(venue=venue)
                return HttpResponseRedirect(reverse('venue_account_already_in_use', args=(venue_account.id, )))

            except:               
                venue_account = VenueAccount(venue=venue, account=account)
                form = NewVenueAccountForm(instance=venue_account, data=request.POST)
                venue_account = form.save()

                types = form.cleaned_data['types']
                venue_account.types = types
                venue_account.save()

                return HttpResponseRedirect(reverse('account_profile_detail', args=(request.user.username, )))                

    return render_to_response('venue_accounts/create_venue_account.html', {
            'venue_account': venue_account,
            'form': form
        }, context_instance=RequestContext(request))


def venue_account_already_in_use(request, venue_account_id):
    venue_account = VenueAccount.objects.get(id=venue_account_id)

    return render_to_response('venue_accounts/already_in_use.html', {
            'venue_account': venue_account
        }, context_instance=RequestContext(request))


def set_venue_privacy(request, venue_account_id, privacy):
    public = (privacy == "public")
    venue_account = VenueAccount.objects.get(id=venue_account_id)
    venue_account.public = public
    venue_account.save()

    return HttpResponse(
        "You make %s venue %s" % (venue_account.venue.name, privacy)
    )


@login_required
def unlink_venue_account_from_user_profile(request, venue_account_id):
    VenueAccount.objects.get(id=venue_account_id).delete()

    return HttpResponseRedirect(
        reverse('account_profile_detail', args=(request.user.username, ))
    )


def profile_detail(request, username, template_name=userena_settings.USERENA_PROFILE_DETAIL_TEMPLATE, extra_context=None, **kwargs):
    """
    Detailed view of an user.

    :param username:
        String of the username of which the profile should be viewed.

    :param template_name:
        String representing the template name that should be used to display
        the profile.

    :param extra_context:
        Dictionary of variables which should be supplied to the template. The
        ``profile`` key is always the current profile.

    **Context**

    ``profile``
        Instance of the currently viewed ``Profile``.

    """
    user = get_object_or_404(get_user_model(),
                             username__iexact=username)

    profile_model = get_profile_model()
    try:
        profile = user.get_profile()
    except profile_model.DoesNotExist:
        profile = profile_model.objects.create(user=user)

    if not profile.can_view_profile(request.user):
        return HttpResponseForbidden(_("You don't have permission to view this profile."))
    if not extra_context:
        extra_context = dict()
    
    extra_context['profile'] = user.get_profile()
    extra_context['hide_email'] = userena_settings.USERENA_HIDE_EMAIL
    extra_context['location'] = request.user_location["location"]

    tabs_page = "profile-detail"
    active_tab = request.session.get(tabs_page, "account-events")
    extra_context['active_tab'] = active_tab

    return ExtraContextTemplateView.as_view(
        template_name=template_name,
        extra_context=extra_context
    )(request)    


def orders(request):
    account = Account.objects.get(user_id=request.user.id)

    advertising_orders = AdvertisingOrder.objects.filter(campaign__account_id=account.id)

    return render_to_response('accounts/orders.html', {
            'account': account,
            'advertising_orders': advertising_orders,
            'featured_orders': []
        }, context_instance=RequestContext(request))


from userena.decorators import secure_required
from guardian.decorators import permission_required_or_403


@secure_required
@permission_required_or_403('change_profile', (get_profile_model(), 'user__username', 'username'))
def profile_edit(request, username, edit_profile_form=AccountForm,
                 template_name='userena/profile_form.html', success_url=None, why_message=None, 
                 extra_context=None, **kwargs):
    """
    Edit profile.

    Edits a profile selected by the supplied username. First checks
    permissions if the user is allowed to edit this profile, if denied will
    show a 404. When the profile is successfully edited will redirect to
    ``success_url``.

    :param username:
        Username of the user which profile should be edited.

    :param edit_profile_form:

        Form that is used to edit the profile. The :func:`EditProfileForm.save`
        method of this form will be called when the form
        :func:`EditProfileForm.is_valid`.  Defaults to :class:`EditProfileForm`
        from userena.

    :param template_name:
        String of the template that is used to render this view. Defaults to
        ``userena/edit_profile_form.html``.

    :param success_url:
        Named URL which will be passed on to a django ``reverse`` function after
        the form is successfully saved. Defaults to the ``userena_detail`` url.

    :param extra_context:
        Dictionary containing variables that are passed on to the
        ``template_name`` template.  ``form`` key will always be the form used
        to edit the profile, and the ``profile`` key is always the edited
        profile.

    **Context**

    ``form``
        Form that is used to alter the profile.

    ``profile``
        Instance of the ``Profile`` that is edited.

    """
    user = get_object_or_404(get_user_model(),
                             username__iexact=username)

    profile = user.get_profile()

    user_initial = {'first_name': user.first_name,
                    'last_name': user.last_name}

    form = edit_profile_form(instance=profile, initial=user_initial)

    if request.method == 'POST':
        form = edit_profile_form(request.POST, request.FILES, instance=profile,
                                 initial=user_initial)

        if form.is_valid():
            profile = form.save()

            if userena_settings.USERENA_USE_MESSAGES:
                messages.success(request, _('Your profile has been updated.'),
                                 fail_silently=True)

            if success_url: redirect_to = success_url
            else: redirect_to = reverse('account_profile_detail', kwargs={'username': username})
            return redirect(redirect_to)

    if not extra_context: extra_context = dict()
    extra_context['form'] = form
    extra_context['profile'] = profile
    extra_context['why_message'] = why_message


    return ExtraContextTemplateView.as_view(template_name=template_name,
                                            extra_context=extra_context)(request)


def set_context(request, context="root"):
    if context=="root":
        request.session['venue_account_id'] = None
    else:
        venue_account = VenueAccount.objects.get(slug=context)
        request.session['venue_account_id'] = venue_account.id

    return HttpResponseRedirect(request.META.get('HTTP_REFERER','/'))


def redirect_to_active_user_context(request):
    venue_account_id = request.session.get('venue_account_id', None)

    if venue_account_id:
        venue_account = VenueAccount.objects.get(id=venue_account_id)
        return HttpResponseRedirect(reverse('private_venue_account', args=(venue_account.slug, )))

    else:
        return HttpResponseRedirect(reverse('account_profile_detail', kwargs={'username': request.user.username}))    
    