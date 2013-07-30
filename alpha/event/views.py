import datetime
import time
import json
import utils

from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail.message import EmailMessage
from django.utils.safestring import mark_safe

from django.conf import settings
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template.loader import render_to_string
from django.template import RequestContext

from django.middleware.csrf import get_token

from django.contrib.gis.geos import Point
from cities.models import City, Country, Region
from django.db.models import Q, Count
from event.filters import EventFilter

from event import DEFAULT_FROM_EMAIL

from event.models import Event, Venue, SingleEvent, AuditEvent, FakeAuditEvent, FeaturedEvent, FeaturedEventOrder
from event.utils import find_nearest_city

from event.forms import SetupFeaturedForm, CreateEventForm, EditEventForm

from taggit.models import Tag, TaggedItem

from ajaxuploader.views import AjaxFileUploader

from accounts.models import Account

from moneyed import Money, CAD
from django.contrib.auth.decorators import login_required
from accounts.decorators import native_region_required


def start(request):
    csrf_token = get_token(request)
    return render_to_response('import.html',
        {'csrf_token': csrf_token}, context_instance=RequestContext(request))


import_uploader = AjaxFileUploader()


def redirect(request):
    return HttpResponseRedirect(reverse('event_browse'))


def search_pad(request):
    start_date, end_date = utils.get_dates_from_request(request)
    start_time, end_time = utils.get_times_from_request(request)

    featured_events = Event.featured_events.all()

    featuredEventsFilter = EventFilter({}, queryset=featured_events)

    events = SingleEvent.future_events.all()

    events_all_count = events.count()

    params = request.GET.copy()

    if not "location" in params:
        params["location"] = "%s|%s" % (
            request.user_location["user_location_type"],
            request.user_location["user_location_id"]
        )

    eventsFilter = EventFilter(params, queryset=events)

    top10_tags = TaggedItem.objects.filter(object_id__in=map(lambda event: event.event.id, eventsFilter.qs())) \
        .values('tag', 'tag__name') \
        .annotate(count=Count('id')) \
        .order_by('-count')[0:10]

    return render_to_response('events/search_pad.html', {
                                'featured_events': featured_events,
                                'featuredEventsFilter': featuredEventsFilter,
                                'events': events,
                                'eventsFilter': eventsFilter,
                                'top10_tags': top10_tags,
                                'events_all_count': events_all_count,
                                'start_date': start_date,
                                'end_date': end_date,
                                'start_time': start_time,
                                'end_time': end_time
                            }, context_instance=RequestContext(request))


def browse(request):
    start_date, end_date = utils.get_dates_from_request(request)
    start_time, end_time = utils.get_times_from_request(request)

    featured_events = Event.featured_events.all()

    featuredEventsFilter = EventFilter({}, queryset=featured_events)

    events = SingleEvent.future_events.all()

    params = request.GET.copy()

    if not "location" in params:
        params["location"] = "%s|%s" % (
            request.user_location["user_location_type"],
            request.user_location["user_location_id"]
        )

    eventsFilter = EventFilter(params, queryset=events)

    tags = TaggedItem.objects.filter(object_id__in=map(lambda event: event.event.id, eventsFilter.qs())) \
        .values('tag', 'tag__name') \
        .annotate(count=Count('id')) \
        .order_by('-count')

    return render_to_response('events/browse_events.html', {
                                'featured_events': featured_events,
                                'featuredEventsFilter': featuredEventsFilter,
                                'events': events,
                                'eventsFilter': eventsFilter,
                                'tags': tags,
                                'start_date': start_date,
                                'end_date': end_date,
                                'start_time': start_time,
                                'end_time': end_time
                            }, context_instance=RequestContext(request))


def view_featured(request, slug, date):
    try:
        event = Event.future_events.get(slug=slug, start_time__startswith=date)
    except ObjectDoesNotExist:
        return HttpResponseRedirect(reverse('event_browse'))   
        
    event.featuredevent_set.all()[0].click() 

    return HttpResponseRedirect(reverse('event_view', args=(slug, date))) 


def view(request, slug, date=None):
    try:
        if date:
            event = SingleEvent.future_events.get(event__slug=slug, start_time__startswith=date)
        else:
            event = Event.future_events.get(slug=slug)
    except ObjectDoesNotExist:
        return HttpResponseRedirect(reverse('event_browse'))

    venue = event.venue

    events_from_venue = SingleEvent.future_events.filter(event__venue_id=venue.id)
    if date:
        events_from_venue = events_from_venue.exclude(id=event.id)

    return render_to_response('events/event_description.html', {
            'event': event,
            'events_from_venue': events_from_venue
        }, context_instance=RequestContext(request))


def save_venue(request):
    if request.POST["venue_name"]:
        name = request.POST["venue_name"]
        street = request.POST["street"]
        city = City.objects.get(id=int(request.POST["city_identifier"]))
        country = Country.objects.get(name='Canada')
        location = Point((
            float(request.POST["location_lng"]),
            float(request.POST["location_lat"])
        ))
        venue = Venue(name=name, street=street, city=city, country=country, location=location)
        venue.save()
    elif request.POST["place"]:
        name = request.POST["geo_venue"]
        street = request.POST["geo_street"]
        city = City.objects.filter(
            Q(name_std=request.POST["geo_city"].encode('utf8')) |
            Q(name=request.POST["geo_city"])
        )
        country = Country.objects.get(name='Canada')
        location = Point((
            float(request.POST["geo_longtitude"]),
            float(request.POST["geo_latitude"])
        ))

        if city.count() > 1:
            city = find_nearest_city(city, location)
        elif not city.count():
            city = City.objects.distance(location).order_by('distance')[0]
        else:
            city = city[0]
        venue, created = Venue.objects.get_or_create(name=name, street=street, city=city, country=country, location=location)
    return venue


def save_when_and_description(request, event_obj):
    when_json = json.loads(request.POST["when_json"])
    description_json = json.loads(request.POST["description_json"])

    event_obj.description = description_json['default']

    for year, months in when_json.iteritems():
        for month, days in months.iteritems():
            for day, times in days.iteritems():
                date = datetime.datetime(int(year), int(month), int(day), 0, 0)
                if date.strftime("%m/%d/%Y") in description_json['days']:
                    description = description_json['days'][date.strftime("%m/%d/%Y")]
                else:
                    description = ""
                start_time = time.strptime(times["start"], '%I:%M %p')
                start = datetime.datetime(int(year), int(month), int(day), start_time[3], start_time[4])

                end_time = time.strptime(times["end"], '%I:%M %p')
                end = datetime.datetime(int(year), int(month), int(day), end_time[3], end_time[4])

                single_event = SingleEvent(
                    event=event_obj,
                    start_time=start.strftime('%Y-%m-%d %H:%M'),
                    end_time=end.strftime('%Y-%m-%d %H:%M'),
                    description=description
                )
                single_event.save()


def send_event_details_email(event_obj):
    current_site = settings.EVENT_EMAIL_SITE
    subject = render_to_string('events/create/creation_email_subject.txt', {
            'site': current_site,
            'title': mark_safe(event_obj.name)
        })

    subject = ''.join(subject.splitlines())  # Email subjects are all on one line

    message = render_to_string('events/create/creation_email.txt', {
            'authentication_key': event_obj.authentication_key,
            'slug': event_obj.slug,
            'site': current_site
        })

    msg = EmailMessage(subject,
               message,
               DEFAULT_FROM_EMAIL,
               [event_obj.email])
    msg.content_subtype = 'html'
    msg.send()


def save_event(request, form):
    event = form.save()

    if event.venue_account_owner:
        venue = event.venue_account_owner.venue
    else:
        venue = save_venue(request)

    event.venue = venue

    save_when_and_description(request, event)

    if request.user.is_authenticated():
        #if logged in, use the users info to complete form
        event.owner = request.user
        event.email = request.user.email  # don't really need this line

    if request.POST["picture_src"]:
        event.picture.name = request.POST["picture_src"].replace(settings.MEDIA_URL, "")

    event = event.save()  # save to the database
    # form.save_m2m()  # needed for many-to-many fields (i.e. the event tags)
    return event


@login_required
def create(request, success_url=None, template_name='events/create/create_event.html'):
    if request.method == 'POST':
        form = CreateEventForm(account=request.account, data=request.POST)
        if form.is_valid():
            event_obj = save_event(request, form)
            send_event_details_email(event_obj)

            if success_url is None:
                success_url = reverse('event_created', kwargs={ 'slug': event_obj.slug })

            return HttpResponseRedirect(success_url)
    else:
        form = CreateEventForm(account=request.account, initial={
            "venue_account_owner": request.current_venue_account
        })


    context = RequestContext(request)
    return render_to_response(template_name, {
            'form': form,
            'posting': True,
            'location': request.user_location["location"],
        }, context_instance=context)


def created(request, slug=None):
    if slug is None:
        raise Http404

    return render_to_response('events/create/creation_complete.html', {
            'slug': slug,
            'posting': True,
        }, context_instance=RequestContext(request))


def initial_place(event):
    venue = event.venue

    full_parts = [x for x in [venue.name, venue.street, venue.city.name, venue.country.name] if x]
    place = {
        "full": ", ".join(full_parts),
        "venue": venue.name,
        "street": venue.street,
        "city": venue.city.name,
        "country": venue.country.name,
        "longtitude": venue.location.x,
        "latitude": venue.location.y
    }

    return place

def initial_location(event):
    return (event.venue.location.y, event.venue.location.x)

def inital_picture_src(event):
    return "/media/%s" % event.picture

def initial_for_event_form(event):    
    when_json = {}
    description_json = {
        "default": event.description,
        "days": {}
    }

    single_events = SingleEvent.objects.filter(event=event)

    for se in single_events:
        start_time = se.start_time
        year = start_time.year
        month = start_time.month
        day = start_time.day

        if not year in when_json:
            when_json[year] = {}

        if not month in when_json[year]:
            when_json[year][month] = {}

        when_json[year][month][day] = {
            "start": start_time.strftime('%I:%M %p'),
            "end": se.end_time.strftime('%I:%M %p')
        }

        description_json["days"][start_time.strftime("%m/%d/%Y")] = se.description

    return {
            "place": initial_place(event),
            "location": initial_location(event),
            "picture_src": inital_picture_src(event),
            "when_json": json.dumps(when_json),
            "description_json": json.dumps(description_json)
        }


@login_required
def edit(request, success_url=None, authentication_key=None, template_name='events/edit/edit_event.html'):
    try:
        event = Event.events.get(authentication_key__exact=authentication_key)
    except ObjectDoesNotExist:
        return HttpResponseRedirect(reverse('event_create'))

    # Set the return address
    if success_url is None:
        success_url = reverse('event_view', kwargs={'slug': event.slug})

    # Verify and save the form to model
    if request.method == 'POST':
        form = EditEventForm(account=request.account, instance=event, data=request.POST)
        if form.is_valid():
            SingleEvent.objects.filter(event=event).delete()

            event = save_event(request, form)
            return HttpResponseRedirect(success_url)
    else:
        form = EditEventForm(
            account=request.account,
            instance=event,
            initial=initial_for_event_form(event)
        )

    return render_to_response(template_name, {
                                'form': form,
                                'event': event,
                                'location': request.user_location["location"],
                            },
                            context_instance=RequestContext(request))


@login_required
def copy(request, authentication_key, template_name='events/create/copy_event.html'):
    if request.method == 'POST':
        form = CreateEventForm(account=request.account, data=request.POST)
        if form.is_valid():
            event_obj = save_event(request, form)
            send_event_details_email(event_obj)

            success_url = reverse('event_created', kwargs={ 'slug': event_obj.slug })

            return HttpResponseRedirect(success_url)
    else:
        basic_event = Event.events.get(authentication_key__exact=authentication_key)   

        event = Event(
            name=basic_event.name, 
            description=basic_event.description,
            price=basic_event.price,
            website=basic_event.website,
            tickets=basic_event.tickets,
            owner=basic_event.owner,
            venue_account_owner=basic_event.venue_account_owner,
            picture=basic_event.picture,
            cropping=basic_event.cropping
        )

        form = CreateEventForm(account=request.account, instance=event, initial={
            "place": initial_place(basic_event),
            "location": initial_location(basic_event),
            "picture_src": inital_picture_src(basic_event),
            "tags": basic_event.tags_representation
        })

    return render_to_response(template_name, {
            'form': form,
            'posting': True,
            'location': request.user_location["location"],
        }, context_instance=RequestContext(request))    


def remove(request, authentication_key):
    event_obj = Event.events.get(authentication_key__exact=authentication_key)
    event_obj.delete()

    return HttpResponseRedirect(reverse('private_venue_account', args=(request.current_venue_account.slug, )))


@login_required
@native_region_required(why_message="native_region_required")
def setup_featured(request, authentication_key):
    account = request.account
    event = Event.events.get(authentication_key__exact=authentication_key)    

    featured_event = FeaturedEvent(
        event=event,
        owner=account,
        start_time=datetime.date.today(),
        end_time=datetime.date.today() + datetime.timedelta(days=15)
    )

    venue_account_featured_stats = FeaturedEvent.objects.filter(event__venue_id=event.venue.id)

    form = SetupFeaturedForm(
        instance=featured_event
    )

    if request.method == 'POST':
        form = SetupFeaturedForm(instance=featured_event, data=request.POST)

        if form.is_valid():
            featured_event = form.save()

            cost = (featured_event.end_time-featured_event.start_time).days * Money(2, CAD)
            total_price = cost

            for tax in account.taxes():
                total_price = total_price + (cost * tax.tax)

            order = FeaturedEventOrder(
                cost=cost,
                total_price=total_price,
                featured_event=featured_event,
                account=account
            )

            order.save()

            return HttpResponseRedirect(reverse('setup_featured_payment', args=(str(order.id),)))

    return render_to_response('events/setup_featured_event.html', {
            'form': form,
            'featured_events_stats': venue_account_featured_stats
        }, context_instance=RequestContext(request))


def payment(request, order_id):
    order = get_object_or_404(FeaturedEventOrder, pk=order_id)

    # form = PaypalConfirmationForm()

    return render_to_response('featured/payment.html', {
        "order": order
    }, context_instance=RequestContext(request))    


def ason(request):
    tag_list = []
    all_events = Event.events.all()
    for j in all_events:
        for u in j.tags.all():
            tag_list.append(u.name)

    return HttpResponse(json.dumps(tag_list), mimetype="application/json")


def city_tags(request):
    city = None
    if request.method == 'POST':
        if "city_identifier" in request.POST:
            city = City.objects.get(id=int(request.POST["city_identifier"]))

        elif "geo_city" in request.POST:
            cities = City.objects.filter(
                Q(name_std=request.POST["geo_city"].encode('utf8')) |
                Q(name=request.POST["geo_city"])
            )
            if cities.count():
                city = cities[0]

        if city:
            tags = Event.events.filter(venue__city=city).select_related('tags').values('tags')
            tags = set([tag['tags'] for tag in tags if tag['tags']])
        else:
            tags = []

        tags = Tag.objects.filter(Q(id__in=tags) |
            Q(name__in=["Free", "Wheelchair"])
        ).values()
        return HttpResponse(json.dumps({"tags": list(tags)}), mimetype="application/json")


def audit_event_list(request):
    audit_events = AuditEvent.objects.all()
    return render_to_response("audit/event_list.html", {'audit_events': audit_events}, context_instance=RequestContext(request))


def audit_event_remove(request, id):
    audit_event = AuditEvent.objects.get(pk=id)
    audit_event.delete()
    return audit_event_list(request)


def audit_event_edit(request, id):
    audit_event = AuditEvent.objects.get(pk=id)
    return render_to_response("audit/event_edit.html", {'audit_event': audit_event}, context_instance=RequestContext(request))


def audit_event_update(request, id):
    audit_event = AuditEvent.objects.get(pk=id)
    audit_event_fake = FakeAuditEvent.objects.get(pk=id)
    event_obj = Event.events.get(pk=id)
    audit_event.phrases.clear()
    audit_event_fake.delete()

    event_obj.audited = True
    event_obj.name = request.POST["name"]
    event_obj.description = request.POST["description"]
    event_obj.save()
    return audit_event_list(request)


def audit_event_admin_update(request, id):
    audit_event = AuditEvent.objects.get(pk=id)
    audit_event_fake = FakeAuditEvent.objects.get(pk=id)
    event_obj = Event.events.get(pk=id)
    audit_event.phrases.clear()
    audit_event_fake.delete()

    event_obj.audited = True
    event_obj.name = request.POST["name"]
    event_obj.description = request.POST["description"]
    event_obj.save()
    return HttpResponseRedirect('/admin/event/auditevent')


def audit_event_approve(request, id):
    audit_event = AuditEvent.objects.get(pk=id)
    audit_event_fake = FakeAuditEvent.objects.get(pk=id)
    event_obj = Event.events.get(pk=id)
    audit_event.phrases.clear()
    audit_event_fake.delete()

    event_obj.audited = True
    event_obj.save()
    return audit_event_list(request)


def nearest_venues(request):
    if request.method == 'GET':
        search = request.GET.get("search", "")

        venues = Venue.with_active_events()
        if search:
            venues = venues.filter(Q(name__icontains=search) | Q(city__name__icontains=search))
        if request.location:
            venues = venues.distance(Point(request.location)).order_by('-distance')[:10]

        return HttpResponse(json.dumps({
            "venues": [{
                "id": venue.id,
                "name": venue.name,
                "city": venue.city.name_std
            } for venue in venues.select_related("city")]
        }), mimetype="application/json")


def save_active_tab(request, page, tab):
    request.session[page] = tab
    return HttpResponse("OK")


def location_autocomplete(request):
    """
        I should give user opportunity to choose region where from events is interesting for him. It can be whole Canada, regions or city
    """

    if request.method == 'GET':
        canada = Country.objects.get(name="Canada")

        locations = []

        kwargs = {
            "country": canada
        }

        search = request.GET.get("search", "")

        if search: 
            kwargs["name__icontains"] = search

        cities = City.objects.filter(**kwargs)

        if request.user_location:
            cities = cities.distance(Point(request.user_location["location"])).order_by('-distance')

        cities = cities[0:5]

        for city in cities:
            if city.region:
                name = "%s, %s, %s" % (city.name, city.region.name, city.country.name)
            else:
                name = "%s, %s" % (city.name, city.country.name)
            locations.append({
                "id": city.id,
                "type": "city",
                "name": name
            })

        regions = Region.objects.filter(**kwargs)[:5]

        for region in regions:
            locations.append({
                "id": region.id,
                "type": "region",
                "name": "%s, %s" % (region.name, region.country.name)
            })

        if not search or search.lower() in "canada":
            locations.append({
                "id": canada.id,
                "type": "country",
                "name": "Canada"
            })

        return HttpResponse(json.dumps({
            "locations": locations
        }), mimetype="application/json")
